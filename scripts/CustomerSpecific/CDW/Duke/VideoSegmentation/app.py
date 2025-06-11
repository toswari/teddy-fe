import os
import cv2
import numpy as np
import json
import time
import torch
from flask import Flask, request, render_template, jsonify, send_file, url_for
from flask_socketio import SocketIO
from werkzeug.utils import secure_filename
from PIL import Image
import subprocess
import shutil
import threading
import uuid

# Try importing ultralytics
try:
    from ultralytics import YOLO
    ULTRALYTICS_AVAILABLE = True
    print("Ultralytics available, will use YOLO for object detection")
except ImportError:
    ULTRALYTICS_AVAILABLE = False
    print("Ultralytics not available, using fallback detection")

# Initialize Flask app
app = Flask(__name__)
socketio = SocketIO(app)

# Configuration
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024 * 1024  # 2GB max upload

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs('static/css', exist_ok=True)
os.makedirs('static/js', exist_ok=True)

# Load configuration
with open('config.json', 'r') as f:
    config = json.load(f)

# Initialize the PyTorch model
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

def load_yolo_model():
    """Load the YOLO model using ultralytics."""
    if not ULTRALYTICS_AVAILABLE:
        print("ERROR: Ultralytics not available, cannot load YOLO model")
        return None
    
    model_path = config['model']['path']
    
    if not os.path.exists(model_path):
        # Try alternate path
        alt_path = os.path.join('weights', os.path.basename(model_path))
        if os.path.exists(alt_path):
            model_path = alt_path
        else:
            print(f"ERROR: Model not found at {model_path} or {alt_path}")
            return None
    
    try:
        print(f"Loading YOLO model from {model_path}")
        # Set lower memory usage for Windows systems
        if os.name == 'nt':
            torch.backends.cudnn.benchmark = True
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                # Use half precision on Windows with CUDA for better memory efficiency
                model = YOLO(model_path)
                #if hasattr(model, 'half'):
                #    model.half()  # Use FP16 if available
            else:
                model = YOLO(model_path)
        else:
            model = YOLO(model_path)
            
        print(f"YOLO model loaded successfully on {device}")
        print(f"Model has {len(model.names)} classes: {model.names}")
        return model
    except Exception as e:
        print(f"ERROR: Failed to load YOLO model: {e}")
        import traceback
        traceback.print_exc()
        return None
def load_kp_yolo_model():
    """Load the YOLO model using ultralytics."""
    if not ULTRALYTICS_AVAILABLE:
        print("ERROR: Ultralytics not available, cannot load YOLO model")
        return None
    
    model_path = config['key_point_model']['path']
    
    if not os.path.exists(model_path):
        # Try alternate path
        alt_path = os.path.join('weights', os.path.basename(model_path))
        if os.path.exists(alt_path):
            model_path = alt_path
        else:
            print(f"ERROR: Model not found at {model_path} or {alt_path}")
            return None
    
    try:
        print(f"Loading YOLO model from {model_path}")
        # Set lower memory usage for Windows systems
        if os.name == 'nt':
            torch.backends.cudnn.benchmark = True
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                # Use half precision on Windows with CUDA for better memory efficiency
                model = YOLO(model_path)
                #if hasattr(model, 'half'):
                #    model.half()  # Use FP16 if available
            else:
                model = YOLO(model_path)
        else:
            model = YOLO(model_path)
            
        print(f"YOLO model loaded successfully on {device}")
        print(f"Model has {len(model.names)} classes: {model.names}")
        return model
    except Exception as e:
        print(f"ERROR: Failed to load YOLO model: {e}")
        import traceback
        traceback.print_exc()
        return None
# Load the YOLO model
MODEL = load_yolo_model()

# Load the key point model
KEYPOINT_MODEL = load_kp_yolo_model()


def allowed_file(filename):
    """Check if file has an allowed extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def is_gameplay_frame(detections, keypoint_results):
    """
    Determine if a frame shows gameplay based on object detections.
    Args:
        detections: YOLO detection results
        keypoint_results: YOLO keypoint detection results
    Returns:
        bool: True if frame is considered gameplay, False otherwise
    """
    try:
        # If no detections at all, it's not gameplay
        if len(detections) == 0:
            return False
        if len(keypoint_results) == 0:
            return False
            
        # Get the detection results for the first image (batch size is 1)
        boxes = detections[0].boxes
        keypoints = keypoint_results[0].keypoints
        
        # Debug keypoint information
        print("\nKeypoint Debug Info:")
        print(f"Keypoints shape: {keypoints.shape}")
        print(f"Keypoints data shape: {keypoints.data.shape}")
        print(f"Keypoints visible: {keypoints.has_visible}")
        
        # If no boxes detected, it's not gameplay
        if len(boxes) == 0:
            return False
            
        # Check for keypoints - look for any non-zero keypoints
        has_keypoints = False
        if hasattr(keypoints, 'data') and keypoints.data.numel() > 0:
            # Check if any keypoints are non-zero
            keypoint_data = keypoints.data.cpu().numpy()
            if keypoint_data.size > 0 and np.any(keypoint_data != 0):
                has_keypoints = True
                print(f"Found {np.sum(keypoint_data != 0)} non-zero keypoints")
        
        # Get class indices and confidence scores
        class_indices = boxes.cls.cpu().numpy().astype(int)
        confidences = boxes.conf.cpu().numpy()
        
        # Count objects by class with confidence above threshold
        min_confidence = config['gameplay_detection']['min_confidence']
        class_counts = {}
        
        for class_idx, confidence in zip(class_indices, confidences):
            if confidence >= min_confidence:
                class_name = config['classes'][class_idx]
                class_counts[class_name] = class_counts.get(class_name, 0) + 1
                
        # Check for required player count
        player_count = class_counts.get('Player', 0)
        min_players = config['gameplay_detection']['min_players']
        
        # Debug info
        print(f"Detected: {class_counts}")
        print(f"Players: {player_count}/{min_players}")
        print(f"Has keypoints: {has_keypoints}")
        
        # Criteria for gameplay:
        # 1. Minimum number of players detected
        # 2. Any keypoints detected (since we know it's a court keypoint model)
        if player_count >= min_players and has_keypoints:
            print("Gameplay detected!")
            return True
            
        return False
        
    except Exception as e:
        print(f"Error in gameplay detection: {e}")
        import traceback
        traceback.print_exc()
        return False

def process_video(video_path, socket_id=None):
    """
    Process video to extract clips showing gameplay based on object detection.
    Each clip starts only when new gameplay is detected, not from the end of the previous clip.
    """
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print(f"Error: Could not open video file {video_path}")
            return [], []
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        print(f"Video properties: {frame_width}x{frame_height}, {fps} fps, {total_frames} total frames")
        video_filename = os.path.basename(video_path).split('.')[0]
        clips = []
        thumbnails = []
        current_clip_frames = []
        current_clip_frame_numbers = []
        clip_id = 0
        frame_count = 0
        is_gameplay = False
        gameplay_start_frame = 0
        gameplay_start_frame_number = 0
        last_processed_frame = 0  # Track the last frame we processed
        sampling_rate = config['video']['sampling_rate']
        min_clip_duration = config['video']['min_clip_duration']
        min_clip_frames = int(min_clip_duration * fps)
        last_update_time = time.time()
        last_progress = 0
        max_clip_frames = int(200 * fps)
        print(f"\nFrame timing debug:")
        print(f"Sampling rate: {sampling_rate}")
        print(f"Min clip frames: {min_clip_frames}")
        print(f"Max clip frames: {max_clip_frames}")
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            if frame_count % sampling_rate == 0:
                # Player detection (per frame)
                try:
                    results = MODEL(frame, verbose=False)
                except Exception as e:
                    print(f"Error in player detection at frame {frame_count}: {e}")
                    results = []
                # Keypoint detection (per frame)
                try:
                    keypoint_results = KEYPOINT_MODEL(frame, verbose=False, conf=0.5)
                except Exception as e:
                    print(f"Error in keypoint detection at frame {frame_count}: {e}")
                    keypoint_results = []
                frame_is_gameplay = is_gameplay_frame(results, keypoint_results)
                if frame_is_gameplay and not is_gameplay:
                    if frame_count > last_processed_frame:
                        print(f"\nGameplay detected at frame {frame_count}")
                        if socket_id:
                            socketio.emit('progress_update', {
                                'progress': int((frame_count / total_frames) * 100),
                                'status': f'Detected gameplay at frame {frame_count}. Starting new clip...'
                            }, room=socket_id)
                        is_gameplay = True
                        gameplay_start_frame = frame_count
                        current_clip_frames = [frame]
                        current_clip_frame_numbers = [frame_count]
                        print(f"Starting new clip at frame {frame_count}")
                elif not frame_is_gameplay and is_gameplay:
                    print(f"\nEnd of gameplay at frame {frame_count}")
                    if socket_id:
                        socketio.emit('progress_update', {
                            'progress': int((frame_count / total_frames) * 100),
                            'status': f'End of gameplay at frame {frame_count}. Saving clip...'
                        }, room=socket_id)
                    print(f"Clip length: {len(current_clip_frames)} frames")
                    if len(current_clip_frames) >= min_clip_frames:
                        start_frame_num = current_clip_frame_numbers[0]
                        end_frame_num = current_clip_frame_numbers[-1]
                        print(f"Clip frame range: {start_frame_num} to {end_frame_num}")
                        if socket_id:
                            socketio.emit('progress_update', {
                                'progress': int((frame_count / total_frames) * 100),
                                'status': f'Saving clip {clip_id} (frames {start_frame_num}-{end_frame_num})...'
                            }, room=socket_id)
                        clip_info = save_clip(
                            frames=current_clip_frames,
                            video_filename=video_filename,
                            clip_id=clip_id,
                            start_frame=start_frame_num,
                            end_frame=end_frame_num,
                            fps=fps,
                            frame_width=frame_width,
                            frame_height=frame_height,
                            socket_id=socket_id,
                            total_frames=total_frames
                        )
                        if clip_info:
                            clips.append(clip_info['clip'])
                            thumbnails.append(clip_info['thumbnail'])
                            clip_id += 1
                            last_processed_frame = end_frame_num
                            print(f"Updated last processed frame to {last_processed_frame}")
                            if socket_id:
                                socketio.emit('progress_update', {
                                    'progress': int((frame_count / total_frames) * 100),
                                    'status': f'Clip {clip_id-1} saved. Resuming detection for next gameplay segment...'
                                }, room=socket_id)
                    current_clip_frames = []
                    current_clip_frame_numbers = []
                    is_gameplay = False
                elif frame_is_gameplay and is_gameplay:
                    current_clip_frames.append(frame)
                    current_clip_frame_numbers.append(frame_count)
                    if len(current_clip_frames) >= max_clip_frames:
                        print(f"\nClip exceeds max frames ({max_clip_frames}), saving intermediate clip")
                        start_frame_num = current_clip_frame_numbers[0]
                        end_frame_num = current_clip_frame_numbers[-1]
                        print(f"Intermediate clip frame range: {start_frame_num} to {end_frame_num}")
                        if socket_id:
                            socketio.emit('progress_update', {
                                'progress': int((frame_count / total_frames) * 100),
                                'status': f'Saving intermediate clip {clip_id} (frames {start_frame_num}-{end_frame_num})...'
                            }, room=socket_id)
                        clip_info = save_clip(
                            frames=current_clip_frames,
                            video_filename=video_filename,
                            clip_id=clip_id,
                            start_frame=start_frame_num,
                            end_frame=end_frame_num,
                            fps=fps,
                            frame_width=frame_width,
                            frame_height=frame_height,
                            socket_id=socket_id,
                            total_frames=total_frames
                        )
                        if clip_info:
                            clips.append(clip_info['clip'])
                            thumbnails.append(clip_info['thumbnail'])
                            clip_id += 1
                            last_processed_frame = end_frame_num
                            print(f"Updated last processed frame to {last_processed_frame}")
                            if socket_id:
                                socketio.emit('progress_update', {
                                    'progress': int((frame_count / total_frames) * 100),
                                    'status': f'Intermediate clip {clip_id-1} saved. Resuming detection for next gameplay segment...'
                                }, room=socket_id)
                        current_clip_frames = []
                        current_clip_frame_numbers = []
                        is_gameplay = False
            elif is_gameplay:
                if frame_count % 2 == 0:
                    current_clip_frames.append(frame)
                    current_clip_frame_numbers.append(frame_count)
            frame_count += 1
            current_time = time.time()
            if current_time - last_update_time >= 1.0 and socket_id and total_frames > 0:
                progress = int((frame_count / total_frames) * 100)
                if progress != last_progress:
                    try:
                        if progress >= 90:
                            socketio.emit('progress_update', {
                                'progress': progress,
                                'status': f'Processing final frames... ({frame_count}/{total_frames})'
                            }, room=socket_id)
                        else:
                            socketio.emit('progress_update', {'progress': progress}, room=socket_id)
                        last_progress = progress
                    except Exception as e:
                        print(f"Error sending progress update: {e}")
                    last_update_time = current_time
                    print(f"Progress: {progress}% ({frame_count}/{total_frames} frames)")
            if frame_count % 3000 == 0:
                import gc
                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
        # After the main loop, check if we need to save the last clip
        if is_gameplay and len(current_clip_frames) >= min_clip_frames:
            print(f"\nEnd of video reached, saving final gameplay clip.")
            start_frame_num = current_clip_frame_numbers[0]
            end_frame_num = current_clip_frame_numbers[-1]
            print(f"Final clip frame range: {start_frame_num} to {end_frame_num}")
            if socket_id:
                socketio.emit('progress_update', {
                    'progress': 100,
                    'status': f'End of video reached. Saving final clip {clip_id} (frames {start_frame_num}-{end_frame_num})...'
                }, room=socket_id)
            clip_info = save_clip(
                frames=current_clip_frames,
                video_filename=video_filename,
                clip_id=clip_id,
                start_frame=start_frame_num,
                end_frame=end_frame_num,
                fps=fps,
                frame_width=frame_width,
                frame_height=frame_height,
                socket_id=socket_id,
                total_frames=total_frames
            )
            if clip_info:
                clips.append(clip_info['clip'])
                thumbnails.append(clip_info['thumbnail'])
                clip_id += 1
                print(f"Saved final gameplay clip as clip {clip_id-1}")
                if socket_id:
                    socketio.emit('progress_update', {
                        'progress': 100,
                        'status': f'Final clip {clip_id-1} saved.'
                    }, room=socket_id)
        cap.release()
        print(f"Processing complete. Created {len(clips)} clips.")
        if socket_id:
            try:
                socketio.emit('progress_update', {
                    'progress': 100,
                    'status': 'Processing complete!'
                }, room=socket_id)
                socketio.sleep(0.5)
                formatted_clips = []
                for clip in clips:
                    if isinstance(clip, dict) and 'clip' in clip:
                        formatted_clips.append(clip['clip'])
                    else:
                        formatted_clips.append(clip)
                print(f"Sending completion event with {len(formatted_clips)} clips")
                print("Clips data being sent:", json.dumps(formatted_clips, indent=2))
                socketio.emit('processing_complete', {
                    'clips': formatted_clips,
                    'status': 'complete',
                    'message': f'Successfully created {len(formatted_clips)} clips'
                }, room=socket_id)
                print(f"Sent completion events to socket {socket_id}")
            except Exception as e:
                print(f"Error sending completion events: {e}")
                import traceback
                traceback.print_exc()
        return clips, thumbnails
    except Exception as e:
        print(f"Error processing video: {e}")
        import traceback
        traceback.print_exc()
        return [], []

def save_clip(frames, video_filename, clip_id, start_frame, end_frame, fps, frame_width, frame_height, socket_id=None, total_frames=None):
    """
    Save a clip from the original video using frame numbers to preserve audio and overlay a resized watermark logo using FFmpeg. 
    Starts exactly at gameplay detection and adds a fixed 0.5 second buffer only at the end of the clip.
    """
    try:
        import cv2
        import subprocess
        clip_filename = f"{video_filename}_clip_{clip_id}.mp4"
        clip_path = os.path.join(app.config['UPLOAD_FOLDER'], clip_filename)
        print(f"Creating clip at {clip_path}")
        os.makedirs(os.path.dirname(clip_path), exist_ok=True)
        original_video_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{video_filename}.mp4")
        # If CFR preprocessing is used, adjust the path
        if not os.path.exists(original_video_path):
            cfr_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{video_filename}_cfr.mp4")
            if os.path.exists(cfr_path):
                original_video_path = cfr_path
        logo_path = os.path.join('static', 'logo', 'logo.png')
        if not os.path.exists(original_video_path):
            print(f"Error: Could not find original video file {original_video_path}")
            return None
        if not os.path.exists(logo_path):
            print(f"Logo not found at {logo_path}, skipping watermark.")
            logo_path = None
        # Calculate exact start time and duration
        start_time = start_frame / fps
        num_frames = end_frame - start_frame + 1  # Include both start and end frames
        duration = num_frames / fps
        print(f"\nClip timing details:")
        print(f"Start frame: {start_frame}")
        print(f"End frame: {end_frame}")
        print(f"Start time: {start_time:.3f} seconds")
        print(f"Number of frames: {num_frames}")
        print(f"Duration: {duration:.3f} seconds")
        if socket_id and total_frames:
            socketio.emit('progress_update', {
                'progress': int((start_frame / total_frames) * 100),
                'status': f'Creating clip {clip_id} from {start_time:.2f}s for {duration:.2f}s ({num_frames} frames)...'
            }, room=socket_id)
        # Build FFmpeg command with logo resize and overlay
        ffmpeg_cmd = [
            'ffmpeg',
            '-y',
            '-ss', str(start_time),  # Move -ss before -i for accurate seeking
            '-i', original_video_path
        ]
        if logo_path:
            ffmpeg_cmd.extend(['-i', logo_path])
        ffmpeg_cmd.extend(['-frames:v', str(num_frames)])
        if logo_path:
            filter_complex = (
                f"[1][0]scale2ref=w=iw*0.15:h=ow/mdar[logo][vid];"
                f"[vid][logo]overlay=W-w-10:H-h-10"
            )
            ffmpeg_cmd.extend(['-filter_complex', filter_complex])
        ffmpeg_cmd.extend([
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-movflags', '+faststart',
            clip_path
        ])
        print(f"Running FFmpeg command: {' '.join(ffmpeg_cmd)}")
        try:
            subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as e:
            print(f"FFmpeg failed: {e.stderr.decode('utf-8')}")
            if socket_id and total_frames:
                socketio.emit('progress_update', {
                    'progress': int((start_frame / total_frames) * 100),
                    'status': f'FFmpeg failed for clip {clip_id}: {e.stderr.decode("utf-8")}'
                }, room=socket_id)
            return None
        # Save thumbnail (using first frame of clip)
        thumbnail_filename = f"{video_filename}_thumbnail_{clip_id}.jpg"
        thumbnail_path = os.path.join(app.config['UPLOAD_FOLDER'], thumbnail_filename)
        cv2.imwrite(thumbnail_path, frames[0])
        print(f"Clip {clip_id} created with FFmpeg, frames: {num_frames}")
        if socket_id and total_frames:
            socketio.emit('progress_update', {
                'progress': int((start_frame / total_frames) * 100),
                'status': f'Clip {clip_id} created.'
            }, room=socket_id)
        web_path = f"/static/uploads/{os.path.basename(clip_path)}"
        return {
            'clip': {
                'id': clip_id,
                'path': web_path,
                'thumbnail': f"/static/uploads/{thumbnail_filename}",
                'start_time': start_time,
                'duration': duration
            },
            'thumbnail': f"/static/uploads/{thumbnail_filename}"
        }
    except Exception as e:
        print(f"Error saving clip: {e}")
        import traceback
        traceback.print_exc()
        if socket_id and total_frames:
            socketio.emit('progress_update', {
                'progress': 0,
                'status': f'Error saving clip {clip_id}: {str(e)}'
            }, room=socket_id)
        return None

def preprocess_video(input_path, output_path, fps=30):
    """
    Preprocess the video to a fixed frame rate (CFR) and standard audio using FFmpeg.
    """
    import subprocess
    ffmpeg_cmd = [
        'ffmpeg', '-y',
        '-i', input_path,
        '-vf', f'fps={fps}',
        '-c:v', 'libx264',
        '-preset', 'fast',
        '-pix_fmt', 'yuv420p',
        '-c:a', 'aac',
        '-b:a', '192k',
        '-movflags', '+faststart',
        output_path
    ]
    print(f"Preprocessing video to CFR: {' '.join(ffmpeg_cmd)}")
    try:
        subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg preprocessing failed: {e.stderr.decode('utf-8')}")
        raise

@app.route('/')
def index():
    """Render the main page."""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_video():
    """Handle video upload and start processing in a background thread."""
    try:
        print("Upload request received")
        if 'video' not in request.files:
            print("No video file in request")
            return jsonify({'error': 'No video file provided'}), 400
        file = request.files['video']
        if file.filename == '':
            print("Empty filename")
            return jsonify({'error': 'No file selected'}), 400
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            video_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            socket_id = request.form.get('socket_id')
            job_id = str(uuid.uuid4())
            try:
                file.save(video_path)
                print(f"Video saved to {video_path}")
            except Exception as e:
                print(f"Error saving uploaded file: {e}")
                import traceback
                traceback.print_exc()
                if socket_id:
                    socketio.emit('progress_update', {
                        'progress': 0,
                        'status': f'Error saving file: {str(e)}'
                    }, room=socket_id)
                return jsonify({'error': f'Error saving file: {str(e)}'}), 500
            # Start processing in a background thread
            def background_process():
                with app.app_context():
                    try:
                        # Preprocess the video to CFR (30fps) with audio
                        cfr_path = os.path.splitext(video_path)[0] + '_cfr.mp4'
                        try:
                            preprocess_video(video_path, cfr_path, fps=30)
                            print(f"Preprocessed video saved to {cfr_path}")
                            if socket_id:
                                socketio.emit('progress_update', {
                                    'progress': 10,
                                    'status': 'Preprocessing complete. Starting detection...'
                                }, room=socket_id)
                            video_path_to_process = cfr_path
                        except Exception as e:
                            print(f"Error preprocessing video: {e}")
                            import traceback
                            traceback.print_exc()
                            if socket_id:
                                socketio.emit('progress_update', {
                                    'progress': 0,
                                    'status': f'Error preprocessing video: {str(e)}'
                                }, room=socket_id)
                            return
                        # Emit status: starting detection
                        if socket_id:
                            socketio.emit('progress_update', {
                                'progress': 15,
                                'status': 'Detecting gameplay and extracting clips...'
                            }, room=socket_id)
                        print(f"Using socket ID: {socket_id}")
                        try:
                            print(f"Starting video processing for {video_path_to_process}")
                            clips, thumbnails = process_video(video_path_to_process, socket_id)
                            print(f"Processing complete, generated {len(clips)} clips")
                            print("Clips data:", json.dumps(clips, indent=2))
                            # Emit status: detection complete
                            if socket_id:
                                socketio.emit('progress_update', {
                                    'progress': 95,
                                    'status': 'Detection complete. Finalizing...'
                                }, room=socket_id)
                        except Exception as e:
                            print(f"Error processing video: {e}")
                            import traceback
                            traceback.print_exc()
                            if socket_id:
                                socketio.emit('progress_update', {
                                    'progress': 0,
                                    'status': f'Error processing video: {str(e)}'
                                }, room=socket_id)
                            return
                        # Prepare response (emit via socketio)
                        video_url = f"/static/uploads/{os.path.basename(video_path_to_process)}"
                        print(f"Sending response with {len(clips)} clips")
                        # Wait for all clip files and thumbnails to exist
                        all_files = []
                        for clip in clips:
                            if isinstance(clip, dict) and 'clip' in clip:
                                c = clip['clip']
                                all_files.append(os.path.join(app.config['UPLOAD_FOLDER'], os.path.basename(c['path'])))
                                all_files.append(os.path.join(app.config['UPLOAD_FOLDER'], os.path.basename(c['thumbnail'])))
                            else:
                                all_files.append(os.path.join(app.config['UPLOAD_FOLDER'], os.path.basename(clip['path'])))
                                all_files.append(os.path.join(app.config['UPLOAD_FOLDER'], os.path.basename(clip['thumbnail'])))
                        # Wait for all clip files and thumbnails to exist and be stable
                        for f in all_files:
                            wait_for_file_complete(f, timeout=5.0, interval=0.1, stable_checks=2)
                        # Now emit processing_complete
                        if not clips:
                            print("No clips were generated")
                            if socket_id:
                                socketio.emit('processing_complete', {
                                    'warning': 'No gameplay clips were detected in the video',
                                    'video_path': video_url,
                                    'clips': [],
                                    'thumbnails': [],
                                    'status': 'complete'
                                }, room=socket_id)
                            return
                        formatted_clips = []
                        for clip in clips:
                            if isinstance(clip, dict) and 'clip' in clip:
                                formatted_clips.append(clip['clip'])
                            else:
                                formatted_clips.append(clip)
                        if socket_id:
                            socketio.emit('processing_complete', {
                                'video_path': video_url,
                                'clips': formatted_clips,
                                'thumbnails': thumbnails,
                                'status': 'complete'
                            }, room=socket_id)
                    except Exception as e:
                        print(f"Unexpected error in background processing: {e}")
                        import traceback
                        traceback.print_exc()
                        if socket_id:
                            socketio.emit('progress_update', {
                                'progress': 0,
                                'status': f'Unexpected server error: {str(e)}'
                            }, room=socket_id)
            threading.Thread(target=background_process, daemon=True).start()
            return jsonify({'status': 'processing', 'job_id': job_id}), 202
        print(f"Invalid file type: {file.filename}")
        return jsonify({'error': 'Invalid file type. Allowed types: mp4, avi, mov'}), 400
    except Exception as e:
        print(f"Unexpected error in upload handler: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/clip/<filename>')
def serve_clip(filename):
    """Serve a specific video clip."""
    clip_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(clip_path):
        return send_file(clip_path, mimetype='video/mp4')
    return jsonify({'error': 'Clip not found'}), 404

@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    print(f'Client connected: {request.sid}')

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    print(f'Client disconnected: {request.sid}')

def wait_for_file_complete(filepath, timeout=5.0, interval=0.1, stable_checks=2):
    waited = 0.0
    last_size = -1
    stable_count = 0
    while waited < timeout:
        if os.path.exists(filepath):
            size = os.path.getsize(filepath)
            if size == last_size and size > 0:
                stable_count += 1
                if stable_count >= stable_checks:
                    return True
            else:
                stable_count = 0
            last_size = size
        time.sleep(interval)
        waited += interval
    return False

if __name__ == '__main__':
    # Run the Flask app with SocketIO
    # Disable auto-reloader to prevent interruptions during video processing
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, use_reloader=False)