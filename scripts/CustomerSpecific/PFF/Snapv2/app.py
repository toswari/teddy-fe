from flask import Flask, request, jsonify, send_file, render_template
import os
from snap_detector import SnapDetector
from werkzeug.utils import secure_filename
import threading
import uuid

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['OUTPUT_FOLDER'] = 'outputs'

# Ensure upload and output directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

# Initialize snap detector
detector = SnapDetector()

# Store processing status
processing_status = {}

def process_video(video_path: str, task_id: str):
    try:
        processing_status[task_id]['status'] = 'processing'
        processing_status[task_id]['progress'] = 10
        
        # Process video
        snap_frame, _, _ = detector.detect_snap(video_path)
        processing_status[task_id]['progress'] = 60
        
        # Generate output files
        base_name = os.path.splitext(os.path.basename(video_path))[0]
        gif_path = os.path.join(app.config['OUTPUT_FOLDER'], f'{base_name}_snap.gif')
        graph_path = os.path.join(app.config['OUTPUT_FOLDER'], f'{base_name}_motion.png')
        
        # Create outputs
        detector.create_snap_gif(video_path, snap_frame, gif_path)
        processing_status[task_id]['progress'] = 80
        
        detector.plot_motion_graph(graph_path)
        
        processing_status[task_id].update({
            'status': 'completed',
            'progress': 100,
            'result': {
                'snap_frame': snap_frame,
                'gif_url': f'/output/{os.path.basename(gif_path)}',
                'graph_url': f'/output/{os.path.basename(graph_path)}'
            }
        })
        
    except Exception as e:
        processing_status[task_id].update({
            'status': 'error',
            'error': str(e)
        })
    finally:
        # Clean up uploaded file
        if os.path.exists(video_path):
            os.remove(video_path)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/detect-snap', methods=['POST'])
def detect_snap():
    if 'video' not in request.files:
        return jsonify({'error': 'No video file provided'}), 400
    
    video = request.files['video']
    if video.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if not video.filename.lower().endswith(('.mp4', '.avi', '.mov')):
        return jsonify({'error': 'Invalid file format'}), 400
    
    # Generate unique task ID
    task_id = str(uuid.uuid4())
    
    try:
        # Save uploaded video
        video_path = os.path.join(app.config['UPLOAD_FOLDER'], 
                                secure_filename(video.filename))
        video.save(video_path)
        
        # Initialize status
        processing_status[task_id] = {
            'status': 'starting',
            'progress': 0
        }
        
        # Start processing in background
        thread = threading.Thread(target=process_video, args=(video_path, task_id))
        thread.start()
        
        return jsonify({'task_id': task_id})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/status/<task_id>')
def get_status(task_id):
    if task_id not in processing_status:
        return jsonify({'error': 'Task not found'}), 404
    return jsonify(processing_status[task_id])

@app.route('/output/<filename>')
def output_file(filename):
    return send_file(os.path.join(app.config['OUTPUT_FOLDER'], filename))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3330) 