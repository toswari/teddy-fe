from itertools import product
from math import floor, pi
from typing import Iterable, Optional, Tuple

import cv2
import numpy as np

from hough import hough_lines_with_votes


__all__ = ['find_yard_lines', 'Lines', 'WarpError']


class WarpError(Exception):
    pass


class Lines:
    '''
    This class wraps a set of lines on the field.
    '''
    def __init__(self, xyxyvs: np.ndarray, image_width: int,
                 image_height: int):
        '''
        Args:

        xyxyvs (:class:`numpy.ndarray`): An array with shape (N, 5) containing
        the actual lines. The columns of the array should be x1 coordinate, y1
        coordinate, x2 coordinate, y2 coordinate, and number of votes. The
        points are expected to be the intersection of the line with the edges
        of the image. The array should always be sorted by number of votes.

        image_width (int): Width of the image in pixels.

        image_height (int): Height of the image in pixels.
        '''
        self.xyxyvs = xyxyvs
        self.image_width = image_width
        self.image_height = image_height

    def __getitem__(self, idx):
        return Lines(self.xyxyvs[idx], self.image_width, self.image_height)

    def __len__(self) -> int:
        return len(self.xyxyvs)

    @classmethod
    def cat(cls, lines):
        '''
        Concatenates an iterable of :class:`Lines` to a new :class:`Lines`
        object.
        '''
        w, h = lines[0].image_width, lines[0].image_height
        if any(w != x.image_width or h != x.image_height for x in lines):
            raise ValueError(
                'Cannot concatenate lines of different image shapes'
            )
        xyxyvs = np.concatenate([x.xyxyvs for x in lines])
        return cls(
            # We want the array to be sorted by number of votes
            xyxyvs[np.argsort(xyxyvs[:, 4])[::-1]],
            w, h,
        )

    @property
    def mbs(self) -> np.ndarray:
        '''
        Converts the lines into slope-intercept form.
        '''
        x1, y1, x2, y2 = self.xyxys.T
        m = (y2 - y1) / (x2 - x1)
        b = y1 - (m * x1)
        return m, b

    @property
    def xyxys(self) -> np.ndarray:
        return self.xyxyvs[:, :4]

    def deduplicate(self, theta_thresh: float = 0.99,
                    dist_thresh: float = 10.):
        '''
        Deduplicates the lines, returning a new :class:`Lines` object.
        '''
        # We begin by comparing the angle of each line
        x1, y1, x2, y2 = self.xyxys.T
        r = np.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)
        d_x, d_y = (x1 - x2) / r, (y1 - y2) / r
        dot = (
            (d_x.reshape(1, -1) * d_x.reshape(-1, 1)) +
            (d_y.reshape(1, -1) * d_y.reshape(-1, 1))
        )
        theta_match = dot > theta_thresh
        # We don't want lines to count as duplicates of themself, so set the
        # diagonal to false.
        idxs = np.arange(len(self), dtype=int)
        theta_match[idxs, idxs] = False

        # Calculate point of closest approach in the image.
        m = (y2 - y1) / (x2 - x1)
        b = y1 - (x1 * m) + (1000 * m)
        x_i = (
            (b.reshape(1, -1) - b.reshape(-1, 1)) /
            (m.reshape(1, -1) - m.reshape(-1, 1))
        )
        y_i = m.reshape(1, -1) * x_i + b.reshape(1, -1)
        is_parallel = np.isnan(x_i)
        is_intersecting = (
            (x_i > 0) & (x_i < self.image_width) & (y_i > 0) &
            (y_i < self.image_height)
        )

        def _dist(_x1, _y1, _x2, _y2):
            return np.sqrt((_x1 - _x2) ** 2 + (_y1 - _y2) ** 2)
        min_end_dist = np.stack(
            [_dist(x1.reshape(1, -1), y1.reshape(1, -1), x1.reshape(-1, 1),
                   y1.reshape(-1, 1)),
             _dist(x1.reshape(1, -1), y1.reshape(1, -1), x2.reshape(-1, 1),
                   y2.reshape(-1, 1)),
             _dist(x2.reshape(1, -1), y2.reshape(1, -1), x1.reshape(-1, 1),
                   y1.reshape(-1, 1)),
             _dist(x2.reshape(1, -1), y2.reshape(1, -1), x2.reshape(-1, 1),
                   y2.reshape(-1, 1))],
            axis=2
        ).min(2)

        dist = np.where(
            is_parallel,
            (
                np.abs(b.reshape(1, -1) - b.reshape(-1, 1)) /
                np.sqrt(m ** 2 + 1).reshape(1, -1)
            ),
            np.where(
                is_intersecting,
                0,
                min_end_dist,
            ),
        )
        b_match = (dist < dist_thresh)

        # Duplicates match in both angle and distance of closest approach
        is_duplicate = (theta_match & b_match)

        # Of a set of duplicates, we want to keep the one with the most votes.
        keep = np.ones(len(self), dtype=bool)
        # I hate not having this vectorized, but haven't found a good way to
        # vectorize it with more C++ code, which I don't have time for.
        for i in range(len(self)):
            if keep[i]:
                keep[i + 1:][is_duplicate[i + 1:, i]] = False

        return self[keep]

    def distance_to_point(self, pt_x: float, pt_y: float,
                          normalize: bool = True) -> np.ndarray:
        '''
        Returns an array giving the distance between a point and the lines.

        Args:

        pt_x (float): X coordinate of the point.

        pt_y (float): Y coordinate of the point.

        normalize (bool): If True, divides the distance by the norm of the
        point.
        '''
        m, b = self.mbs
        # Given a point (x', y'), minimizing the distance between the point and
        # y = mx + b gives:
        # x = (y' + x' - b) / (m^2 + 1)
        closest_x = (m * pt_y + pt_x - m * b) / (m ** 2 + 1)
        closest_y = m * closest_x + b
        d = np.sqrt((pt_x - closest_x) ** 2 + (pt_y - closest_y) ** 2)
        # Normalize by the distance to the intersection point
        if normalize:
            d /= np.sqrt(pt_x ** 2 + pt_y ** 2)
        return d

    @classmethod
    def empty(cls, image_width: int, image_height: int):
        '''
        Returns an empty :class:`Lines` object with the given image dimensions.
        '''
        return cls(np.empty((0, 5)), image_width, image_height)

    @staticmethod
    def _binarize_image(image: np.ndarray) -> np.ndarray:
        '''
        Binarizes an image prior to line detection using the Hough transform.
        '''
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
        image = cv2.morphologyEx(image, cv2.MORPH_TOPHAT, kernel)
        image = cv2.adaptiveThreshold(
            image, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 129,
            -4
        )
        return image

    @classmethod
    def hough(cls, image: np.ndarray):
        '''
        Constructs a :class:`Lines` object from an image using the Hough
        transform.
        '''
        if image.ndim == 3:
            image = cls._binarize_image(image)
        lines = hough_lines_with_votes(
            image,
            theta=(pi / 1440),
            rho=1,
            threshold=50,
            min_theta=0,
            max_theta=pi,
            use_edgeval=False,
        )
        lines = lines.squeeze(1)
        height, width, *_ = image.shape

        rhos, thetas, votes = lines.T

        cos_t = np.cos(thetas)
        sin_t = np.sin(thetas)

        # Create masks for non-zero denominators
        cos_t_nz = np.abs(cos_t) > 1e-4
        sin_t_nz = np.abs(sin_t) > 1e-4

        # Top edge (y=0)
        x_top = np.divide(
            rhos, cos_t, where=cos_t_nz, out=np.full_like(rhos, np.nan)
        )
        # Bottom edge (y=height)
        x_bottom = np.divide(
            rhos - height * sin_t, cos_t, where=cos_t_nz,
            out=np.full_like(rhos, np.nan)
        )
        # Left edge (x=0)
        y_left = np.divide(
            rhos, sin_t, where=sin_t_nz, out=np.full_like(rhos, np.nan)
        )
        # Right edge (x=width)
        y_right = np.divide(
            rhos - width * cos_t, sin_t, where=sin_t_nz,
            out=np.full_like(rhos, np.nan)
        )

        # Stack all potential intersection points into a (N, 4, 2) array
        # The 4 points are [top, bottom, left, right]
        candidates = np.stack([
            np.stack([x_top, np.zeros_like(x_top)], axis=1),
            np.stack([x_bottom, np.full_like(x_bottom, height)], axis=1),
            np.stack([np.zeros_like(y_left), y_left], axis=1),
            np.stack([np.full_like(y_right, width), y_right], axis=1)
        ], axis=1)

        # Create a validity mask for these candidates
        # A point is valid if its coordinates are within the image boundaries
        top_valid = (x_top >= 0) & (x_top <= width)
        bottom_valid = (x_bottom >= 0) & (x_bottom <= width)
        left_valid = (y_left >= 0) & (y_left <= height)
        right_valid = (y_right >= 0) & (y_right <= height)

        validity_mask = np.stack(
            [top_valid, bottom_valid, left_valid, right_valid], axis=1
        )
        validity_mask[validity_mask.sum(1) > 2, 3] = False
        validity_mask[validity_mask.sum(1) > 2, 2] = False
        lines = candidates[validity_mask].reshape(-1, 4)
        num_pix = np.abs(lines[:, :2] - lines[:, 2:]).max(1)

        lines = np.concatenate(
            (lines, (votes / num_pix).reshape(-1, 1)), axis=1
        )
        lines = lines[num_pix > 0]
        lines = lines[np.argsort(lines[:, 4])[::-1], :]

        return cls(lines, width, height)

    def intersection_point(self) -> np.ndarray:
        '''
        Estimates a common intersection point of the lines. Does this by
        finding all of the pairwise intersections and taking their median.
        '''
        m, b = self.mbs
        # Given mx + b = m'x + b', (m' - m)x = b - b'
        inter_x = (
            -(b.reshape(1, -1) - b.reshape(-1, 1)) /
            (m.reshape(1, -1) - m.reshape(-1, 1))
        )
        inter_y = m.reshape(1, -1) * inter_x + b.reshape(1, -1)
        # nanmedian to ignore the non-existent self-intersection
        inter_x, inter_y = np.nanmedian(inter_x), np.nanmedian(inter_y)
        return (inter_x, inter_y)

    def intersects_box(self, box: np.ndarray) -> np.ndarray:
        '''
        Returns a mask specifying which lines which intersect with an array of
        boxes.
        '''
        if box.ndim == 1:
            return self.intersects_box(box[None, :]).flatten()

        x, y, w, h = box.T
        x1, y1, x2, y2 = self.xyxys.T
        a, b, c = y1 - y2, x2 - x1, (y2 - y1) * x1 - (x2 - x1) * y1
        tl = np.outer(a, x) + np.outer(b, y) + c[:, None]
        br = np.outer(a, x + w) + np.outer(b, y + h) + c[:, None]
        tr = np.outer(a, x + w) + np.outer(b, y) + c[:, None]
        bl = np.outer(a, x) + np.outer(b, y + h) + c[:, None]
        return ((tl * br) < 0) + ((tr * bl) < 0)

    def angle_from_point(self, x: float, y: float) -> np.ndarray:
        x1, y1, x2, y2 = self.xyxys.T
        midpoint_x = (x1 + x2) / 2
        midpoint_y = (y1 + y2) / 2
        return np.atan2(midpoint_y - y, x - midpoint_x)


def select_lines(optional_lines: Lines, required_line: Lines,
                 max_depth: int = 1000, max_lines: int = 8,
                 min_lines: int = 2) -> Lines:
    lines = optional_lines[:1024].deduplicate()[:max_lines]
    lines = Lines.cat((lines, required_line)).deduplicate()

    for _ in range(max_depth):
        inter_point = lines.intersection_point()
        dist = lines.distance_to_point(*inter_point)
        lines = Lines.cat((lines[dist < 0.2], required_line)).deduplicate()

        if len(lines) >= min_lines:
            inter_point = lines.intersection_point()
            dist = lines.distance_to_point(*inter_point)
            if (dist < 0.1).all():
                return lines[:max_lines]

        dist = lines.distance_to_point(*inter_point)
        lines = lines[dist < 0.2]
        lines = Lines.cat((lines, required_line)).deduplicate()

    else:
        raise WarpError('Failed to find yard lines after maximum iterations')


def select_lines_intersecting_boxes(lines: Lines, boxes: np.ndarray,
                                    max_depth: int = 10_000) \
        -> Tuple[Lines, Optional[Tuple[float, float]]]:
    '''
    Finds the best set of lines intersecting a set of boxes.

    Args:

    lines (:class:`Lines`): The lines.

    boxes (:class:`numpy.ndarray`): The boxes.

    max_depth (int): This is the maximum depth to iterate through when
    attempting to choose the best set of lines.
    '''
    if len(boxes) == 0:
        out = Lines.empty(lines.image_width, lines.image_height)
        return out, None

    # Determine which lines intersect which box.
    intersection_mask = lines.intersects_box(boxes)

    # If we only have one box, then just use the best line intersecting that
    # box.
    if len(boxes) == 1:
        return lines[intersection_mask.flatten()][0:1], None

    # Next, we create a list of candidate choices to consider for each box.
    # Since the lines are sorted by number of votes, this gives us the best
    # possible lines for each box. candidates will then be a List[Lines].
    n_lines_per_box = floor(max_depth ** (1 / len(boxes)))
    candidates = [lines[m][:n_lines_per_box] for m in intersection_mask.T]

    def _pick_from_heap(heap: Iterable[Iterable[int]],
                        candidates: Iterable[Lines],
                        boxes: Iterable[Optional[np.ndarray]]):
        '''
        This is a utility function. Given a heap, we go through the heap one at
        a time looking for a valid set of candidates.
        '''
        # heap[i][j] will be the index of the line we're choosing from
        # candidates[j] at the ith step.
        for idxs in heap:
            # Build the set of candidate lines.
            lines = Lines.cat(
                [_l[_i:_i + 1] for _i, _l in zip(idxs, candidates)
                 if _i is not None]
            )
            if len(lines) == 0:
                continue

            # Deduplicate. If a line intersects multiple boxes, we might be
            # able to eliminate a line as a duplicate.
            mask = lines.intersects_box(boxes)
            keep = np.zeros(len(lines), dtype=bool)
            no_intersect = np.ones(len(boxes), dtype=bool)
            for i in range(len(lines)):
                if (mask[i] & no_intersect).any():
                    keep[i] = True
                    no_intersect[mask[i]] = False
            lines = lines[keep]

            if len(lines) == 1:
                return lines, None

            # Find the intersection point, and check the distance to the
            # intersection point. If it's good, we're done.
            in_x, in_y = lines.intersection_point()
            dist = lines.distance_to_point(in_x, in_y)

            if (dist < 0.01).all():
                return lines, (in_x, in_y)

        else:
            raise WarpError('Failed to find yard lines')

    # The heap will consist of pairs (score, idxs), where score is the sum of
    # the votes, and idxs[i] is the index of the line we're choosing in
    # candidates[i]. We sort the heap to ensure we start with the best possible
    # choices, but once that's done we don't use the scores.
    heap = [
        (sum(_l.xyxyvs[_i, 4] for _i, _l in zip(idxs, candidates)), idxs)
        for idxs in product(*(range(len(_l)) for _l in candidates))
    ]
    heap.sort(reverse=True)
    heap = [x[1] for x in heap]

    # We start by calling _pick_from_heap. That goes through the heap one at a
    # time, looking for a valid choice. If that doesn't work, we rebuild the
    # heap, this time allowing one box to be missing a line, and try again. We
    # use None in place of the index to denote that we're not picking a line
    # for that box this time.
    try:
        return _pick_from_heap(heap, candidates, boxes)
    except WarpError:
        heap = []
        for i in range(len(boxes)):
            for idxs in product(*(
                [None] if (j == i) else range(len(_l))
                for j, _l in enumerate(candidates)
            )):
                score = sum(
                    _l.xyxyvs[_i, 4] for _i, _l in zip(idxs, candidates)
                    if _i is not None
                )
                heap.append((score, idxs))
        heap.sort(reverse=True, key=lambda row: row[0])
        heap = [x[1] for x in heap]
        return _pick_from_heap(heap, candidates, boxes)


def find_yard_lines(lines: Lines, boxes: np.ndarray, max_depth: int = 10_000) \
        -> Lines:
    '''
    This is the function that finds the yard lines.

    Args:

    lines (:class:`Lines`): All the lines in the image.

    boxes (:class:`numpy.ndarray`): The yard boxes.

    max_depth (int): This is the maximum depth to iterate through when
    attempting to choose the best set of lines.
    '''
    # Begin by finding the lines intersecting the boxes themselves. If we find
    # multiple lines, inter_point will be the vanishing point of the lines.
    initial_lines, inter_point = select_lines_intersecting_boxes(
        lines, boxes, max_depth
    )
    if inter_point is None:
        return select_lines(lines, initial_lines)

    # Look for all lines that intersect the vanishing point.
    lines = lines[lines.distance_to_point(*inter_point) < 0.01]

    # Calculate the angles between the vanishing point and the line.
    thetas = lines.angle_from_point(*inter_point)
    init_thetas = initial_lines.angle_from_point(*inter_point)
    init_thetas.sort()

    # Look for lines in between the yard lines.
    mid_lines = []
    for theta_1, theta_2 in zip(init_thetas[:-1], init_thetas[1:]):
        d = theta_2 - theta_1
        mask = (thetas > theta_1 + 0.2 * d) & (thetas < theta_2 - 0.2 * d)
        mid_lines.append(lines[mask][0:1])

    # Add the in-between lines to the original lines, and we're done.
    lines = Lines.cat((*mid_lines, initial_lines))

    return lines
