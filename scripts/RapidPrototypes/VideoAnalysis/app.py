from flask import Flask, request, render_template, jsonify, Response, session, stream_with_context, send_from_directory
import os
import logging
from datetime import datetime
from frame_analyzer import analyze_video, test_connection
import json
from rag_engine import VideoAnalysisRAG
from werkzeug.utils import secure_filename
import traceback
from prompts_config import PROMPTS
from flask_cors import CORS

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='static')
CORS(app)  # Enable CORS for all routes
app.secret_key = os.urandom(24)  # Required for session
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # 200MB max file size
app.config['UPLOAD_FOLDER'] = 'uploads'

# Ensure upload and static directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('static', exist_ok=True)

# Load MODEL_CONFIG from model_configs.json
with open('model_configs.json', 'r') as f:
    MODEL_CONFIG = json.load(f)

# Initialize RAG engine with default config (credentials will be added per request)
rag_engine = VideoAnalysisRAG(MODEL_CONFIG)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        if 'video' not in request.files:
            return jsonify({'error': 'No video file provided'}), 400
        
        video_file = request.files['video']
        if video_file.filename == '':
            return jsonify({'error': 'No video file selected'}), 400

        # Get category and prompt
        category = request.form.get('category', 'general')
        prompt = request.form.get('prompt', '').strip()
        if not prompt:
            prompt = PROMPTS.get(category, PROMPTS['general'])
        
        if not prompt:
            return jsonify({'error': 'No analysis prompt provided'}), 400

        # Save video file
        filename = secure_filename(video_file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        video_file.save(filepath)
        
        logger.info(f"Starting analysis for video: {filepath}")
        logger.info(f"Category: {category}")
        logger.info(f"Using prompt: {prompt}")

        # Analyze video
        results = analyze_video(
            video_path=filepath,
            model_config=MODEL_CONFIG,
            prompt=prompt
        )

        if 'error' in results:
            return jsonify({'error': results['error']}), 500

        # Save results to JSON file
        results_path = os.path.join(app.config['UPLOAD_FOLDER'], f'results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
        with open(results_path, 'w') as f:
            json.dump(results, f, indent=2)

        logger.info(f"Analysis complete. Results saved to: {results_path}")

        # Clean up video file
        try:
            os.remove(filepath)
            logger.info(f"Cleaned up video file: {filepath}")
        except Exception as e:
            logger.warning(f"Failed to clean up video file: {e}")

        # Return the entire results object
        return jsonify(results)

    except Exception as e:
        logger.error(f"Error during analysis: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/ask', methods=['POST'])
def ask_question():
    try:
        data = request.json
        if not data or 'question' not in data or 'results' not in data:
            return jsonify({'error': 'Missing question or results data'}), 400

        question = data['question']
        results = data['results']

        # Get answer from RAG engine
        answer = rag_engine.ask_question(question, results)
        
        return jsonify({'answer': answer})
    except Exception as e:
        logging.error(f"Error in ask endpoint: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        question = data.get('question')
        analysis_results = data.get('analysis_results')
        username = data.get('username')
        pat = data.get('pat')
        
        if not question or not analysis_results:
            return jsonify({'error': 'Missing question or analysis results'}), 400
            
        if not username or not pat:
            return jsonify({'error': 'Missing credentials'}), 400
            
        # Update RAG engine with credentials
        rag_engine.update_credentials(username, pat)
            
        # Store the question and analysis results in the session
        session['current_question'] = question
        session['current_analysis'] = {'results': analysis_results}
        session['username'] = username
        session['pat'] = pat
        
        logger.info(f"Stored question: {question}")
        logger.info(f"Stored analysis results: {json.dumps(analysis_results, indent=2)}")
        
        return jsonify({'status': 'ok'})
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/chat/stream/<question>', methods=['GET'])
def chat_stream(question):
    try:
        # Get the stored analysis results and credentials from the session
        analysis_results = session.get('current_analysis')
        username = session.get('username')
        pat = session.get('pat')
        
        if not analysis_results:
            logger.error("No analysis results found in session")
            return jsonify({'error': 'No analysis results found'}), 400
            
        if not username or not pat:
            logger.error("No credentials found in session")
            return jsonify({'error': 'No credentials found'}), 400
            
        # Update RAG engine with credentials
        rag_engine.update_credentials(username, pat)
            
        logger.info(f"Starting stream for question: {question}")
        logger.info(f"Using analysis results: {json.dumps(analysis_results, indent=2)}")
            
        def generate():
            try:
                # Get streaming response from RAG engine
                for chunk in rag_engine.ask_question(question, analysis_results):
                    if isinstance(chunk, str):
                        logger.info(f"Streaming chunk: {chunk}")
                        yield f"data: {json.dumps({'chunk': chunk})}\n\n"
                    elif hasattr(chunk, 'text'):
                        logger.info(f"Streaming chunk with text: {chunk.text}")
                        yield f"data: {json.dumps({'chunk': chunk.text})}\n\n"
            except Exception as e:
                logger.error(f"Error in chat stream: {str(e)}")
                logger.error(traceback.format_exc())
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
        
        return Response(generate(), mimetype='text/event-stream')
        
    except Exception as e:
        logger.error(f"Error in chat stream endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/analyze/stream', methods=['POST'])
def analyze_stream():
    try:
        if 'video' not in request.files:
            return Response('data: {"error": "No video file provided"}\n\n', mimetype='text/event-stream')
        
        video_file = request.files['video']
        if video_file.filename == '':
            return Response('data: {"error": "No video file selected"}\n\n', mimetype='text/event-stream')

        # Get credentials from form
        username = request.form.get('username')
        pat = request.form.get('pat')
        if not username or not pat:
            return Response('data: {"error": "Username and PAT are required"}\n\n', mimetype='text/event-stream')

        # Update model config with credentials
        model_config = MODEL_CONFIG.copy()
        model_config['user_id'] = username
        model_config['pat'] = pat

        # Update RAG engine with new credentials
        rag_engine.update_credentials(username, pat)

        # Get category and prompt
        category = request.form.get('category', 'general')
        prompt = request.form.get('prompt', '').strip()
        if not prompt:
            prompt = PROMPTS.get(category, PROMPTS['general'])
        if not prompt:
            return Response('data: {"error": "No analysis prompt provided"}\n\n', mimetype='text/event-stream')

        # Save video file
        filename = secure_filename(video_file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        video_file.save(filepath)

        logger.info(f"Starting streaming analysis for video: {filepath}")
        logger.info(f"Category: {category}")
        logger.info(f"Using prompt: {prompt}")

        def generate():
            try:
                final_results = None
                for progress in analyze_video(
                    video_path=filepath,
                    model_config=model_config,
                    prompt=prompt,
                    stream=True
                ):
                    # Store the final results when we get them
                    if isinstance(progress, dict) and 'results' in progress:
                        final_results = progress
                    
                    # Ensure each chunk is properly formatted and flushed
                    chunk = f"data: {json.dumps(progress)}\n\n"
                    logger.info(f"Sending chunk: {chunk.strip()}")
                    yield chunk
                
                # Send final completion message with results
                if final_results:
                    completion_msg = {
                        'status': 'complete',
                        'results': final_results
                    }
                    yield f"data: {json.dumps(completion_msg)}\n\n"
                else:
                    yield f"data: {json.dumps({'status': 'complete'})}\n\n"
                    
            finally:
                try:
                    os.remove(filepath)
                    logger.info(f"Cleaned up video file: {filepath}")
                except Exception as e:
                    logger.warning(f"Failed to clean up video file: {e}")

        response = Response(
            stream_with_context(generate()),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'X-Accel-Buffering': 'no'  # Disable proxy buffering
            }
        )
        return response

    except Exception as e:
        logger.error(f"Error during streaming analysis: {str(e)}")
        logger.error(traceback.format_exc())
        return Response(f'data: {{"error": "{str(e)}"}}\n\n', mimetype='text/event-stream')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True) 