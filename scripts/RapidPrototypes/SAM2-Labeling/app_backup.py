from flask import Flask, render_template, request, redirect, url_for, jsonify, send_from_directory
import os
import cv2
import numpy as np
import tempfile
import json
import uuid
import io
from werkzeug.utils import secure_filename
from PIL import Image
from dotenv import load_dotenv
import shutil
from pathlib import Path
import zipfile
import time
from scipy import ndimage

# Load environment variables
load_dotenv()

# Set up environment variables for Windows compatibility
if os.name == 'nt':  # Windows
    os.environ['HOME'] = os.environ.get('USERPROFILE', '')
    os.environ['CLARIFAI_PAT'] = os.getenv('PAT', '')

# Import Clarifai 
from clarifai.client import Model
from clarifai.runners.utils import data_types as dt

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max upload size
app.config['OUTPUT_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'processed_videos')

# Create upload and output folders if they don't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

# Global variables to store session data
video_data = {}

# Global tracking progress data
tracking_progress = {}

def render_mask(image, mask, color, alpha=0.5):
    """Render mask on image with specified color and transparency"""
    colored_mask = np.expand_dims(mask, 0).repeat(3, axis=0)
    colored_mask = np.moveaxis(colored_mask, 0, -1)
    masked = np.ma.MaskedArray(image, mask=colored_mask, fill_value=color)
    image_overlay = masked.filled()
    image = cv2.addWeighted(image, 1 - alpha, image_overlay, alpha, 0)
    return image

def draw_points(image, points, labels, color, point_size=4):
    """Draw points on the image with different styles for positive/negative points.
    
    Args:
        image: The image to draw on
        points: List of [x, y] normalized coordinates
        labels: List of point labels (1 for positive, 0 for negative)
        color: Base color for the points
        point_size: Size of the points in pixels
    """
    h, w = image.shape[:2]
    for (x, y), label in zip(points, labels):
        # Convert normalized coordinates to pixel coordinates
        px = int(x * w)
        py = int(y * h)
        
        if label == 1:  # Positive point
            # Draw filled circle with white border
            cv2.circle(image, (px, py), point_size + 2, (255, 255, 255), -1)
            cv2.circle(image, (px, py), point_size, color, -1)
        else:  # Negative point
            # Draw X mark
            size = point_size + 2
            cv2.line(image, (px - size, py - size), (px + size, py + size), (255, 255, 255), 3)
            cv2.line(image, (px - size, py + size), (px + size, py - size), (255, 255, 255), 3)
            cv2.line(image, (px - size, py - size), (px + size, py + size), color, 2)
            cv2.line(image, (px - size, py + size), (px + size, py - size), color, 2)

def render_mask_and_bbox(image, mask, color, alpha=0.5, points=None, labels=None):
    """Render mask, bounding box, and points on the image"""
    # Ensure mask is the same size as the image
    if mask.shape[:2] != image.shape[:2]:
        mask = cv2.resize(mask, (image.shape[1], image.shape[0]), interpolation=cv2.INTER_NEAREST)
    
    # Render mask
    colored_mask = np.expand_dims(mask, 0).repeat(3, axis=0)
    colored_mask = np.moveaxis(colored_mask, 0, -1)
    masked = np.ma.MaskedArray(image, mask=colored_mask, fill_value=color)
    image_overlay = masked.filled()
    image = cv2.addWeighted(image, 1 - alpha, image_overlay, alpha, 0)
    
    # Add bounding box
    contours, _ = cv2.findContours(mask.astype(np.uint8), 
                                 cv2.RETR_EXTERNAL, 
                                 cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        largest_contour = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(largest_contour)
        cv2.rectangle(image, (x, y), (x + w, y + h), color, 2)
    
    # Draw points if provided
    if points is not None and labels is not None:
        draw_points(image, points, labels, color)
    
    return image

def create_output_directory(video_filename):
    """Create a directory for the video output files"""
    base_name = os.path.splitext(video_filename)[0]
    safe_name = "".join(c for c in base_name if c.isalnum() or c in (' ', '-', '_')).strip()
    output_dir = os.path.join(app.config['OUTPUT_FOLDER'], safe_name)
    os.makedirs(output_dir, exist_ok=True)
    return output_dir

def convert_to_coco_format(frames, tracked_masks, image_width, image_height, output_dir):
    """Convert tracked masks to COCO format"""
    coco_data = {
        "images": [],
        "annotations": [],
        "categories": []
    }
    
    # Create a category for each unique object ID
    unique_obj_ids = set()
    for frame_masks in tracked_masks:
        for obj_id in frame_masks.keys():
            unique_obj_ids.add(obj_id)
    
    # Add categories with the original track IDs
    for obj_id in unique_obj_ids:
        coco_data["categories"].append({
            "id": int(obj_id),  # Use the original track ID
            "name": f"player_{obj_id}",
            "supercategory": "person"
        })
    
    for frame_idx, frame in enumerate(frames):
        image_info = {
            "id": frame_idx + 1,
            "width": image_width,
            "height": image_height,
            "file_name": f"frame_{frame_idx:04d}.jpg"
        }
        coco_data["images"].append(image_info)
        
        # Check if we have masks for this frame
        if frame_idx < len(tracked_masks) and tracked_masks[frame_idx]:
            for obj_id, mask in tracked_masks[frame_idx].items():
                contours, _ = cv2.findContours(mask.astype(np.uint8), 
                                             cv2.RETR_EXTERNAL, 
                                             cv2.CHAIN_APPROX_SIMPLE)
                
                if contours:
                    largest_contour = max(contours, key=cv2.contourArea)
                    epsilon = 0.005 * cv2.arcLength(largest_contour, True)
                    polygon = cv2.approxPolyDP(largest_contour, epsilon, True)
                    segmentation = polygon.reshape(-1).tolist()
                    x, y, w, h = cv2.boundingRect(largest_contour)
                    
                    annotation = {
                        "id": len(coco_data["annotations"]) + 1,
                        "image_id": frame_idx + 1,
                        "category_id": int(obj_id),  # Use the original track ID as category_id
                        "track_id": int(obj_id),     # Explicitly add track_id for MOT
                        "segmentation": [segmentation],
                        "area": float(cv2.contourArea(largest_contour)),
                        "bbox": [float(x), float(y), float(w), float(h)],
                        "iscrowd": 0
                    }
                    coco_data["annotations"].append(annotation)
    
    return coco_data

def mask_to_polygons(mask, min_area=100):
    """Convert a binary mask to a list of polygons.
    
    Args:
        mask: Binary mask array
        min_area: Minimum area for a polygon to be considered
    
    Returns:
        List of polygons, where each polygon is a numpy array of points
    """
    # Find contours in the mask
    contours, _ = cv2.findContours(mask.astype(np.uint8), 
                                 cv2.RETR_EXTERNAL, 
                                 cv2.CHAIN_APPROX_SIMPLE)
    
    polygons = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area >= min_area:
            # Simplify the contour to reduce number of points
            epsilon = 0.005 * cv2.arcLength(contour, True)
            polygon = cv2.approxPolyDP(contour, epsilon, True)
            polygons.append(polygon.squeeze())
    
    return polygons

def find_core_regions(mask):
    """Find the core regions of a mask using distance transform.
    
    Args:
        mask: Binary mask array
    
    Returns:
        cores: Core regions of the mask
        dist_transform: Distance transform of the mask
    """
    from scipy import ndimage
    
    # Create distance transform
    dist_transform = ndimage.distance_transform_edt(mask)
    
    # Find core regions (areas far from boundaries)
    max_dist = np.max(dist_transform)
    if max_dist > 0:
        # Normalize distance transform
        dist_norm = dist_transform / max_dist
        # Core regions are areas with high distance values
        cores = dist_norm > 0.6  # Core regions are 60% of max distance
    else:
        cores = np.zeros_like(mask)
        dist_norm = np.zeros_like(mask, dtype=float)
    
    return cores, dist_norm

def find_separation_zones(mask, other_masks):
    """Find zones where objects need to be explicitly separated.
    
    Args:
        mask: Binary mask array
        other_masks: Dictionary of other object masks
    
    Returns:
        separation_zones: Binary mask of separation zones
        dilated_others: Dilated mask of other objects
    """
    h, w = mask.shape
    kernel_size = max(5, int(min(w, h) * 0.04))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    
    # Create dilated version of current mask
    dilated_mask = cv2.dilate(mask.astype(np.uint8), kernel, iterations=2)
    
    # Create dilated version of other masks
    dilated_others = np.zeros_like(mask)
    if other_masks:
        for other_mask in other_masks.values():
            dilated_other = cv2.dilate(other_mask.astype(np.uint8), kernel, iterations=2)
            dilated_others = np.logical_or(dilated_others, dilated_other)
    
    # Find overlap zones
    separation_zones = dilated_mask & dilated_others
    
    # Dilate separation zones slightly
    separation_zones = cv2.dilate(separation_zones.astype(np.uint8), kernel, iterations=1)
    
    return separation_zones, dilated_others.astype(np.uint8)

def generate_structured_grid(mask, dist_transform, cores, num_points):
    """Generate a structured grid of points within mask, focused on core regions.
    
    Args:
        mask: Binary mask array
        dist_transform: Distance transform of the mask
        cores: Core regions of the mask
        num_points: Number of points to generate
    
    Returns:
        points: List of [x, y] normalized coordinates
    """
    h, w = mask.shape
    points = []
    
    # Find core region centroids
    core_labels, num_cores = ndimage.label(cores)
    if num_cores > 0:
        for i in range(1, num_cores + 1):
            core_mask = core_labels == i
            M = cv2.moments(core_mask.astype(np.uint8))
            if M["m00"] > 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                points.append([cx/w, cy/h])
    
    # If no core points found, use mask centroid
    if not points:
        M = cv2.moments(mask.astype(np.uint8))
        if M["m00"] > 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            points.append([cx/w, cy/h])
    
    if len(points) > 0:
        # Generate concentric circles of points
        num_circles = int(np.sqrt(num_points))
        points_per_circle = max(1, num_points // (num_circles * len(points)))
        
        for center_point in points[:]:  # Use existing core points as centers
            cx, cy = int(center_point[0] * w), int(center_point[1] * h)
            max_radius = np.max(dist_transform[max(0, cy-20):min(h, cy+20), 
                                             max(0, cx-20):min(w, cx+20)])
            
            for i in range(num_circles):
                radius = max_radius * (i + 1) / (num_circles + 1)
                for j in range(points_per_circle):
                    angle = 2 * np.pi * j / points_per_circle
                    px = cx + radius * np.cos(angle)
                    py = cy + radius * np.sin(angle)
                    
                    # Ensure point is within bounds
                    px = int(max(0, min(w-1, px)))
                    py = int(max(0, min(h-1, py)))
                    
                    if mask[py, px] and dist_transform[py, px] > 0.3:  # Only add points in safe areas
                        points.append([px/w, py/h])
    
    return points

def generate_boundary_points(mask, separation_zones, dilated_others, num_points, margin):
    """Generate boundary points that respect separation zones.
    
    Args:
        mask: Binary mask array
        separation_zones: Binary mask of separation zones
        dilated_others: Dilated mask of other objects
        num_points: Number of points to generate
        margin: Base margin distance
    
    Returns:
        points: List of [x, y] normalized coordinates
    """
    h, w = mask.shape
    points = []
    
    # Find contours of the mask
    contours, _ = cv2.findContours(mask.astype(np.uint8), 
                                 cv2.RETR_EXTERNAL, 
                                 cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        return points
    
    # Get the largest contour
    contour = max(contours, key=cv2.contourArea)
    
    # Calculate base margin distance
    base_margin = min(w, h) * margin
    
    # Generate points along the contour
    perimeter = cv2.arcLength(contour, True)
    interval = perimeter / num_points
    
    for i in range(num_points):
        # Get point on perimeter
        dist = i * interval
        total_dist = 0
        point_found = False
        
        for j in range(len(contour) - 1):
            pt1 = contour[j][0]
            pt2 = contour[(j + 1) % len(contour)][0]
            d = np.sqrt(np.sum((pt2 - pt1)**2))
            
            if total_dist + d >= dist:
                # Interpolate point
                frac = (dist - total_dist) / d
                px = pt1[0] + frac * (pt2[0] - pt1[0])
                py = pt1[1] + frac * (pt2[1] - pt1[1])
                
                # Calculate normal vector
                dx = pt2[0] - pt1[0]
                dy = pt2[1] - pt1[1]
                length = np.sqrt(dx*dx + dy*dy)
                
                if length > 0:
                    nx = -dy/length
                    ny = dx/length
                    
                    # Check if we're near a separation zone
                    near_separation = False
                    if separation_zones[int(py), int(px)]:
                        near_separation = True
                    
                    # Try different margins based on location
                    margins = [1.5, 2.0, 2.5, 3.0] if near_separation else [1.0, 1.5, 2.0]
                    
                    for mult in margins:
                        margin_dist = base_margin * mult
                        if near_separation:
                            margin_dist *= 1.5  # Increase margin near separation zones
                        
                        # Add small random variation
                        margin_dist *= (1 + np.random.uniform(-0.1, 0.1))
                        
                        test_px = px + nx * margin_dist
                        test_py = py + ny * margin_dist
                        
                        # Ensure point is within bounds
                        test_px = int(max(0, min(w-1, test_px)))
                        test_py = int(max(0, min(h-1, test_py)))
                        
                        # Check if point is valid
                        if not mask[test_py, test_px] and \
                           not dilated_others[test_py, test_px] and \
                           not separation_zones[test_py, test_px]:
                            points.append([test_px/w, test_py/h])
                            point_found = True
                            break
                
                if point_found:
                    break
            
            total_dist += d
    
    return points

def find_object_parts(mask, min_area=100):
    """Find distinct parts of an object using hierarchical contour analysis.
    
    Args:
        mask: Binary mask array
        min_area: Minimum area for a part to be considered
    
    Returns:
        List of (contour, center_point) tuples for each significant part
    """
    h, w = mask.shape
    min_area = max(min_area, int(0.01 * h * w))  # Adaptive minimum area based on image size
    parts = []
    
    # Find contours with hierarchy
    contours, hierarchy = cv2.findContours(mask.astype(np.uint8), 
                                         cv2.RETR_TREE, 
                                         cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        return parts
    
    # Process contours considering hierarchy
    hierarchy = hierarchy[0]
    for i, contour in enumerate(contours):
        area = cv2.contourArea(contour)
        if area < min_area:
            continue
        
        # Get contour properties
        M = cv2.moments(contour)
        if M["m00"] == 0:
            continue
        
        cx = int(M["m10"] / M["m00"])
        cy = int(M["m01"] / M["m00"])
        
        # Calculate contour complexity
        perimeter = cv2.arcLength(contour, True)
        complexity = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        
        # Check if this is a potential separate part
        is_separate_part = False
        if hierarchy[i][3] == -1:  # External contour
            is_separate_part = True
        elif len(complexity) > 8:  # Complex enough to be a separate part
            is_separate_part = True
        
        if is_separate_part:
            # Create mask for this contour
            part_mask = np.zeros_like(mask)
            cv2.drawContours(part_mask, [contour], -1, 1, -1)
            
            # Check if this part is sufficiently distinct
            if cv2.countNonZero(part_mask) > min_area:
                parts.append((contour, (cx, cy)))
    
    return parts

def get_edge_points(contour, num_points, mask_shape, other_masks=None):
    """Get evenly spaced points along the contour edge.
    
    Args:
        contour: Object contour
        num_points: Number of points to generate
        mask_shape: Shape of the original mask (h, w)
        other_masks: Dictionary of other object masks
    
    Returns:
        List of [x, y] normalized coordinates
    """
    h, w = mask_shape
    points = []
    
    # Create mask of other objects if provided
    other_objects = np.zeros(mask_shape, dtype=np.uint8)
    if other_masks:
        for other_mask in other_masks.values():
            other_objects = np.logical_or(other_objects, other_mask)
    
    # Get evenly spaced points along contour
    perimeter = cv2.arcLength(contour, True)
    interval = perimeter / num_points
    
    for i in range(num_points):
        # Get point on perimeter
        dist = i * interval
        total_dist = 0
        
        for j in range(len(contour) - 1):
            pt1 = contour[j][0]
            pt2 = contour[(j + 1) % len(contour)][0]
            d = np.sqrt(np.sum((pt2 - pt1)**2))
            
            if total_dist + d >= dist:
                # Interpolate point
                frac = (dist - total_dist) / d
                px = pt1[0] + frac * (pt2[0] - pt1[0])
                py = pt1[1] + frac * (pt2[1] - pt1[1])
                
                # Check if point is too close to other objects
                px_int, py_int = int(px), int(py)
                if 0 <= px_int < w and 0 <= py_int < h:
                    if not other_objects[py_int, px_int]:
                        points.append([px/w, py/h])
                break
            
            total_dist += d
    
    return points

def generate_grid_points(mask, grid_size=5, margin=0.1, other_masks=None):
    """Generate points for tracking using enhanced object part detection and strategic point placement.
    
    Args:
        mask: Binary mask array
        grid_size: Base size for point grid
        margin: Margin around the mask for negative points
        other_masks: Dictionary of {obj_id: mask} for other objects to avoid
    
    Returns:
        List of [x, y] normalized coordinates and their labels
    """
    h, w = mask.shape
    points = []
    labels = []
    
    # Find object parts using enhanced detection
    parts = find_object_parts(mask)
    if not parts:
        return [], []
    
    # Calculate distance transform for the mask
    dist_transform = cv2.distanceTransform(mask.astype(np.uint8), cv2.DIST_L2, 5)
    dist_transform = dist_transform / dist_transform.max()  # Normalize
    
    # Find separation zones if other masks exist
    separation_zones = np.zeros_like(mask)
    if other_masks:
        kernel_size = max(5, int(min(w, h) * 0.04))
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
        dilated_mask = cv2.dilate(mask.astype(np.uint8), kernel, iterations=2)
        
        for other_mask in other_masks.values():
            dilated_other = cv2.dilate(other_mask.astype(np.uint8), kernel, iterations=2)
            overlap = dilated_mask & dilated_other
            separation_zones = np.logical_or(separation_zones, overlap)
    
    # Process each part
    for contour, center in parts:
        # Add center point with high confidence
        cx, cy = center
        if not separation_zones[int(cy), int(cx)]:
            points.append([cx/w, cy/h])
            labels.append(1)
        
        # Get contour points with adaptive spacing
        epsilon = 0.02 * cv2.arcLength(contour, True)
        approx_contour = cv2.approxPolyDP(contour, epsilon, True)
        
        # Calculate number of points based on contour complexity
        num_points = max(grid_size * 2, len(approx_contour))
        
        # Get evenly spaced points along the contour
        contour_points = []
        for i in range(num_points):
            idx = (i * len(approx_contour)) // num_points
            px, py = approx_contour[idx][0]
            
            # Check distance from separation zones
            if separation_zones[int(py), int(px)]:
                continue
                
            # Add point if it's in a high-confidence region
            if dist_transform[int(py), int(px)] > 0.3:
                contour_points.append([px/w, py/h])
        
        points.extend(contour_points)
        labels.extend([1] * len(contour_points))
        
        # Generate negative points strategically
        part_mask = np.zeros_like(mask)
        cv2.drawContours(part_mask, [contour], -1, 1, -1)
        
        # Create boundary zone
        boundary_width = max(3, int(min(w, h) * margin))
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (boundary_width, boundary_width))
        dilated = cv2.dilate(part_mask, kernel, iterations=1)
        boundary = cv2.subtract(dilated, part_mask)
        
        # Sample negative points from boundary
        y_coords, x_coords = np.where(boundary > 0)
        if len(y_coords) > 0:
            # Calculate angles from center to potential points
            angles = np.arctan2(y_coords - cy, x_coords - cx)
            
            # Divide into sectors and sample points from each sector
            num_sectors = 8
            sector_size = 2 * np.pi / num_sectors
            points_per_sector = max(1, grid_size // num_sectors)
            
            for sector in range(num_sectors):
                sector_start = sector * sector_size - np.pi
                sector_end = (sector + 1) * sector_size - np.pi
                
                # Find points in this sector
                sector_mask = (angles >= sector_start) & (angles < sector_end)
                sector_indices = np.where(sector_mask)[0]
                
                if len(sector_indices) > 0:
                    # Sample points from this sector
                    sample_size = min(points_per_sector, len(sector_indices))
                    sampled_indices = np.random.choice(sector_indices, sample_size, replace=False)
                    
                    for idx in sampled_indices:
                        px, py = x_coords[idx], y_coords[idx]
                        
                        # Verify point is valid
                        if other_masks:
                            valid = True
                            for other_mask in other_masks.values():
                                if other_mask[py, px]:
                                    valid = False
                                    break
                            if not valid:
                                continue
                        
                        # Add negative point
                        points.append([px/w, py/h])
                        labels.append(0)
    
    return points, labels

def write_video_from_frames(frames, masks, obj_to_color, fps=30, points_data=None):
    """Write frames with masks, bounding boxes, and points to a video file"""
    # Create temporary directory for frames
    frames_dir = tempfile.mkdtemp(prefix="frames-")
    try:
        # Save frames as images
        for frame_idx, frame in enumerate(frames):
            annotated_frame = frame.copy()
            frame_masks = masks[frame_idx] if frame_idx < len(masks) else {}
            
            # Draw masks, bounding boxes, and points for each tracked object
            for obj_id, mask in frame_masks.items():
                color = obj_to_color[obj_id]
                # Get points data if available
                frame_points = None
                frame_labels = None
                if points_data and frame_idx < len(points_data):
                    obj_points = points_data[frame_idx].get(obj_id, None)
                    if obj_points:
                        frame_points = obj_points["points"]
                        frame_labels = obj_points["labels"]
                
                annotated_frame = render_mask_and_bbox(
                    annotated_frame, mask, color, 0.7,
                    frame_points, frame_labels
                )
            
            # Add frame number
            cv2.putText(
                annotated_frame,
                f"Frame {frame_idx + 1}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (255, 255, 255),
                2
            )
            
            # Save frame
            frame_path = os.path.join(frames_dir, f"frame_{frame_idx:04d}.jpg")
            cv2.imwrite(frame_path, cv2.cvtColor(annotated_frame, cv2.COLOR_RGB2BGR))
        
        # Create output video path
        output_path = tempfile.mktemp(suffix=".mp4", prefix="out-sam2-")
        
        # Use ffmpeg to create video from frames with explicit FPS
        ffmpeg_cmd = f'ffmpeg -y -framerate {fps} -i "{frames_dir}/frame_%04d.jpg" -c:v libx264 -pix_fmt yuv420p -crf 23 -r {fps} "{output_path}"'
        result = os.system(ffmpeg_cmd)
        
        if result != 0:
            raise Exception("Failed to create video using ffmpeg")
        
        return output_path
    finally:
        # Clean up temporary directory
        shutil.rmtree(frames_dir)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'video' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['video']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Generate a unique ID for this session
    session_id = str(uuid.uuid4())
    
    # Save the file
    filename = secure_filename(file.filename)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{session_id}_{filename}")
    file.save(file_path)
    
    # Extract the first frame for annotation
    cap = cv2.VideoCapture(file_path)
    ret, frame = cap.read()
    
    if not ret:
        return jsonify({'error': 'Could not read video file'}), 400
    
    # Get video info
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 30  # Default to 30 FPS if not available
    
    # Extract all frames (for now, in a real app you might want to stream this)
    frames = []
    while ret:
        frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        ret, frame = cap.read()
    
    cap.release()
    
    # Save first frame as JPEG
    first_frame_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{session_id}_first_frame.jpg")
    cv2.imwrite(first_frame_path, cv2.cvtColor(frames[0], cv2.COLOR_RGB2BGR))
    
    # Save session info
    video_data[session_id] = {
        'file_path': file_path,
        'filename': filename,
        'first_frame_path': first_frame_path,
        'frames': frames,
        'fps': fps,
        'objects': [],
        'obj_id': 0,
        'obj_to_color': {},
        'width': frames[0].shape[1],
        'height': frames[0].shape[0]
    }
    
    return jsonify({
        'session_id': session_id,
        'first_frame': f"/uploads/{session_id}_first_frame.jpg",
        'width': frames[0].shape[1],
        'height': frames[0].shape[0]
    })

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/add_player', methods=['POST'])
def add_player():
    data = request.json
    session_id = data.get('session_id')
    
    if session_id not in video_data:
        return jsonify({'error': 'Invalid session ID'}), 400
    
    # Create a new player object
    obj_id = video_data[session_id]['obj_id']
    video_data[session_id]['obj_id'] += 1
    
    # Generate a random color for this player
    color = tuple(np.random.randint(0, 255, 3).tolist())
    video_data[session_id]['obj_to_color'][obj_id] = color
    
    # Create new player entry
    video_data[session_id]['objects'].append({
        'points': [],
        'labels': [],
        'mask': None,
        'obj_id': obj_id
    })
    
    return jsonify({
        'obj_id': obj_id,
        'color': color
    })

@app.route('/add_point', methods=['POST'])
def add_point():
    data = request.json
    session_id = data.get('session_id')
    obj_id = data.get('obj_id')
    point = data.get('point')  # [x, y] normalized coordinates
    point_type = data.get('point_type')  # 'positive' or 'negative'
    
    if session_id not in video_data:
        return jsonify({'error': 'Invalid session ID'}), 400
    
    # Find the object
    obj = None
    for o in video_data[session_id]['objects']:
        if o['obj_id'] == obj_id:
            obj = o
            break
    
    if obj is None:
        return jsonify({'error': 'Invalid object ID'}), 400
    
    # Add the point
    obj['points'].append(point)
    obj['labels'].append(1 if point_type == 'positive' else 0)
    
    return jsonify({
        'success': True,
        'point_id': len(obj['points']) - 1
    })

@app.route('/remove_point', methods=['POST'])
def remove_point():
    data = request.json
    session_id = data.get('session_id')
    obj_id = data.get('obj_id')
    point_id = data.get('point_id')
    
    if session_id not in video_data:
        return jsonify({'error': 'Invalid session ID'}), 400
    
    # Find the object
    obj = None
    for o in video_data[session_id]['objects']:
        if o['obj_id'] == obj_id:
            obj = o
            break
    
    if obj is None:
        return jsonify({'error': 'Invalid object ID'}), 400
    
    if point_id < 0 or point_id >= len(obj['points']):
        return jsonify({'error': 'Invalid point ID'}), 400
    
    # Remove the point
    obj['points'].pop(point_id)
    obj['labels'].pop(point_id)
    
    return jsonify({'success': True})

@app.route('/clear_points', methods=['POST'])
def clear_points():
    data = request.json
    session_id = data.get('session_id')
    obj_id = data.get('obj_id')
    
    if session_id not in video_data:
        return jsonify({'error': 'Invalid session ID'}), 400
    
    # Find the object
    obj = None
    for o in video_data[session_id]['objects']:
        if o['obj_id'] == obj_id:
            obj = o
            break
    
    if obj is None:
        return jsonify({'error': 'Invalid object ID'}), 400
    
    # Clear points
    obj['points'] = []
    obj['labels'] = []
    
    return jsonify({'success': True})

@app.route('/get_players', methods=['GET'])
def get_players():
    session_id = request.args.get('session_id')
    
    if session_id not in video_data:
        return jsonify({'error': 'Invalid session ID'}), 400
    
    players = []
    for obj in video_data[session_id]['objects']:
        players.append({
            'obj_id': obj['obj_id'],
            'points': obj['points'],
            'labels': obj['labels'],
            'color': video_data[session_id]['obj_to_color'][obj['obj_id']]
        })
    
    return jsonify({'players': players})

@app.route('/generate_masks', methods=['POST'])
def generate_masks():
    data = request.json
    session_id = data.get('session_id')
    
    if session_id not in video_data:
        return jsonify({'error': 'Invalid session ID'}), 400
    
    # Get PAT from environment
    pat = os.getenv("PAT")
    if not pat:
        return jsonify({'error': 'PAT not found in environment'}), 500
    
    # Initialize model
    model_url = data.get('model_url', 'https://clarifai.com/meta/segment-anything/models/sam2_1-hiera-base-plus')
    model = Model(url=model_url, pat=pat)
    
    # Generate masks for each player
    session = video_data[session_id]
    first_frame = session['frames'][0]
    first_frame_pil = Image.fromarray(first_frame)
    
    results = []
    for obj in session['objects']:
        if not obj['points']:
            results.append({
                'obj_id': obj['obj_id'],
                'success': False,
                'error': 'No points provided'
            })
            continue
        
        try:
            masks = model.predict(
                image=dt.Image.from_pil(first_frame_pil),
                dict_inputs={"points": obj['points'], "labels": obj['labels']},
                multimask_output=False
            )
            
            if not masks:
                results.append({
                    'obj_id': obj['obj_id'],
                    'success': False,
                    'error': 'No mask returned'
                })
                continue
            
            mask_bytes = masks[0].proto.region_info.mask.image.base64
            mask = Image.open(io.BytesIO(mask_bytes))
            obj['mask'] = np.asarray(mask, dtype=np.uint8)
            
            # Generate preview image with the mask
            preview_frame = first_frame.copy()
            color = session['obj_to_color'][obj['obj_id']]
            preview_frame = render_mask_and_bbox(preview_frame, obj['mask'], color, 0.7)
            
            # Save preview image
            preview_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{session_id}_mask_{obj['obj_id']}.jpg")
            cv2.imwrite(preview_path, cv2.cvtColor(preview_frame, cv2.COLOR_RGB2BGR))
            
            results.append({
                'obj_id': obj['obj_id'],
                'success': True,
                'preview': f"/uploads/{session_id}_mask_{obj['obj_id']}.jpg"
            })
            
        except Exception as e:
            results.append({
                'obj_id': obj['obj_id'],
                'success': False,
                'error': str(e)
            })
    
    # Generate combined preview
    combined_frame = first_frame.copy()
    for obj in session['objects']:
        if obj['mask'] is not None:
            color = session['obj_to_color'][obj['obj_id']]
            combined_frame = render_mask_and_bbox(combined_frame, obj['mask'], color, 0.7)
            
            # Add object ID to the mask
            contours, _ = cv2.findContours(obj['mask'].astype(np.uint8), 
                                         cv2.RETR_EXTERNAL, 
                                         cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                largest_contour = max(contours, key=cv2.contourArea)
                M = cv2.moments(largest_contour)
                if M["m00"] != 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    cv2.putText(
                        combined_frame,
                        f"ID: {obj['obj_id']}",
                        (cx - 20, cy),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1,
                        session['obj_to_color'][obj['obj_id']],
                        2
                    )
    
    # Save combined preview
    combined_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{session_id}_masks_combined.jpg")
    cv2.imwrite(combined_path, cv2.cvtColor(combined_frame, cv2.COLOR_RGB2BGR))
    
    return jsonify({
        'results': results,
        'combined_preview': f"/uploads/{session_id}_masks_combined.jpg"
    })

@app.route('/check_tracking_progress', methods=['GET'])
def check_tracking_progress():
    session_id = request.args.get('session_id')
    
    if session_id not in tracking_progress:
        return jsonify({'progress': 0, 'status': 'Not started', 'updates': []})
    
    return jsonify(tracking_progress[session_id])

@app.route('/track_and_annotate', methods=['POST'])
def track_and_annotate():
    data = request.json
    session_id = data.get('session_id')
    
    if session_id not in video_data:
        return jsonify({'error': 'Invalid session ID'}), 400
    
    session = video_data[session_id]
    
    # Check if masks have been generated
    masks_generated = all(obj.get('mask') is not None for obj in session['objects'])
    if not masks_generated:
        return jsonify({'error': 'Generate masks first'}), 400
    
    # Get PAT from environment
    pat = os.getenv("PAT")
    if not pat:
        return jsonify({'error': 'PAT not found in environment'}), 500
    
    # Initialize model
    model_url = data.get('model_url', 'https://clarifai.com/meta/segment-anything/models/sam2_1-hiera-base-plus')
    model = Model(url=model_url, pat=pat)
    
    # Create output directory
    output_dir = create_output_directory(session['filename'])
    
    # Prepare input for tracking
    list_input_dict = []
    for obj in session['objects']:
        list_input_dict.append({
            "points": obj["points"],
            "labels": obj["labels"],
            "obj_id": obj["obj_id"]
        })
    
    # Initialize tracking progress
    tracking_progress[session_id] = {
        'progress': 0,
        'status': 'Processing video',
        'updates': [],
        'is_complete': False,
        'output_dir': output_dir,
        'total_frames': len(session['frames']),
        'current_frame': 0,
        'frame_previews': {}  # Store frame preview paths
    }
    
    # Start processing in a background thread to not block the response
    import threading
    thread = threading.Thread(
        target=process_video_tracking,
        args=(session_id, session, model, list_input_dict, output_dir)
    )
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'success': True,
        'message': 'Tracking process started',
        'session_id': session_id
    })

def process_video_tracking(session_id, session, model, list_input_dict, output_dir):
    try:
        print(f"Starting video processing for session {session_id}")
        print(f"Video file path: {session['file_path']}")
        print(f"Total frames: {len(session['frames'])}")
        
        tracking_progress[session_id].update({
            'status': "Processing video",
            'progress': 0.1,
            'current_frame': 0,
            'total_frames': len(session['frames']),
            'frame_previews': {}  # Store frame preview paths
        })
        
        # Process the entire video at once
        print("Reading video file...")
        with open(session['file_path'], "rb") as f:
            video_bytes = f.read()
        print(f"Video size: {len(video_bytes)} bytes")
        cl_video = dt.Video(bytes=video_bytes)
        
        try:
            print("Starting model.generate call...")
            start_track_time = time.perf_counter()
            tracked_frames = model.generate(
                video=cl_video,
                list_dict_inputs=list_input_dict
            )
            print("model.generate completed")
            
            # Initialize storage for masks and points
            all_tracked_masks = []
            all_points_data = []
            total_frames = len(session['frames'])
            
            print("Processing tracked frames...")
            # Process each frame
            for frame_idx, trk_frame in enumerate(tracked_frames):
                print(f"Processing frame {frame_idx + 1}/{total_frames}")
                if frame_idx >= total_frames:
                    break
                
                frame_masks = {}
                frame_points = {}
                
                for reg in trk_frame.regions:
                    track_id = int(reg.proto.track_id)
                    print(f"Processing region for track_id {track_id}")
                    
                    mask_bytes = reg.proto.region_info.mask.image.base64
                    mask = Image.open(io.BytesIO(mask_bytes))
                    mask = np.asarray(mask, dtype=np.uint8)
                    
                    # Ensure mask is the same size as the frame
                    if mask.shape[:2] != session['frames'][frame_idx].shape[:2]:
                        print(f"Resizing mask from {mask.shape} to {session['frames'][frame_idx].shape[:2]}")
                        mask = cv2.resize(mask, (session['frames'][frame_idx].shape[1], session['frames'][frame_idx].shape[0]), 
                                        interpolation=cv2.INTER_NEAREST)
                    
                    frame_masks[track_id] = mask
                    
                    # Generate points for visualization
                    points, labels = generate_grid_points(mask)
                    frame_points[track_id] = {
                        "points": points,
                        "labels": labels
                    }
                
                all_tracked_masks.append(frame_masks)
                all_points_data.append(frame_points)
                
                # Create preview of current frame
                preview_frame = session['frames'][frame_idx].copy()
                for obj_id, mask in frame_masks.items():
                    color = session['obj_to_color'][obj_id]
                    points_data = frame_points.get(obj_id)
                    points = points_data["points"] if points_data else None
                    labels = points_data["labels"] if points_data else None
                    preview_frame = render_mask_and_bbox(preview_frame, mask, color, 0.7, points, labels)
                
                # Add frame number to preview
                cv2.putText(
                    preview_frame,
                    f"Frame {frame_idx + 1}/{total_frames}",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (255, 255, 255),
                    2
                )
                
                # Save preview
                preview_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{session_id}_frame_{frame_idx}.jpg")
                cv2.imwrite(preview_path, cv2.cvtColor(preview_frame, cv2.COLOR_RGB2BGR))
                
                # Update progress
                progress = min(0.9, 0.1 + (0.8 * frame_idx / total_frames))
                tracking_progress[session_id].update({
                    'progress': progress,
                    'status': f"Processing frame {frame_idx + 1}/{total_frames}",
                    'current_frame': frame_idx,
                    'frame_previews': {
                        frame_idx: f"/uploads/{session_id}_frame_{frame_idx}.jpg"
                    }
                })
                
                # Add update message
                tracking_progress[session_id]['updates'].append({
                    'message': f"Processed frame {frame_idx + 1}/{total_frames}",
                    'progress': progress,
                    'frame_idx': frame_idx,
                    'preview': f"/uploads/{session_id}_frame_{frame_idx}.jpg"
                })
            
            # Final processing
            tracking_progress[session_id]['status'] = "Finalizing results"
            tracking_progress[session_id]['progress'] = 0.9
            
            success = False
            download_url = None
            
            if all_tracked_masks:
                # Convert to COCO format
                tracking_progress[session_id].update({
                    'status': "Converting to COCO format",
                    'progress': 0.92
                })
                
                coco_data = convert_to_coco_format(
                    session['frames'], 
                    all_tracked_masks, 
                    session['width'], 
                    session['height'], 
                    output_dir
                )
                
                # Save COCO annotations
                tracking_progress[session_id].update({
                    'status': "Saving annotations",
                    'progress': 0.94
                })
                
                annotations_path = os.path.join(output_dir, "annotations.json")
                with open(annotations_path, "w") as f:
                    json.dump(coco_data, f)
                
                # Save frames with masks
                tracking_progress[session_id].update({
                    'status': "Saving annotated frames",
                    'progress': 0.96
                })
                
                frames_dir = os.path.join(output_dir, "frames")
                os.makedirs(frames_dir, exist_ok=True)
                
                for frame_idx, frame in enumerate(session['frames']):
                    frame_masks = all_tracked_masks[frame_idx] if frame_idx < len(all_tracked_masks) else {}
                    frame_points = all_points_data[frame_idx] if frame_idx < len(all_points_data) else {}
                    annotated_frame = frame.copy()
                    
                    for obj_id, mask in frame_masks.items():
                        color = session['obj_to_color'][obj_id]
                        points_data = frame_points.get(obj_id)
                        points = points_data["points"] if points_data else None
                        labels = points_data["labels"] if points_data else None
                        annotated_frame = render_mask_and_bbox(annotated_frame, mask, color, 0.7, points, labels)
                    
                    # Save frame
                    frame_path = os.path.join(frames_dir, f"frame_{frame_idx:04d}.jpg")
                    cv2.imwrite(frame_path, cv2.cvtColor(annotated_frame, cv2.COLOR_RGB2BGR))
                
                # Create annotated video
                tracking_progress[session_id].update({
                    'status': "Creating annotated video",
                    'progress': 0.98
                })
                
                try:
                    tracked_video_path = write_video_from_frames(
                        session['frames'], 
                        all_tracked_masks, 
                        session['obj_to_color'],
                        fps=session['fps'],
                        points_data=all_points_data
                    )
                    
                    if tracked_video_path:
                        # Copy to output directory
                        output_video_path = os.path.join(output_dir, f"tracked_{session['filename']}")
                        shutil.copy(tracked_video_path, output_video_path)
                        os.remove(tracked_video_path)
                except Exception as e:
                    print(f"Failed to save annotated video: {e}")
                    tracking_progress[session_id]['updates'].append({
                        'message': f"Warning: Failed to create video: {str(e)}",
                        'progress': 0.98
                    })
                
                success = True
                download_url = f"/download/{os.path.basename(output_dir)}"
            
            # Update final tracking progress
            tracking_progress[session_id].update({
                'progress': 1.0,
                'status': 'Complete' if success else 'Failed',
                'success': success,
                'is_complete': True,
                'download_url': download_url,
                'error': None if success else 'No frames were successfully processed'
            })
            
            # Add final completion message
            tracking_progress[session_id]['updates'].append({
                'message': 'Processing complete! Results ready for download.',
                'progress': 1.0
            })
            
        except Exception as e:
            print(f"Error in tracking: {str(e)}")
            tracking_progress[session_id].update({
                'progress': 1.0,
                'status': 'Failed',
                'success': False,
                'is_complete': True,
                'error': str(e)
            })
            
    except Exception as e:
        print(f"Error in processing: {str(e)}")
        tracking_progress[session_id].update({
            'progress': 1.0,
            'status': 'Failed',
            'success': False,
            'is_complete': True,
            'error': str(e)
        })

@app.route('/download/<directory>')
def download_results(directory):
    # Create a zip file of the output directory
    output_dir = os.path.join(app.config['OUTPUT_FOLDER'], directory)
    if not os.path.exists(output_dir):
        return jsonify({'error': 'Directory not found'}), 404
    
    # Create a temporary zip file
    zip_path = tempfile.mktemp(suffix=".zip")
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for root, dirs, files in os.walk(output_dir):
            for file in files:
                file_path = os.path.join(root, file)
                zipf.write(file_path, os.path.relpath(file_path, app.config['OUTPUT_FOLDER']))
    
    return send_from_directory(os.path.dirname(zip_path), os.path.basename(zip_path), as_attachment=True)

@app.route('/generate_mask_for_player', methods=['POST'])
def generate_mask_for_player():
    """Generate a mask for a single player in real-time for immediate feedback"""
    data = request.json
    session_id = data.get('session_id')
    obj_id = data.get('obj_id')
    
    if session_id not in video_data:
        return jsonify({'error': 'Invalid session ID', 'success': False}), 400
    
    # Find the player object
    obj = None
    for o in video_data[session_id]['objects']:
        if o['obj_id'] == obj_id:
            obj = o
            break
    
    if obj is None:
        return jsonify({'error': 'Invalid object ID', 'success': False}), 400
    
    if not obj['points']:
        return jsonify({'error': 'No points provided', 'success': False}), 400
    
    # Debug info for points and labels
    print(f"Generating mask for player {obj_id} with {len(obj['points'])} points")
    print(f"Points: {obj['points']}")
    print(f"Labels: {obj['labels']}")
    
    try:
        # Get PAT from environment
        pat = os.getenv("PAT")
        if not pat:
            return jsonify({'error': 'PAT not found in environment', 'success': False}), 500
        
        # Initialize model
        model_url = data.get('model_url', 'https://clarifai.com/meta/segment-anything/models/sam2_1-hiera-base-plus')
        model = Model(url=model_url, pat=pat)
        
        # Get the first frame
        session = video_data[session_id]
        first_frame = session['frames'][0]
        first_frame_pil = Image.fromarray(first_frame)
        
        # Create inputs dictionary with all points and labels
        inputs = {
            "points": obj['points'],
            "labels": obj['labels']
        }
        
        print(f"Sending to model: {inputs}")
        
        # Generate mask
        masks = model.predict(
            image=dt.Image.from_pil(first_frame_pil),
            dict_inputs=inputs,
            multimask_output=False
        )
        
        if not masks:
            return jsonify({
                'error': 'No mask returned from model',
                'success': False
            }), 400
        
        # Get mask bytes and convert to numpy array
        mask_bytes = masks[0].proto.region_info.mask.image.base64
        mask = Image.open(io.BytesIO(mask_bytes))
        obj['mask'] = np.asarray(mask, dtype=np.uint8)
        
        # Generate preview image with mask
        preview_frame = first_frame.copy()
        color = session['obj_to_color'][obj['obj_id']]
        preview_frame = render_mask_and_bbox(preview_frame, obj['mask'], color, 0.7)
        
        # Save preview image and return URL
        preview_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{session_id}_mask_{obj['obj_id']}_preview.jpg")
        cv2.imwrite(preview_path, cv2.cvtColor(preview_frame, cv2.COLOR_RGB2BGR))
        
        return jsonify({
            'success': True,
            'preview': f"/uploads/{session_id}_mask_{obj['obj_id']}_preview.jpg",
            'obj_id': obj['obj_id'],
            'point_count': len(obj['points'])  # Return the number of points used
        })
    
    except Exception as e:
        print(f"Error generating mask: {e}")
        return jsonify({
            'error': str(e),
            'success': False
        }), 500

@app.route('/get_frame_preview/<session_id>/<int:frame_idx>')
def get_frame_preview(session_id, frame_idx):
    if session_id not in tracking_progress or not tracking_progress[session_id].get('is_complete', False):
        return jsonify({'error': 'Tracking not complete'}), 400
    
    # Get the output directory from the tracking progress
    output_dir = tracking_progress[session_id].get('output_dir')
    if not output_dir or not os.path.exists(output_dir):
        return jsonify({'error': 'Output directory not found'}), 404
    
    # Check if the frames directory exists
    frames_dir = os.path.join(output_dir, "frames")
    if not os.path.exists(frames_dir):
        return jsonify({'error': 'Frames directory not found'}), 404
    
    # Get the frame file
    frame_file = os.path.join(frames_dir, f"frame_{frame_idx:04d}.jpg")
    if not os.path.exists(frame_file):
        return jsonify({'error': 'Frame not found'}), 404
    
    return send_from_directory(os.path.dirname(frame_file), os.path.basename(frame_file))

if __name__ == '__main__':
    app.run(debug=True) 