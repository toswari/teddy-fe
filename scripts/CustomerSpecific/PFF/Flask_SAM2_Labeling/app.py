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

def render_mask_and_bbox(image, mask, color, alpha=0.5):
    """Render both mask and bounding box on the image"""
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

def split_video_into_chunks(video_path, chunk_size=30):
    """Split video into smaller chunks of specified number of frames with overlap"""
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    
    chunk_paths = []
    for i in range(0, total_frames, chunk_size):
        chunk_path = f"{video_path}_chunk_{i}.mp4"
        chunk_paths.append(chunk_path)
        
        # Extract chunk using ffmpeg with overlap
        start_time = i / fps
        # Add one frame to the duration to ensure overlap
        duration = min((chunk_size + 1) / fps, (total_frames - i) / fps)
        # Use precise frame extraction
        os.system(f'ffmpeg -y -ss {start_time} -t {duration} -i "{video_path}" -c:v libx264 -pix_fmt yuv420p -r {fps} "{chunk_path}"')
    
    return chunk_paths

def process_video_chunk(chunk_path, model, list_input_dict, start_frame, total_frames, obj_to_color, previous_masks=None):
    """Process a single video chunk and return tracked masks"""
    results = {
        "tracked_masks": [],
        "last_frame": None,
        "fps": 0,
        "total_fps": 0,
        "track_time": 0,
        "preprocess_time": 0
    }
    
    # Read chunk frames
    cap = cv2.VideoCapture(chunk_path)
    frames = []
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    cap.release()
    
    # Initialize empty masks for all frames in this chunk
    tracked_masks = [{} for _ in range(len(frames))]
    
    # If we have previous masks, update the input for tracking
    if previous_masks:
        # Get the last frame's masks and convert them to points
        last_frame_masks = previous_masks[-1]
        updated_input = []
        for obj_id, mask in last_frame_masks.items():
            # Find contours in the mask
            contours, _ = cv2.findContours(mask.astype(np.uint8), 
                                         cv2.RETR_EXTERNAL, 
                                         cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                # Get the largest contour
                largest_contour = max(contours, key=cv2.contourArea)
                # Get the center point of the contour
                M = cv2.moments(largest_contour)
                if M["m00"] != 0:
                    cx = M["m10"] / M["m00"]  # Use floating point for precision
                    cy = M["m01"] / M["m00"]  # Use floating point for precision
                    # Convert to normalized coordinates without rounding
                    h, w = mask.shape
                    cx_norm = cx / w
                    cy_norm = cy / h
                    # Add to input
                    updated_input.append({
                        "points": [[cx_norm, cy_norm]],
                        "labels": [1],  # Positive point
                        "obj_id": obj_id
                    })
    else:
        # If no previous masks, use the initial input
        updated_input = list_input_dict
    
    if updated_input:
        # Create video input for chunk
        with open(chunk_path, "rb") as f:
            video_bytes = f.read()
        cl_video = dt.Video(bytes=video_bytes)
        
        try:
            start_track_time = time.perf_counter()
            tracked_frames = model.generate(
                video=cl_video,
                list_dict_inputs=updated_input
            )
            
            total_track_time = []
            frame_idx = 0
            
            for trk_frame in tracked_frames:
                if frame_idx >= len(frames):
                    break
                    
                frame_masks = {}
                for reg in trk_frame.regions:
                    mask_bytes = reg.proto.region_info.mask.image.base64
                    mask = Image.open(io.BytesIO(mask_bytes))
                    mask = np.asarray(mask, dtype=np.uint8)
                    # Ensure mask is the same size as the frame
                    if mask.shape[:2] != frames[frame_idx].shape[:2]:
                        mask = cv2.resize(mask, (frames[frame_idx].shape[1], frames[frame_idx].shape[0]), 
                                        interpolation=cv2.INTER_NEAREST)
                    track_id = int(reg.proto.track_id)
                    frame_masks[track_id] = mask
                
                tracked_masks[frame_idx] = frame_masks
                this_track_time = time.perf_counter() - start_track_time
                total_track_time.append(this_track_time)
                
                # Calculate FPS
                first_frame_time = total_track_time[0] if total_track_time else 0
                track_time = sum(total_track_time[1:]) if len(total_track_time) > 1 else 0
                fps = round((len(total_track_time) - 1) / track_time, 3) if track_time else -1
                total_fps = round(len(total_track_time) / sum(total_track_time), 3) if total_track_time else 0
                
                start_track_time = time.perf_counter()
                frame_idx += 1
            
            # Create preview of the last frame
            if frames:
                last_frame = frames[-1].copy()
                last_frame_masks = tracked_masks[-1] if tracked_masks else {}
                
                # Check which objects are still being tracked
                active_objects = set(last_frame_masks.keys())
                all_objects = set(obj_to_color.keys())
                missing_objects = all_objects - active_objects
                
                # Draw masks for tracked objects
                for obj_id, mask in last_frame_masks.items():
                    color = obj_to_color[obj_id]
                    last_frame = render_mask_and_bbox(last_frame, mask, color, 0.7)
                
                # Add text for missing objects
                if missing_objects:
                    cv2.putText(
                        last_frame,
                        f"Objects {', '.join(map(str, missing_objects))} not in frame",
                        (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1,
                        (255, 0, 0),
                        2
                    )
                
                results["last_frame"] = last_frame
                results["fps"] = fps
                results["total_fps"] = total_fps
                results["track_time"] = track_time
                results["preprocess_time"] = first_frame_time
                
        except Exception as e:
            print(f"Tracking failed for chunk: {e}")
            # Return empty masks for failed frames
            return results
    
    # Return all masks except the last one (which will be the first frame of next chunk)
    results["tracked_masks"] = tracked_masks[:-1]
    return results

def write_video_from_frames(frames, masks, obj_to_color, fps=30):
    """Write frames with masks and bounding boxes to a video file using ffmpeg"""
    # Create temporary directory for frames
    frames_dir = tempfile.mkdtemp(prefix="frames-")
    try:
        # Save frames as images
        for frame_idx, frame in enumerate(frames):
            annotated_frame = frame.copy()
            frame_masks = masks[frame_idx] if frame_idx < len(masks) else {}
            
            # Draw masks and bounding boxes for each tracked object
            for obj_id, mask in frame_masks.items():
                color = obj_to_color[obj_id]
                annotated_frame = render_mask_and_bbox(annotated_frame, mask, color, 0.7)
            
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
        'status': 'Processing video chunks',
        'updates': [],
        'is_complete': False
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

# New function to handle video processing in background
def process_video_tracking(session_id, session, model, list_input_dict, output_dir):
    try:
        # Split video into chunks
        chunk_paths = split_video_into_chunks(session['file_path'], chunk_size=30)
        
        # Process each chunk
        all_tracked_masks = []
        total_frames = len(session['frames'])
        previous_masks = None
        progress_updates = []
        
        # Store the output directory in the tracking progress
        tracking_progress[session_id]['output_dir'] = output_dir
        tracking_progress[session_id]['total_frames'] = total_frames
        
        for i, chunk_path in enumerate(chunk_paths):
            # Update progress status
            tracking_progress[session_id]['status'] = f"Processing chunk {i+1}/{len(chunk_paths)}"
            tracking_progress[session_id]['progress'] = min(0.95, (i / len(chunk_paths)))
            
            start_frame = i * 30
            
            chunk_result = process_video_chunk(
                chunk_path, model, list_input_dict,
                start_frame, total_frames,
                session['obj_to_color'],
                previous_masks
            )
            
            chunk_masks = chunk_result["tracked_masks"]
            if not chunk_masks:
                update = {
                    'message': f"All objects lost tracking at chunk {i + 1}. Stopping processing.",
                    'progress': (start_frame + 1) / total_frames
                }
                progress_updates.append(update)
                tracking_progress[session_id]['updates'].append(update)
                break
            
            all_tracked_masks.extend(chunk_masks)
            previous_masks = chunk_masks
            
            update = {
                'message': f"Processed chunk {i + 1}/{len(chunk_paths)}. " +
                          f"Total FPS = {chunk_result['total_fps']}. " +
                          f"Track FPS = {chunk_result['fps']}.",
                'progress': min(1.0, (start_frame + len(chunk_masks)) / total_frames),
                'preview': None
            }
            
            # Save preview image if available
            if chunk_result["last_frame"] is not None:
                preview_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{session_id}_chunk_{i}_preview.jpg")
                cv2.imwrite(preview_path, cv2.cvtColor(chunk_result["last_frame"], cv2.COLOR_RGB2BGR))
                update['preview'] = f"/uploads/{session_id}_chunk_{i}_preview.jpg"
            
            progress_updates.append(update)
            tracking_progress[session_id]['updates'].append(update)
            
            # Clean up chunk file
            try:
                os.remove(chunk_path)
            except:
                pass
        
        # Final processing after all chunks are done
        tracking_progress[session_id]['status'] = "Finalizing results"
        tracking_progress[session_id]['progress'] = 0.95
        
        success = False
        download_url = None
        
        # If we have masks, convert to COCO and save frames
        if all_tracked_masks:
            # Convert to COCO format
            tracking_progress[session_id]['status'] = "Converting to COCO format (1/4)"
            tracking_progress[session_id]['progress'] = 0.96
            tracking_progress[session_id]['updates'].append({
                'message': "Converting tracking results to COCO format...",
                'progress': 0.96
            })
            
            coco_data = convert_to_coco_format(
                session['frames'], 
                all_tracked_masks, 
                session['width'], 
                session['height'], 
                output_dir
            )
            
            # Save COCO annotations
            tracking_progress[session_id]['status'] = "Saving annotations (2/4)"
            tracking_progress[session_id]['progress'] = 0.97
            tracking_progress[session_id]['updates'].append({
                'message': "Saving COCO annotations to file...",
                'progress': 0.97
            })
            
            annotations_path = os.path.join(output_dir, "annotations.json")
            with open(annotations_path, "w") as f:
                json.dump(coco_data, f)
            
            # Save frames with masks
            tracking_progress[session_id]['status'] = "Saving annotated frames (3/4)"
            tracking_progress[session_id]['progress'] = 0.98
            tracking_progress[session_id]['updates'].append({
                'message': f"Saving {len(session['frames'])} annotated frames...",
                'progress': 0.98
            })
            
            frames_dir = os.path.join(output_dir, "frames")
            os.makedirs(frames_dir, exist_ok=True)
            
            for frame_idx, frame in enumerate(session['frames']):
                if frame_idx % 50 == 0:  # Update status occasionally
                    frame_progress = 0.98 + (0.01 * frame_idx / len(session['frames']))
                    tracking_progress[session_id]['progress'] = frame_progress
                    tracking_progress[session_id]['status'] = f"Saving frames: {frame_idx}/{len(session['frames'])}"
                
                frame_masks = all_tracked_masks[frame_idx] if frame_idx < len(all_tracked_masks) else {}
                annotated_frame = frame.copy()
                
                for obj_id, mask in frame_masks.items():
                    color = session['obj_to_color'][obj_id]
                    annotated_frame = render_mask_and_bbox(annotated_frame, mask, color, 0.7)
                
                # Save frame
                frame_path = os.path.join(frames_dir, f"frame_{frame_idx:04d}.jpg")
                cv2.imwrite(frame_path, cv2.cvtColor(annotated_frame, cv2.COLOR_RGB2BGR))
            
            # Create annotated video
            tracking_progress[session_id]['status'] = "Creating annotated video (4/4)"
            tracking_progress[session_id]['progress'] = 0.99
            tracking_progress[session_id]['updates'].append({
                'message': "Creating final annotated video...",
                'progress': 0.99
            })
            
            try:
                tracked_video_path = write_video_from_frames(
                    session['frames'], 
                    all_tracked_masks, 
                    session['obj_to_color'],
                    fps=session['fps']
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
                    'progress': 0.99
                })
                # Even if video creation fails, we still have the frames and annotations
            
            success = True
            download_url = f"/download/{os.path.basename(output_dir)}"
        
        # Update final tracking progress
        tracking_progress[session_id].update({
            'progress': 1.0,
            'status': 'Complete' if success else 'Failed',
            'success': success,
            'is_complete': True,
            'download_url': download_url,
            'error': None if success else 'No frames were successfully processed',
            'progress_updates': progress_updates
        })
        
        # Add final completion message
        tracking_progress[session_id]['updates'].append({
            'message': 'Processing complete! Results ready for download.',
            'progress': 1.0
        })
        
    except Exception as e:
        print(f"Error in processing: {str(e)}")
        # Update tracking progress with error
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