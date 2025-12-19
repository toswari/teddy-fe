import os

# Set HOME environment variable for Windows if not set
if os.name == "nt" and "HOME" not in os.environ:
    os.environ["HOME"] = os.path.expanduser("~")

import json
import time
import cv2
import logging
from PIL import Image
import io
import threading
from threading import Thread
from queue import Queue, Empty
import gc
import traceback

# Now import Clarifai
from clarifai.client.model import Model
from clarifai.client.input import Inputs

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from clarifai.client.model import Model
    from clarifai.client.input import Inputs
except ImportError as e:
    logger.error(f"Failed to import Clarifai client: {e}")
    raise


class TimeoutError(Exception):
    pass


def run_with_timeout(func, args=(), kwargs={}, timeout_seconds=4):
    result_queue = Queue()

    def wrapper():
        try:
            result = func(*args, **kwargs)
            result_queue.put(("success", result))
        except Exception as e:
            result_queue.put(("error", e))

    thread = Thread(target=wrapper)
    thread.daemon = True
    thread.start()
    thread.join(timeout_seconds)

    if thread.is_alive():
        return "timeout", None

    if not result_queue.empty():
        status, value = result_queue.get()
        if status == "success":
            return "success", value
        else:
            return "error", value
    return "timeout", None


def process_model_prediction(model, inputs, timeout_seconds=16):
    for attempt in range(6):
        try:
            status, result = run_with_timeout(
                model.predict,
                kwargs={"inputs": inputs},
                timeout_seconds=timeout_seconds,
            )

            if status == "success":
                return result.outputs[0] if hasattr(result, "outputs") else result[0]
            elif status == "timeout":
                if attempt == 2:
                    logger.error(
                        f"Model prediction failed after {timeout_seconds}s and 3 attempts"
                    )
                    return f"Error: Timeout after {timeout_seconds}s and 3 attempts"
                wait_time = 2**attempt
                logger.info(
                    f"Prediction timeout, retry {attempt + 1}/3 after {wait_time}s"
                )
                time.sleep(wait_time)
            else:  # status == "error"
                if attempt == 2:
                    logger.error(
                        f"Model prediction error after 3 attempts: {str(result)}"
                    )
                    return f"Error: {str(result)}"
                wait_time = 2**attempt
                logger.info(
                    f"Prediction error, retry {attempt + 1}/3 after {wait_time}s: {str(result)}"
                )
                time.sleep(wait_time)
        except Exception as e:
            if attempt == 2:
                logger.error(
                    f"Unexpected error in prediction after 3 attempts: {str(e)}"
                )
                return f"Error: {str(e)}"
            wait_time = 2**attempt
            logger.info(
                f"Unexpected error, retry {attempt + 1}/3 after {wait_time}s: {str(e)}"
            )
            time.sleep(wait_time)


def process_frame(
    frame, model_config, prompt, previous_frames=None, max_context_frames=3
):
    """Process a single frame with the model, including context from previous frames."""
    try:
        # Convert frame to PIL Image
        img = Image.fromarray(frame)

        # Resize if needed
        if img.width > 1000 or img.height > 1000:
            ratio = min(1000 / img.width, 1000 / img.height)
            new_size = (int(img.width * ratio), int(img.height * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)

        # Convert to bytes
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format="JPEG", quality=100)
        image_bytes = img_byte_arr.getvalue()

        # Initialize model
        model = Model(
            url=model_config["url"],
            pat=model_config["pat"],
            user_id=model_config["user_id"],
        )

        # Prepare context from previous frames (optimized for MiniCPM)
        context_text = ""
        if previous_frames:
            # Get the last 3 frames for context (reduced for MiniCPM efficiency)
            recent_frames = previous_frames[-3:]
            context_text = "\n\nPREVIOUS CONTEXT:\n"
            for idx, prev_frame in enumerate(recent_frames):
                if not prev_frame.get("error"):
                    timestamp = prev_frame.get("timestamp", 0)
                    # Extract key fields only for concise context
                    key_info = []
                    if "event" in prev_frame:
                        key_info.append(f"Event: {prev_frame['event']}")
                    if "category" in prev_frame:
                        key_info.append(f"Category: {prev_frame['category']}")
                    if "suspicious_behaviors" in prev_frame:
                        key_info.append(
                            f"Behaviors: {prev_frame['suspicious_behaviors']}"
                        )
                    if "reasoning" in prev_frame:
                        key_info.append(f"Reason: {prev_frame['reasoning'][:100]}...")

                    if key_info:
                        context_text += f"[{timestamp:.1f}s] {' | '.join(key_info)}\n"

        # Combine context with the original prompt (optimized structure for MiniCPM)
        if context_text:
            enhanced_prompt = f"{prompt}{context_text}\n\nAnalyze the current frame:"
        else:
            enhanced_prompt = prompt

        # Create input
        input_obj = Inputs.get_multimodal_input(
            input_id="", image_bytes=image_bytes, raw_text=enhanced_prompt
        )

        # Process with model
        output = process_model_prediction(model, [input_obj])

        if isinstance(output, str) and output.startswith("Error:"):
            return {"error": output}

        try:
            # Parse the response
            response_text = output.data.text.raw
            # Find JSON object in the text
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            if json_start == -1 or json_end == 0:
                return {"error": "No JSON found in response"}

            json_str = response_text[json_start:json_end]
            result = json.loads(json_str)

            # Add timestamp
            result["timestamp"] = time.time()
            return result

        except Exception as e:
            logger.error(f"Error parsing response: {str(e)}")
            logger.error(f"Raw response: {response_text}")
            return {"error": f"Error parsing response: {str(e)}"}

    except Exception as e:
        logger.error(f"Error processing frame: {str(e)}")
        return {"error": str(e)}
    finally:
        if "img_byte_arr" in locals():
            img_byte_arr.close()
        if "img" in locals():
            img.close()
        gc.collect()


def extract_frames(video_path, fps=1):
    """Extract frames from video at specified FPS."""
    try:
        logger.info(f"Opening video file: {video_path}")
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.error(f"Failed to open video file: {video_path}")
            raise ValueError("Could not open video file")

        # Get video properties
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        video_fps = cap.get(cv2.CAP_PROP_FPS)
        duration = total_frames / video_fps

        logger.info(
            f"Video properties - Total frames: {total_frames}, FPS: {video_fps}, Duration: {duration}"
        )

        # Calculate frame interval
        frame_interval = int(video_fps / fps)
        if frame_interval < 1:
            frame_interval = 1

        logger.info(f"Extracting frames with interval: {frame_interval}")

        frames = []
        timestamps = []
        frame_count = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                logger.info("Reached end of video")
                break

            if frame_count % frame_interval == 0:
                # Convert BGR to RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frames.append(frame_rgb)
                timestamps.append(frame_count / video_fps)
                logger.debug(
                    f"Extracted frame {frame_count} at timestamp {frame_count / video_fps}"
                )

            frame_count += 1

        cap.release()
        logger.info(f"Successfully extracted {len(frames)} frames")
        return frames, timestamps, duration

    except Exception as e:
        logger.error(f"Error extracting frames: {str(e)}")
        logger.error(traceback.format_exc())
        return [], [], 0


def analyze_video(video_path, model_config, prompt, stream=False, fps=1.0):
    """Analyze video frames and return results. If stream=True, yield progress after each frame."""
    try:
        logger.info("Extracting frames from video...")
        frames, timestamps, duration = extract_frames(video_path, fps=fps)

        if not frames:
            if stream:
                yield {"error": "No frames extracted from video"}
                return
            return {"error": "No frames extracted from video"}

        logger.info(f"Processing {len(frames)} frames...")
        results = []
        processed_frames = []  # Store processed frames for context

        for i, (frame, timestamp) in enumerate(zip(frames, timestamps)):
            logger.info(
                f"Processing frame {i + 1}/{len(frames)} at timestamp {timestamp:.2f}s"
            )

            # Process frame with context from previous frames
            frame_result = process_frame(
                frame=frame,
                model_config=model_config,
                prompt=prompt,
                previous_frames=processed_frames,
            )

            # Add timestamp to the result
            frame_result["timestamp"] = timestamp

            # Add to results and processed frames
            results.append(frame_result)
            processed_frames.append(frame_result)

            # Log progress
            if not frame_result.get("error"):
                logger.info(
                    f"Frame {i + 1} processed successfully: {json.dumps(frame_result)}"
                )
            else:
                logger.warning(
                    f"Error processing frame {i + 1}: {frame_result.get('error')}"
                )

            if stream:
                # Yield progress for streaming
                yield {
                    "frame": i + 1,
                    "total_frames": len(frames),
                    "result": frame_result,
                    "duration": duration,
                }

        final_result = {
            "frames": results,
            "duration": duration,
            "total_frames": len(frames),
        }
        if stream:
            yield {"done": True, "result": final_result}
            return
        return final_result

    except Exception as e:
        logger.error(f"Error analyzing video: {str(e)}")
        logger.error(traceback.format_exc())
        if stream:
            yield {"error": str(e)}
            return
        return {"error": str(e)}
    finally:
        gc.collect()


def generate_summary(frame_results):
    """Generate a summary of the frame analysis."""
    try:
        # Count categories
        categories = {}
        for result in frame_results:
            if "category" in result:
                cat = result["category"]
                categories[cat] = categories.get(cat, 0) + 1

        # Find most common category
        most_common = (
            max(categories.items(), key=lambda x: x[1])
            if categories
            else ("unknown", 0)
        )

        # Calculate average confidence
        confidences = [
            r.get("confidence", 0) for r in frame_results if "confidence" in r
        ]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0

        return {
            "primary_category": most_common[0],
            "category_distribution": categories,
            "average_confidence": avg_confidence,
            "total_frames": len(frame_results),
        }

    except Exception as e:
        logger.error(f"Error generating summary: {str(e)}")
        return {"error": str(e)}


def test_connection(model_config):
    """Test the connection to Clarifai API."""
    try:
        model = Model(
            url=model_config["url"],
            pat=model_config["pat"],
            user_id=model_config.get("user_id"),
        )
        return True
    except Exception as e:
        logger.error(f"Failed to connect to Clarifai: {str(e)}")
        return False


if __name__ == "__main__":
    # Test configuration
    model_config = {
        "name": "MiniCPM-o-2_6-language",
        "url": "https://clarifai.com/openbmb/miniCPM/models/MiniCPM-o-2_6-language",
        "pat": "295ac5c37ad44f84a18d46e1198813b5",
        "user_id": "mulder",
    }

    # Test connection
    if test_connection(model_config):
        print("Successfully connected to Clarifai API")
    else:
        print("Failed to connect to Clarifai API")
