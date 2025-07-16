import cv2
import itertools
import json
import logging
import numpy as np
import os
import pandas as pd
import traceback

from dataclasses import dataclass
from enum import Enum
from sklearn.cluster import DBSCAN
from typing import Optional, Tuple, Dict, List, NamedTuple, TypedDict

logger = logging.getLogger(__name__)

# # Field dimensions in yards
# FIELD_LENGTH = 120  # 100 yards + 2x10 yard end zones
# FIELD_WIDTH = 53.3

class League(Enum):
    """Enumeration for football leagues."""
    NFL = 'NFL'
    NCAA = 'NCAA'
    HS = 'HS'
    CFL = 'CFL'

field_lengths = {
    League.NFL: 120,
    League.NCAA: 120,
    League.HS: 120,
    League.CFL: 150  # CFL field is longer
}

field_widths = {
    League.NFL: 53.3,
    League.NCAA: 53.3,
    League.HS: 53.3,
    League.CFL: 65  # CFL field is wider
}

end_zone_depths = {
    League.NFL: 10,
    League.NCAA: 10,
    League.HS: 10,
    League.CFL: 20  # CFL end zones are deeper
}

# Distances from each sideline (in yards)
hash_mark_distances = {
    League.NFL: 23.7,
    League.NCAA: 20,
    League.HS: 17.8,
    League.CFL: 24
}

hash_mark_colors = {
    League.NFL: (0, 255, 255),
    League.NCAA: (0, 165, 255),
    League.HS: (255, 255, 0),
    League.CFL: (128, 128, 128)  # Gray for CFL
}

# hash_mark_colors = {
#     League.NFL: 'yellow',
#     League.NCAA: 'tab:orange',
#     League.HS: 'cyan',
#     League.CFL: 'tab:green'
# }

# Collect bottom and top edge hash mark coordinates at 5-yard increments (excluding end zones)
bottom_edge_hash_mark_coords = {
    league: [
        [x, 0] for x in range(
            end_zone_depths[league] + 5,
            field_lengths[league] - end_zone_depths[league],
            5
        )
    ]
    for league in League
}

top_edge_hash_mark_coords = {
    league: [
        [x, field_widths[league]] for x in range(
            end_zone_depths[league] + 5,
            field_lengths[league] - end_zone_depths[league],
            5
        )
    ]
    for league in League
}

class EdgeMethod(Enum):
    """Edge detection methods."""
    GRAY_CANNY = "gray-canny"
    GRAY_CANNY_BLUR = "gray-canny-blur"
    HLS_CANNY = "hls-canny"
    HLS_CANNY_BLUR = "hls-canny-blur"
    CANNY = "canny"


class LineMethod(Enum):
    """Line detection methods."""
    HOUGH = "hough"
    HOUGHP = "houghp"

@dataclass(frozen=True)
class ProcessingConfig:
    """Immutable configuration for football field line detection and analysis."""
    edge_method: EdgeMethod = EdgeMethod.HLS_CANNY_BLUR
    line_method: LineMethod = LineMethod.HOUGH

# line-detection-lib
def hls_filter(image):
    hls_image = cv2.cvtColor(image, cv2.COLOR_BGR2HLS)
    h, l, s = cv2.split(hls_image)

    h_min, h_max = 0, 179
    s_min, s_max = 0, 255

    l_lower = int(np.percentile(l, 90))
    l_upper = 225

    lower_white = np.array([h_min, l_lower, s_min])
    upper_white = np.array([h_max, l_upper, s_max])
    white_mask = cv2.inRange(hls_image, lower_white, upper_white)
    result = cv2.bitwise_and(image, image, mask=white_mask)
    return result

def get_edges(image, method):
    kernel = np.ones((3,3), np.float32)/9
    if method == EdgeMethod.GRAY_CANNY.value:
        pass
    elif method == EdgeMethod.GRAY_CANNY_BLUR.value:
        image = cv2.filter2D(image, -1, kernel)
    elif method == EdgeMethod.HLS_CANNY.value:
        image = hls_filter(image)
    elif method == EdgeMethod.HLS_CANNY_BLUR.value:
        image = cv2.filter2D(image, -1, kernel)
        image = hls_filter(image)
    else:
        raise ValueError(f"edge_method = {method} is not supported")
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    return edges

def get_lines(edges, method, edge_method=None):
    if method == LineMethod.HOUGHP.value:
        all_lines = cv2.HoughLinesP(edges, rho=1, theta=np.pi/180,
                               threshold=200 if 'hls' not in edge_method else 100,
                               minLineLength=1,
                               maxLineGap=80)
    elif method == LineMethod.HOUGH.value:
        all_lines = cv2.HoughLines(edges, 1, np.pi/180, 150, None, 0, 0)
        if all_lines is not None:
            result = []
            for i in range(0, len(all_lines)):
                rho = all_lines[i][0][0]
                theta = all_lines[i][0][1]
                a, b = np.cos(theta), np.sin(theta)
                x, y = a*rho, b*rho
                pt1 = (int(x + 1000*(-b)), int(y+1000*(a)))
                pt2 = (int(x - 1000*(-b)), int(y-1000*(a)))
                result.append([[*pt1, *pt2]])
            all_lines = np.array(result)
    else:
        raise ValueError("invalid line method")

    return [] if all_lines is None else all_lines
# line-detection-lib ends here

# comp-geo-lib
def line_convert(lines: np.typing.NDArray, in_fmt: str, out_fmt: str) -> np.typing.NDArray:
    """Converts a Numpy array of lines (N, in_fmt) from in_fmt to out_fmt"""
    if in_fmt == 'xym' and out_fmt == 'abc':
        x, y, m = lines.T
        return np.vstack((m, -1*np.ones_like(m), y - m * x)).T
    elif in_fmt == 'xyxy' and out_fmt == 'abc':
        x1, y1, x2, y2 = lines.T
        return np.vstack((y1-y2, x2-x1, (y2-y1)*x1 - (x2-x1)*y1)).T
    elif in_fmt == 'mb' and out_fmt == 'abc':
        m, b = lines.T
        return line_convert(np.vstack((np.zeros_like(m), b, 1, m+b)).T, 'xyxy', 'abc')
    elif in_fmt == 'mb' and out_fmt == 'xyxy':
        m, b = lines.T
        return np.vstack((np.zeros_like(m), b, 1, m+b)).T
    elif in_fmt == 'xyxy' and out_fmt == 'xym':
        x,y,x2,y2 = lines.T
        return np.vstack((x, y, (y2-y)/(x2-x))).T
    else:
        raise ValueError("conversion from {in_fmt} to {out_fmt} is not supported")

def line_intersects_box(lines: np.typing.NDArray, boxes: np.typing.NDArray, mode:str='any', line_fmt:str='xyxy') -> np.typing.NDArray:
    """Given a line in xym format and box in xywhc, returns a boolean indicating whether the line intersects the box"""
    A, B, C = line_convert(lines, line_fmt, 'abc').T
    C = C[:,None]
    x, y, w, h = boxes[:,:4].T
    x2, y2 = x + w, y + h

    tl = (np.outer(A,x) + np.outer(B,y) + C)
    br = (np.outer(A,x2) + np.outer(B,y2) + C)
    tr = (np.outer(A, x2) + np.outer(B, y) + C)
    bl = (np.outer(A,x) + np.outer(B,y2) + C)
    intersect = ((tl * br) < 0) + ((tr * bl) < 0) # + for or
    if not intersect.any():
        return intersect
    # We have an intersection, what kind?
    if mode == 'any':
        return intersect
    elif mode == 'vertical':
        # left/right points are on the same side of the line, respecitvely
        return ((tl * bl) > 0) * ((tr * br) > 0) * ((tl * tr) < 0) * ((bl * br) < 0)
# comp-geo-lib ends here

# filter-lib
def directional_filter(all_lines, direction, dot_thr=0.99):
    """
    all_lines: np.array of all lines in xyxy
    direction: unit vector in xy
    dot_thr: dot product threshold
    """
    all_units = all_lines[:,2:] - all_lines[:,:2]
    all_units = all_units / np.linalg.norm(all_units, axis=1, keepdims=True)

    ## compute dot product of prototypical unit vector with all unit vectors
    dots = np.abs(np.dot(direction, all_units.T))
    dot_mask = dots > dot_thr

    return dot_mask
# filter-lib ends here

# dedup-lib
def transverse_clustering(lines, transverse=None):
    """
    lines: np.array of lines to cluster in xyxy format
    transverse: np.array of transverse line to use in mb format
    """
    if transverse is None:
        transverse = np.array([[0, 0]])
    if transverse.ndim == 1:
        transverse = transverse[None, :]

    ## compute intersection (cross product in homogeneous coordinates)
    crossed = np.linalg.cross(line_convert(transverse, 'mb', 'abc'), line_convert(lines, 'xyxy', 'abc'))
    crossed /= crossed[:,-1:]

    ## compute transverse unit vector and projections
    transverse_xyxy = line_convert(transverse, 'mb', 'xyxy')
    P0 = transverse_xyxy[0,:2]
    d = transverse_xyxy[0,2:] - P0
    d = d / np.linalg.norm(d)
    t = np.dot((crossed[:,:2] - P0), d.T)

    ## cluster projections
    clustering = DBSCAN(eps=0.05, min_samples=1).fit(t.reshape(-1,1)/t.max())

    clustered = np.hstack((crossed[:, :2], clustering.labels_.reshape(-1,1)))

    ## compute prototypical line for each cluster
    proto_lines = []
    for g in np.unique(clustered[:,-1]):
        if g == -1: continue
        group = lines[clustered[:,-1] == g]
        group_xym = line_convert(group, 'xyxy', 'xym')
        m = np.median(group_xym[:,-1])
        xy = clustered[clustered[:,-1] == g][:,:2].mean(axis=0)
        proto_lines.append([*xy, m])
    proto_lines = np.array(proto_lines)

    return clustered, proto_lines

def transverse_gap_fill(proto_lines, transverse, ratio_thr=2):
    transverse_xyxy = line_convert(transverse, 'mb', 'xyxy')
    P0 = transverse_xyxy[0,:2]
    d = transverse_xyxy[0,2:] - P0
    d = d / np.linalg.norm(d)

    proto_dots = np.dot(proto_lines[:,:2] - P0, d.T)
    order = np.argsort(proto_dots)

    proto_dots = proto_dots[order]
    proto_lines = proto_lines[order]

    ratio = (np.diff(proto_dots).max() / np.diff(proto_dots))
    if ratio.max() > ratio_thr:
        assert (ratio == 1).sum() == 1, 'filling multiple gaps is not supported'
        gap_idx = np.argmax(ratio == 1) + 1
        P = P0 + proto_dots[gap_idx-1:gap_idx+1].mean() * d
        # if straddling 50-yd, mean won't work because of the singularity
        m = proto_lines[gap_idx-1:gap_idx+1, -1].mean() if proto_lines[gap_idx-1, -1] * proto_lines[gap_idx, -1] > 0 else -1/1e-2
        proto_lines = np.insert(proto_lines, gap_idx, [*P, m], axis=0)

    return proto_lines
# dedup-lib ends here

# associate-lib
def associate_line_to_yard(proto_lines, yard_boxes, yard_labels):
    line_yard_intersect = line_intersects_box(proto_lines, yard_boxes, line_fmt='xym')
    line_yard_imap = np.stack(np.nonzero(line_yard_intersect), axis=1)

    line_yard_map = np.hstack((line_yard_imap, yard_labels[line_yard_imap[:,1]].reshape(-1,1).astype(int)))
    line_yard_map = np.unique(line_yard_map[:,[0,2]], axis=0)
    if not line_yard_map.shape[0]:
        # no yard lines intersected, return empty map
        return line_yard_map, line_yard_imap

    # create map for all proto lines, with -1 for ones without a box
    tmp_line_yard_map = np.hstack((np.arange(proto_lines.shape[0]).reshape(-1,1), -1*np.ones((proto_lines.shape[0],1))))
    tmp_line_yard_map[line_yard_map[:,0], 1] = line_yard_map[:,1]
    tmp_line_yard_map[tmp_line_yard_map[:,-1]==-1, 1] = np.interp(tmp_line_yard_map[tmp_line_yard_map[:,-1]==-1, 0], tmp_line_yard_map[tmp_line_yard_map[:,-1]!=-1, 0], tmp_line_yard_map[tmp_line_yard_map[:,-1]!=-1,1], left=-1, right=-1)

    # line_yard_map = np.column_stack((line_yard_map, gaps, np.interp(gaps, *line_yard_map.T, right=-1, left=-1))).reshape(-1,2)
    line_yard_map = tmp_line_yard_map[tmp_line_yard_map[:,-1] != -1]

    # get rid of peak at 50, just go from 0 = left goal line -> 100 = right goal line
    diffs = np.diff(line_yard_map[:,1])
    if not len(diffs):
        # only one known yard line in view...
        pass
    elif (np.max(diffs) > 0) == 0:
        # right side of field
        line_yard_map[:,1] = 100 - line_yard_map[:,1]
    else:
        # straddling 50 or left side
        line_yard_map[:,1] = line_yard_map[0,1] + np.cumsum([0,*np.abs(diffs)]) * (2*np.max(diffs > 0) - 1)

    return line_yard_map, line_yard_imap

def associate_hash_to_yard(proto_lines, line_yard_dict, inner_boxes, up_edge_boxes):
    line_inner_intersect = line_intersects_box(proto_lines, inner_boxes, line_fmt='xym')
    line_inner_imap = np.stack(np.nonzero(line_inner_intersect), axis=1)

    inner_yard_map = np.stack((line_inner_imap[:, 1], [line_yard_dict.get(k, -1) for k in line_inner_imap[:,0]]), axis=1)
    inner_yard_map = inner_yard_map[inner_yard_map[:,-1] != -1]

    if len(up_edge_boxes):
        line_up_edge_intersect = line_intersects_box(proto_lines, up_edge_boxes, line_fmt='xym')
        line_up_edge_imap = np.stack(np.nonzero(line_up_edge_intersect), axis=1)

        up_edge_yard_map = np.stack((line_up_edge_imap[:, 1], [line_yard_dict.get(k, -1) for k in line_up_edge_imap[:,0]]), axis=1)
        up_edge_yard_map = up_edge_yard_map[up_edge_yard_map[:,-1] != -1]
    else:
        up_edge_yard_map = np.empty(shape=(0,2))

    return inner_yard_map, up_edge_yard_map
# associate-lib ends here

def detect_field_features(
        image: np.ndarray,
        config: ProcessingConfig
):
    """Detects field features (lines) in a given image using specified processing configuration.

    Args:
        image (np.ndarray): The input image as a NumPy array.
        config (ProcessingConfig): Configuration object specifying edge and line detection methods.

    Returns:
        np.ndarray: An array of detected lines, where each line is represented by its endpoints.
    """
    edges = get_edges(image, config.edge_method.value)
    all_lines = get_lines(edges, config.line_method.value)
    all_lines = np.array([l[0] for l in all_lines])
    all_lines = all_lines[all_lines[:,0] != all_lines[:,2]]

    return all_lines

def extract_yard_lines(
        all_lines: np.ndarray,
        yard_boxes: np.ndarray,
        inner_boxes: np.ndarray,
        directional_threshold: float = 0.995
) -> Tuple[np.ndarray, np.ndarray]:
    # filter lines
    # find lines that intersect yard boxes only through bottom and top edges
    yard_mask = line_intersects_box(all_lines, yard_boxes, mode='vertical').any(axis=1)
    yard_lines = all_lines[yard_mask]
    
    # compute directional vectors of the yard lines
    unit = yard_lines[:,2:] - yard_lines[:,:2]
    unit = unit / np.linalg.norm(unit, axis=1, keepdims=True)
    
    # compute the slopes, for use in directional filtering
    slopes = unit[:,1]/unit[:,0]
    
    mask = np.ones((all_lines.shape[0])).astype(bool)
    for slope_mask in [slopes >= 0, slopes < 0]:
        if slope_mask.sum() == 0:
            # we don't have any vectors, so just skip it
            continue
    
        _unit = unit[slope_mask]
    
        # compute prototypical angle and unit vector
        proto_angle = np.mean(np.arctan(_unit[:,1]/_unit[:,0]))
        proto_unit = np.array([np.cos(proto_angle), np.sin(proto_angle)])
    
        # keep if directionally ok
        mask &= directional_filter(all_lines, proto_unit, directional_threshold)

    inner_mask = line_intersects_box(all_lines, inner_boxes, mode='vertical').any(axis=1)
    # also keep lines which intersect "inner" hash marks
    mask |= (yard_mask & inner_mask) | inner_mask
    
    yard_lines = all_lines[mask]

    return yard_lines, mask

def deduplicate_lines(yard_lines: np.ndarray, inner_boxes: np.ndarray) -> np.ndarray:
    # deduplicate
    # compute linear regression of inner boxes
    # for use as transverse line for distance grouping
    inner_xywh = inner_boxes[:,:4]
    inner_xcyc = inner_xywh[:,:2] + inner_xywh[:,2:]/2
    A = np.hstack((inner_xcyc[:,:1], np.ones((inner_xcyc.shape[0], 1))))
    lstsq = np.linalg.lstsq(A, inner_xcyc[:,1:], rcond=None)[0]
    inner_abc = line_convert(np.array([lstsq.T]), 'mb', 'abc')

    # while we're at it, let's classify the inner hash marks into upper/lower
    upper = np.dot(inner_abc, np.hstack((inner_xywh[:,:2], np.ones_like(inner_xywh[:,:1]))).T) < 0
    inner_to_upper = dict(np.hstack((np.arange(upper.shape[1])[:,None], upper.T)).astype(int))
    
    transverse = np.array([lstsq.T])
    clustered, proto_lines = transverse_clustering(yard_lines, transverse)
    proto_lines = transverse_gap_fill(proto_lines, transverse)

    return proto_lines, clustered, inner_to_upper

class LineAssociationError(Exception):
    def __init__(
            self, 
            message: str, 
            all_lines: Optional[np.ndarray] = None,
            yard_lines: Optional[np.ndarray] = None,
            proto_lines: Optional[np.ndarray] = None,
            clustered: Optional[np.ndarray] = None,
            inner_to_upper: Optional[Dict[int, int]] = None,
            line_yard_map: Optional[np.ndarray] = None,
    ):
        super().__init__(message, message)
        self.message = message
        self.all_lines = all_lines
        self.yard_lines = yard_lines
        self.proto_lines = proto_lines
        self.clustered = clustered
        self.inner_to_upper = inner_to_upper
        self.line_yard_map = line_yard_map

class LineLabelConflictError(LineAssociationError):
    pass

class LineLabelDuplicateError(LineAssociationError):
    pass

class CorrespondenceError(Exception):
    def __init__(
            self, 
            message: str, 
            all_lines: Optional[np.ndarray] = None,
            yard_lines: Optional[np.ndarray] = None,
            proto_lines: Optional[np.ndarray] = None,
            clustered: Optional[np.ndarray] = None,
            inner_to_upper: Optional[Dict[int, int]] = None,
            line_yard_map: Optional[np.ndarray] = None,
            inner_yard_map: Optional[Dict[int, int]] = None,
            up_edge_yard_map: Optional[Dict[int, int]] = None
    ):
        super().__init__(message, message)
        self.message = message
        self.all_lines = all_lines
        self.yard_lines = yard_lines
        self.proto_lines = proto_lines
        self.clustered = clustered
        self.inner_to_upper = inner_to_upper
        self.line_yard_map = line_yard_map
        self.inner_yard_map = inner_yard_map
        self.up_edge_yard_map = up_edge_yard_map

def extract_correspondence_points(
    inner_boxes: np.ndarray,
    up_edge_boxes: np.ndarray,
    inner_yard_map: Dict[int, int],
    up_edge_yard_map: Dict[int, int], 
    inner_to_upper: Dict[int, bool],
    league: League
) -> Tuple[np.ndarray, np.ndarray]:
    image_points = []
    field_points = []
    
    # Add yard line intersections with hash marks
    for inner_idx, yard_num in inner_yard_map.items():
        if inner_idx < len(inner_boxes):
            # Get center of inner hash mark bounding box
            bbox = inner_boxes[inner_idx.astype(int)]
            center_x = bbox[0] + bbox[2] / 2
            center_y = bbox[1] + bbox[3] / 2
            image_points.append([center_x, center_y])
            
            # Find corresponding field coordinate using league-specific hash mark distance
            hash_distance = hash_mark_distances[league]
            field_y = hash_distance if inner_to_upper.get(inner_idx, False) else (field_widths[league] - hash_distance)
            field_points.append([yard_num+end_zone_depths[league], field_y])
    
    # Add upper edge hash marks
    for up_idx, yard_num in up_edge_yard_map.items():
        if up_idx < len(up_edge_boxes):
            bbox = up_edge_boxes[up_idx.astype(int)]
            center_x = bbox[0] + bbox[2] / 2
            center_y = bbox[1] + bbox[3] / 2
            image_points.append([center_x, center_y])
            
            # Upper edge is at field boundary
            field_points.append([yard_num+end_zone_depths[league], 0])

    if len(image_points) < 4:
        raise ValueError(
            f"Not enough correspondence points found: {len(image_points)} < 4"
        )
    
    return np.array(image_points, dtype=np.float32), np.array(field_points, dtype=np.float32)

class HomographyResult(NamedTuple):
    """Result from homography computation."""
    matrix: np.ndarray
    image_points: np.ndarray
    field_points: np.ndarray

class HomographyError(Exception):
    pass

def compute_homography(
    image_points: np.ndarray,
    field_points: np.ndarray,
    method: int = cv2.RANSAC
) -> HomographyResult:
    """
    Compute homography matrix from correspondence points.
    
    Pure function - returns everything needed, no hidden state.
    
    Parameters
    ----------
    image_points : np.ndarray
        Nx2 array of image coordinates
    field_points : np.ndarray
        Nx2 array of field coordinates
    method : int
        OpenCV method for homography computation
        
    Returns
    -------
    result : HomographyResult
        Homography result containing matrix and correspondence points
        
    Raises
    ------
    InsufficientDataError
        If fewer than 4 correspondence points are provided
    ComputationError
        If OpenCV fails to compute the homography matrix
    """
    if len(image_points) < 4 or len(field_points) < 4:
        raise ValueError(
            f"At least 4 point correspondences required, got {len(image_points)}, {len(field_points)}"
        )

    H, mask = cv2.findHomography(
        image_points, field_points,
        method=method,
        ransacReprojThreshold=5.0
    )

    if H is None:
        raise HomographyError("OpenCV failed to compute homography matrix")
    
    return HomographyResult(
        matrix=H,
        image_points=image_points,
        field_points=field_points,
    )

def conflict_dfs(
        proto_lines: np.ndarray, 
        boxes: np.ndarray, 
        labels: np.ndarray, 
        path: tuple, 
        visited: set, 
        out: list
    ):
    """Backtracking DFS to find all consistent associations of boxes to proto lines.

    Args:
        proto_lines (np.ndarray): The proto lines to associate with boxes.
        boxes (np.ndarray): The boxes to associate with proto lines.
        labels (np.ndarray): The labels for the boxes.
        path (tuple): The current path of removed box indices being considered.
        visited (set): A set of visited paths to avoid cycles.
        out (list): A list to collect all valid mappings found.
    """
    if path in visited:
        return
    visited.add(path)

    line_yard_map, line_yard_imap = associate_line_to_yard(proto_lines, boxes, labels)

    # Check if line_yard_map is monotonic in either column (0 or 1)
    column_0_mono = (np.all(np.diff(line_yard_map[:, 0]) >= 0) or np.all(np.diff(line_yard_map[:, 0]) <= 0))
    column_1_mono = (np.all(np.diff(line_yard_map[:, 1]) >= 0) or np.all(np.diff(line_yard_map[:, 1]) <= 0))
    
    if len(line_yard_map) <= 1:
        return
    elif len(np.unique(line_yard_map[:, 0])) != line_yard_map.shape[0]:
        # there are conflicts, we need to drop boxes
        vals, index, counts = np.unique(line_yard_map[:, 0], return_counts=True, return_index=True)

        problem_indices = line_yard_imap[np.isin(line_yard_imap[:, 0], vals[counts > 1]), :]
        # remove one box from each problem line at a time
        problem_paths = itertools.product(*[
            problem_indices[problem_indices[:, 0] == l, 1].astype(int).tolist()
            for l in np.unique(problem_indices[:, 0])
        ])
        for p in problem_paths:
            # Drop a conflicting box
            new_boxes = np.delete(boxes, p, axis=0)
            new_labels = np.delete(labels, p, axis=0)
            conflict_dfs(proto_lines, new_boxes, new_labels, tuple(path + p), visited, out=out)
    elif len(np.unique(line_yard_map[:, 1])) != line_yard_map.shape[0]:
        # there are conflicts (multiple lines with same label), we need to drop boxes
        vals, index, counts = np.unique(line_yard_map[:, 1], return_counts=True, return_index=True)

        problem_indices = line_yard_map[np.isin(line_yard_map[:, 1], vals[counts > 1]), 0]
        problem_indices = line_yard_imap[np.isin(line_yard_imap[:, 0], problem_indices), :]
        # for each unique line, drop all boxes for that line
        problem_paths = [
            tuple(problem_indices[problem_indices[:, 0] == l, 1].astype(int).tolist())
            for l in np.unique(problem_indices[:, 0])
        ]
        for p in problem_paths:
            # Drop a conflicting box
            new_boxes = np.delete(boxes, p, axis=0)
            new_labels = np.delete(labels, p, axis=0)
            conflict_dfs(proto_lines, new_boxes, new_labels, tuple(path + p), visited, out=out)
    elif not (column_0_mono and column_1_mono):
        return
    # check for yard difference of 5 yards
    # this likely means a line that is misclassified but only has one box
    # TODO: we need to drop such a box
    # elif len(line_yard_map) > 1 and np.abs(np.diff(line_yard_map[:, 1]).max()) > 5:
    #     return
    else:
        # No conflicts, we can return the mapping
        out.append((line_yard_map, line_yard_imap, boxes))

class ProcessingResult(NamedTuple):
    """NamedTuple for processing results."""
    all_lines: np.ndarray
    yard_lines: np.ndarray
    proto_lines: np.ndarray
    clustered: np.ndarray
    inner_to_upper: Dict[int, int]
    line_yard_map: np.ndarray
    line_yard_imap: np.ndarray
    line_yard_boxes: np.ndarray
    inner_yard_map: Dict[int, int]
    up_edge_yard_map: Dict[int, int]
    homography: HomographyResult
    warnings: List[CorrespondenceError]

def process_image(
        image: np.ndarray, 
        league: League, 
        yard_boxes: np.ndarray,
        yard_labels: np.ndarray,
        inner_boxes: np.ndarray,
        up_edge_boxes: np.ndarray,
        config: ProcessingConfig = ProcessingConfig()
) -> ProcessingResult:
    # Step 1: Detect field features
    all_lines = detect_field_features(image, config)

    if len(all_lines) == 0:
        raise ValueError("No lines detected in the image. Please check the image quality or configuration.")

    # Step 2: Extract yard lines
    yard_lines, mask = extract_yard_lines(all_lines, yard_boxes, inner_boxes)

    # Step 3: Deduplicate lines
    proto_lines, clustered, inner_to_upper = deduplicate_lines(yard_lines, inner_boxes)

    # possible association issues and fixes
    # 1. Inconsistent yard line label: multiple numbers assigned to same line
    ## loop over all conflicts, dropping a conflicting box each time, minimize backprojection error
    ## or just take the most confident line for conflicted lines
    # 2. Inconsistent yard line label: multiple lines assigned to same number
    ## loop over all conflicts, dropping a conflicting line each time, minimize backprojection error
    ## or just take the most confident line for duplicated lines
    # we use a backtracking DFS to find all consistent associations of boxes to proto lines
    candidate_associations = []
    conflict_dfs(
        proto_lines, 
        yard_boxes, 
        yard_labels, 
        path=tuple(), 
        visited=set(), 
        out=candidate_associations
    )

    best_line_yard_map = None
    best_line_yard_imap = None
    best_line_yard_boxes = None
    best_inner_yard_map = None
    best_up_edge_yard_map = None
    best_homography_result = None
    best_backprojection_error = float('inf')
    best_warnings = []
    for line_yard_map, line_yard_imap, boxes in candidate_associations:
        warnings = []
        inner_yard_map, up_edge_yard_map = associate_hash_to_yard(proto_lines, dict(line_yard_map), inner_boxes, up_edge_boxes)
        inner_yard_map = dict(inner_yard_map)
        up_edge_yard_map = dict(up_edge_yard_map)

        try:
            image_points, field_points = extract_correspondence_points(
                inner_boxes, up_edge_boxes, inner_yard_map, up_edge_yard_map, inner_to_upper, league
            )
        except ValueError as e:
            # caught, but we have other candidate associations to try
            warnings.append(CorrespondenceError(
                f"Failed to extract correspondence points: {str(e)}",
                all_lines=all_lines,
                yard_lines=yard_lines,
                proto_lines=proto_lines,
                clustered=clustered,
                inner_to_upper=inner_to_upper,
                line_yard_map=line_yard_map,
                inner_yard_map=inner_yard_map,
                up_edge_yard_map=up_edge_yard_map,
            ))
        
        try:
            homography_result = compute_homography(image_points, field_points)
        except ValueError as e:
            # caught, but we have other candidate associations to try
            warnings.append(CorrespondenceError(
                f"Insufficient correspondence points for homography computation: {str(e)}",
                all_lines=all_lines,
                yard_lines=yard_lines,
                proto_lines=proto_lines,
                clustered=clustered,
                inner_to_upper=inner_to_upper,
                line_yard_map=line_yard_map,
                inner_yard_map=inner_yard_map,
                up_edge_yard_map=up_edge_yard_map,
            ))
        
        backproj = transform_points(
            homography_result.field_points,
            homography_result.matrix,
            inverse=True
        )
        mse = np.mean(np.square(homography_result.image_points - backproj))
        if mse < best_backprojection_error:
            best_line_yard_map = line_yard_map
            best_line_yard_imap = line_yard_imap
            best_line_yard_boxes = boxes
            best_inner_yard_map = inner_yard_map
            best_up_edge_yard_map = up_edge_yard_map
            best_backprojection_error = mse
            best_homography_result = homography_result
            best_warnings = warnings

    return ProcessingResult(
        all_lines=all_lines,
        yard_lines=yard_lines,
        proto_lines=proto_lines,
        clustered=clustered,
        inner_to_upper=inner_to_upper,
        line_yard_map=best_line_yard_map,
        line_yard_imap=best_line_yard_imap,
        line_yard_boxes=best_line_yard_boxes,
        inner_yard_map=best_inner_yard_map,
        up_edge_yard_map=best_up_edge_yard_map,
        homography=best_homography_result or HomographyResult(
            matrix=None,
            field_points=None,
            image_points=None
        ),
        warnings=best_warnings
    )

def transform_points(
    points: np.ndarray,
    homography_matrix: np.ndarray,
    inverse: bool = False
) -> np.ndarray:
    """
    Transform points using a homography matrix.
    
    Pure function - explicitly requires the homography matrix.
    
    Parameters
    ----------
    points : np.ndarray
        Nx2 array of points to transform
    homography_matrix : np.ndarray
        3x3 homography matrix
    inverse : bool
        If True, transform from field to image coordinates.
        If False, transform from image to field coordinates.
        
    Returns
    -------
    transformed_points : np.ndarray
        Nx2 array of transformed points
    """
    points = np.array(points, dtype=np.float32)
    if points.ndim == 1:
        points = points.reshape(1, -1)
    
    H = np.linalg.inv(homography_matrix) if inverse else homography_matrix
    
    transformed = cv2.perspectiveTransform(points.reshape(-1, 1, 2), H)
    return transformed.reshape(-1, 2)

def draw_proto_lines(
    detected_img: np.ndarray,
    proto_lines: np.ndarray,
    line_yard_map: Optional[np.ndarray] = None,
):
    for idx, (x, y, m) in enumerate(proto_lines):
        unit = np.array([1, m])
        unit = unit / np.linalg.norm(unit)
        xy = np.array([x, y])
        pt1 = (xy - x * unit).astype(int)
        pt2 = (xy + (detected_img.shape[1] - x) * unit).astype(int)
        cv2.line(detected_img, tuple(pt1), tuple(pt2), (255, 255, 0), 3)

        # Label the line with the inferred yard number if available
        if line_yard_map is None or line_yard_map.shape[0] == 0:
            continue
        yard_label = None
        matches = line_yard_map[line_yard_map[:, 0] == idx, 1]
        if len(matches) > 0:
            yard_label = matches[0]
            mid_pt = tuple(xy.astype(int))
            cv2.putText(detected_img, f'{yard_label}', mid_pt, cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

def draw_yard_boxes(
        detected_img: np.ndarray, 
        yard_boxes: np.ndarray, 
        yard_labels: Optional[np.ndarray] = None, 
        color: Optional[Tuple[int, int, int]] = (0, 255, 255)
    ):
    if yard_labels is None:
        yard_labels = [None] * yard_boxes.shape[0]

    for (x,y,w,h,score),lbl in zip(yard_boxes, yard_labels):
        cv2.rectangle(detected_img, (int(x), int(y)), (int(x+w), int(y+h)), color, 2)
        if lbl is not None:
            cv2.putText(detected_img, f'{lbl} {str(int(score*100))}', (int(x), int(y-10)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)

def draw_inner_boxes(detected_img: np.ndarray, inner_boxes: np.ndarray, inner_to_upper: Dict[int, int]):
    for i, (x,y,w,h,score) in enumerate(inner_boxes):
        color = (255,0,0) if inner_to_upper[i] else (255,0,255)
        cv2.rectangle(detected_img, (int(x), int(y)), (int(x+w), int(y+h)), color, 2)
        cv2.putText(detected_img, 'inner', (int(x), int(y-10)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

def draw_up_edge_boxes(detected_img: np.ndarray, up_edge_boxes: np.ndarray):
    for (x,y,w,h,score) in up_edge_boxes:
        cv2.rectangle(detected_img, (int(x), int(y)), (int(x+w), int(y+h)), (0, 0, 255), 2)
        cv2.putText(detected_img, 'up_edge', (int(x), int(y-10)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 255), 1)

def field_to_pixel(x, y, field_img, league):
    h, w = field_img.shape[:2]
    scale_x, scale_y = w / field_lengths[league], h / field_widths[league]
    scale = min(scale_x, scale_y)

    field_origin = np.array([(w - field_lengths[league] * scale) // 2, (h - field_widths[league] * scale) // 2])
    return (field_origin + np.array([x, y]) * scale).astype(int)

def gen_field(h, w, league, exclude_hash_marks: bool = False) -> np.ndarray:
    field_img = np.zeros((h, w, 3), dtype=np.uint8)
    field_img.fill(34)
    
    # Draw field outline
    field_corners = [(0, 0), (field_lengths[league], 0), (field_lengths[league], field_widths[league]), (0, field_widths[league])]
    field_corners_px = [field_to_pixel(x, y, field_img, league) for x, y in field_corners]
    cv2.polylines(field_img, [np.array(field_corners_px)], True, (255, 255, 255), 2)

    # Draw yard lines every 10 yards
    for x in range(end_zone_depths[league], field_lengths[league] - end_zone_depths[league] + 1, 10):
        p1 = field_to_pixel(x, 0, field_img, league)
        p2 = field_to_pixel(x, field_widths[league], field_img, league)
        cv2.line(field_img, p1, p2, (255, 255, 255), 1)

        # Add yard numbers
        if end_zone_depths[league] < x < field_lengths[league] - end_zone_depths[league]:
            yard_num = min(x - end_zone_depths[league], field_lengths[league] - end_zone_depths[league] - x)  # Distance from nearest goal line
            cv2.putText(field_img, str(yard_num), 
                    field_to_pixel(x - 2, field_widths[league] / 2, field_img, league), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
            
    if exclude_hash_marks:
        return field_img
    
    # Draw hash marks for each league with corresponding color
    for league_enum, hash_dist in hash_mark_distances.items():
        color = hash_mark_colors[league_enum]

        # Bottom edge hash marks
        for x, _ in bottom_edge_hash_mark_coords[league]:
            px, py = field_to_pixel(x, hash_dist, field_img, league)
            cv2.circle(field_img, (px, py), 3, color, -1)

        # Top edge hash marks
        for x, _ in top_edge_hash_mark_coords[league]:
            px, py = field_to_pixel(x, field_widths[league] - hash_dist, field_img, league)
            cv2.circle(field_img, (px, py), 3, color, -1)
            
    return field_img

def main(image_path: str,
         league: League,
         clarifai_model_url: str,
         output_dir: str,
         verbose: bool = False,
         config: ProcessingConfig = ProcessingConfig(),
         burn_metrics: bool = False):
    print(f"Processing: {image_path}")

    print(f"Using remote detector at {clarifai_model_url}")
    model = Model(url=clarifai_model_url)
    with open(image_path, 'rb') as img_file:
        img_bytes = img_file.read()
    response = model.predict(image=Image(bytes=img_bytes), relative=False)

    yard_boxes, yard_labels, inner_boxes, up_edge_boxes = [], [], [], []
    for region in response:
        cls = region.concepts[0].name
        box = region.box
        score = region.concepts[0].value
        if cls in ('10', '20', '30','40', '50'):
            yard_boxes.append([box[0], box[1], box[2]-box[0], box[3]-box[1], score])
            yard_labels.append(int(cls))
        elif cls == 'inner':
            inner_boxes.append([box[0], box[1], box[2]-box[0], box[3]-box[1], score])
        elif cls == 'up_edge':
            up_edge_boxes.append([box[0], box[1], box[2]-box[0], box[3]-box[1], score])
        
    image_base = os.path.basename(os.path.splitext(image_path)[0])
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Could not read image from {image_path}")
    
    detected_img = img.copy()
    hom_img = img.copy()
    
    h, w = hom_img.shape[:2]
    field_img = gen_field(h, w, league)
    try:
        if not len(yard_boxes):
            raise ValueError("No yard lines detected in the image. Please check the image quality or configuration.")
        if not len(inner_boxes):
            raise ValueError("No inner hash marks detected in the image. Please check the image quality or configuration.")
        result = process_image(
            img,
            league=league,
            yard_boxes=np.array(yard_boxes, dtype=np.float32),
            yard_labels=np.array(yard_labels, dtype=np.int32),
            inner_boxes=np.array(inner_boxes, dtype=np.float32),
            up_edge_boxes=np.array(up_edge_boxes, dtype=np.float32),
            config=config
        )
        homography_result = result.homography
        warnings = result.warnings

        draw_proto_lines(detected_img, result.proto_lines, result.line_yard_map)
        draw_yard_boxes(detected_img, yard_boxes, yard_labels, color=(0, 255, 255))
        if result.line_yard_boxes is not None and result.line_yard_boxes.shape[0] > 0:
            draw_yard_boxes(detected_img, result.line_yard_boxes, color=(255, 255, 0))
        draw_inner_boxes(detected_img, inner_boxes, result.inner_to_upper)
        draw_up_edge_boxes(detected_img, up_edge_boxes)

        if homography_result.matrix is None:
            raise HomographyError("Failed to compute homography matrix. Not enough correspondence points or invalid data.")

        backproj = transform_points(
            homography_result.field_points,
            homography_result.matrix,
            inverse=True
        )
        se = np.square(homography_result.image_points - backproj)
        mse = np.mean(se)

        # compute condition number of the homography matrix
        # if the condition number is too high, it indicates numerical instability
        # and the homography may not be reliable (TODO)
        cond = np.linalg.cond(homography_result.matrix)
        if cond > 1e12:
            # warnings.append(HomographyError(
            #     f"Homography matrix condition number is too high: {cond}",
            #     all_lines=result.all_lines,
            #     yard_lines=result.yard_lines,
            #     proto_lines=result.proto_lines,
            #     clustered=result.clustered,
            #     inner_to_upper=result.inner_to_upper,
            #     line_yard_map=result.line_yard_map,
            #     inner_yard_map=result.inner_yard_map,
            #     up_edge_yard_map=result.up_edge_yard_map
            # ))
            print(f"Warning: Homography matrix condition number is too high: {cond}")

        print(mse, len(warnings))

        with open(os.path.join(output_dir, 'homography', f"{image_base}_homography.json"), 'w') as f:
            json.dump({
                'matrix': homography_result.matrix.tolist(),
                'image_points': homography_result.image_points.tolist(),
                'field_points': homography_result.field_points.tolist(),
                'squared_backprojection_errors': se.tolist(),
                'mse': float(mse),
                'warnings': [str(w) for w in warnings]
            }, f, indent=4)

        for i, pt in enumerate(homography_result.image_points):
            px, py = tuple(pt.astype(int))
            cv2.circle(hom_img, (px, py), 5, (0, 0, 255), -1)
            cv2.putText(hom_img, f'{i}', 
                        (px + 5, py), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)

        for i, pt in enumerate(homography_result.field_points):
            px, py = field_to_pixel(pt[0], pt[1], field_img, league)
            cv2.circle(field_img, (px, py), 5, (0, 0, 255), -1)
            cv2.putText(field_img, f'{i}', 
                        (px + 5, py), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)

        for i, pt in enumerate(transform_points(homography_result.image_points, homography_result.matrix)):
            px, py = field_to_pixel(pt[0], pt[1], field_img, league)
            cv2.circle(field_img, (px, py), 5, (0, 255, 0), -1)
            cv2.putText(field_img, f'{i}', 
                        (px + 5, py), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)

        # TODO: check if field of view is convex
        fov_pts = [field_to_pixel(*x, field_img, league) for x in transform_points([(0, 0), (w, 0), (w, h), (0, h)], homography_result.matrix)]
        # Check if fov_pts forms a convex polygon
        def is_convex_polygon(pts):
            pts = np.array(pts)
            n = len(pts)
            if n < 4:
                return True  # triangles are always convex
            sign = None
            for i in range(n):
                dx1 = pts[(i+1)%n][0] - pts[i][0]
                dy1 = pts[(i+1)%n][1] - pts[i][1]
                dx2 = pts[(i+2)%n][0] - pts[(i+1)%n][0]
                dy2 = pts[(i+2)%n][1] - pts[(i+1)%n][1]
                zcross = dx1 * dy2 - dy1 * dx2
                if zcross != 0:
                    if sign is None:
                        sign = np.sign(zcross)
                    elif np.sign(zcross) != sign:
                        return False
            return True

        is_convex = is_convex_polygon(fov_pts)
        if not is_convex:
            raise ValueError("Field of view is not convex")
        cv2.polylines(field_img, [np.array(fov_pts)], True, (0, 255, 0), 1)

        if burn_metrics:
            singular_values = np.linalg.svd(homography_result.matrix, compute_uv=False)
            cv2.putText(field_img, f'MSE: {mse:.2f}, Cond: {cond:.2f}, S[0]/S[1]: {singular_values[0] / singular_values[1]:.2f}', (10, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 1)
            cv2.putText(field_img, f'Warn: {[type(w).__name__ for w in warnings]}', (10, 55),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 1)
    except ValueError as e:
        print(f"ValueError processing image: {e}")
        traceback.print_exc()
    except LineAssociationError as e:
        print(f"AssociationError processing image: {e}")
        draw_proto_lines(detected_img, result.proto_lines, result.line_yard_map)
        draw_yard_boxes(detected_img, yard_boxes, yard_labels, color=(255, 255, 0))
        draw_inner_boxes(detected_img, inner_boxes, e.inner_to_upper)
        draw_up_edge_boxes(detected_img, up_edge_boxes)
        cv2.putText(detected_img, f'Error: {type(e).name}', (10, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
    except CorrespondenceError as e:
        print(f"CorrespondenceError extracting correspondence points: {e}")
        draw_proto_lines(detected_img, result.proto_lines, result.line_yard_map)
        draw_yard_boxes(detected_img, yard_boxes, yard_labels, color=(255, 255, 0))
        draw_inner_boxes(detected_img, inner_boxes, e.inner_to_upper)
        draw_up_edge_boxes(detected_img, up_edge_boxes)
        cv2.putText(detected_img, f'Error: {type(e).name}', (10, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
    except HomographyError as e:
        print(f"Error computing homography: {e}")
    finally:
        if verbose:
            print(f"Warnings: {warnings}")

        cv2.imwrite(os.path.join(output_dir, 'detected', f"{image_base}_detected.jpg"), detected_img)
        combined = cv2.hconcat([hom_img, field_img])
        cv2.imwrite(os.path.join(output_dir, 'visualization', f"{image_base}_homography.jpg"), combined)

if __name__ == "__main__":
    import argparse
    from clarifai.client import Model
    from clarifai.runners.utils.data_types import Image

    parser = argparse.ArgumentParser(description='Functional homography computation for football field images')
    parser.add_argument('image_path', help='Path to input image')
    parser.add_argument('--output_dir', default=None,
                       help='Output directory for visualizations')
    parser.add_argument('--league', default='NFL', choices=League.__members__.values(), type=League,
                       help='Football league (affects hash mark positioning)')
    parser.add_argument('--edge_method', default='hls-canny-blur', choices=EdgeMethod.__members__.keys(),
                       help='Edge detection method')
    parser.add_argument('--line_method', default='hough', choices=LineMethod.__members__.keys(),
                       help='Line detection method')
    parser.add_argument('--clarifai_model_url', default=None,
                   help='URL of remote detector service for yard/hash boxes (overrides local JSONs)')
    parser.add_argument('--verbose', action='store_true',
                       help='Enable verbose output')
    parser.add_argument('--burn_metrics', action='store_true',
                       help='Burn metrics into output images (for debugging)')
    
    args = parser.parse_args()

    # Set up output directory
    output_dir = args.output_dir or os.path.dirname(args.image_path)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    for x in ['detected', 'homography', 'visualization']:
        os.makedirs(os.path.join(output_dir, x), exist_ok=True)
        
    # Create configuration
    config = ProcessingConfig(
        edge_method=EdgeMethod(args.edge_method),
        line_method=LineMethod(args.line_method)
    )

    if os.path.isfile(args.image_path):
        # Process a single image
        main(args.image_path,
             args.league,
             args.clarifai_model_url,
             output_dir,
             verbose=args.verbose,
             config=config,
             burn_metrics=args.burn_metrics)
    elif os.path.isdir(args.image_path):
        # Process all images in a directory
        for image_file in sorted(os.listdir(args.image_path)):
            if image_file.lower().endswith(('.png', '.jpg', '.jpeg')):
                full_image_path = os.path.join(args.image_path, image_file)
                try:
                    main(full_image_path,
                        args.league,
                        args.clarifai_model_url,
                        output_dir,
                        verbose=args.verbose,
                        config=config,
                        burn_metrics=args.burn_metrics)
                except Exception as e:
                    # log but continue processing other images
                    print(f"Error processing {full_image_path}: {e}")
