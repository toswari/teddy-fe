import streamlit as st
import tempfile
import os
from moviepy import VideoFileClip
from time import perf_counter_ns

from clarifai.client import Model
from clarifai.runners.utils.data_types.data_types import Video

import asyncio
import numpy as np

def ensure_event_loop():
    try:
        # Check if an event loop is already running
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop, create a new one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop

# Call this function before your gRPC/async operations in Streamlit
loop = ensure_event_loop()
# Now you can use gRPC aio or other async functions
# Example: loop.run_until_complete(your_grpc_async_function())

def extract_clip(video_path, key_time, clip_duration=10):
    """
    Extract a clip around the key time.
    """
    start_time = key_time #max(0, key_time - clip_duration/2)
    end_time = key_time + clip_duration
    
    video = VideoFileClip(video_path)
    clip = video.subclipped(start_time, end_time)
    
    # Save clip to temporary file
    temp_clip = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
    clip.write_videofile(temp_clip.name)
    clip.close()
    video.close()
    
    return temp_clip.name

st.set_page_config(layout="wide")
st.title("Video Key Time Extractor")

uploaded_file = st.file_uploader("Upload a video", type=['mp4', 'avi', 'mov', 'mkv'])
# weights_path = st.text_input("Model Weights Path", value="snap_model_iter_1012.pth")

if uploaded_file is not None:
    # Save uploaded file to temporary location
    temp_video = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
    temp_video.write(uploaded_file.read())
    temp_video.close()
    
    col1, col2 = st.columns(2)
    col1.subheader("Original Video")
    col1.video(temp_video.name)

    if st.button("Find Key Time and Extract Clip"):
        with st.spinner("Processing video..."):
            # Find key time
            start = perf_counter_ns()
            key_time, probs, votes = Model("https://clarifai.com/pff-org/labelstudio-unified/models/snap").predict_proba_votes(
                video=Video(bytes=open(temp_video.name, 'rb').read()),
                conf_thresh=0,
                clip_length=16
            )
            inference_time = (perf_counter_ns() - start) / 1e9
            
            # Extract clip
            clip_path = extract_clip(temp_video.name, key_time, clip_duration=2)

            col2.subheader("Extracted Clip")
            col2.video(clip_path)
            col2.success(f"Key time found: {key_time:.2f} seconds. Inference took: {inference_time:.2f} seconds.")

            # Plot probabilities and votes
            import matplotlib.pyplot as plt

            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))

            # Plot probabilities
            time_steps = np.arange(len(probs))
            ax1.plot(probs, 'b-', linewidth=2)
            ax1.axvline(x=key_time * 30, color='r', linestyle='--', linewidth=2, label=f'Key Time: {key_time:.2f}s')
            ax1.set_xlabel('Time Steps')
            ax1.set_ylabel('Probability')
            ax1.set_title('Model Probabilities Over Time')
            ax1.legend()
            ax1.grid(True, alpha=0.3)

            # Plot votes
            ax2.plot(votes, 'g-', linewidth=2)
            ax2.axvline(x=key_time * 30, color='r', linestyle='--', linewidth=2, label=f'Key Time: {key_time:.2f}s')
            ax2.set_xlabel('Time Steps')
            ax2.set_ylabel('Votes')
            ax2.set_title('Model Votes Over Time')
            ax2.legend()
            ax2.grid(True, alpha=0.3)

            plt.tight_layout()
            col2.pyplot(fig)

            # Clean up temporary clip file
            os.unlink(clip_path)
    
    # Clean up temporary video file when done
    if st.button("Clear"):
        os.unlink(temp_video.name)
        st.rerun()
