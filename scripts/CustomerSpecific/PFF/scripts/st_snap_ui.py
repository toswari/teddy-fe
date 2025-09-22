import streamlit as st
import tempfile
import os
from moviepy import VideoFileClip
from time import perf_counter_ns

from clarifai.client import Model
from clarifai.runners.utils.data_types.data_types import Video

import asyncio
import numpy as np
from moviepy import CompositeVideoClip
from concurrent.futures import ThreadPoolExecutor

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
    end_time = key_time + clip_duration if clip_duration else None
    
    video = VideoFileClip(video_path)
    clip = video.subclipped(start_time, end_time)
    
    # Save clip to temporary file
    temp_clip = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
    clip.write_videofile(temp_clip.name)
    clip.close()
    video.close()
    
    return temp_clip.name

def infer_model(url, video_path):
    loop = ensure_event_loop()
    model = Model(url=url)
    try:
        result = model.predict_proba_votes(
                        video=Video(bytes=open(video_path, 'rb').read()),
                        conf_thresh=0,
                        clip_length=16
                    )
        return result
    finally:
        loop.close()

st.set_page_config(layout="wide")
st.title("Video Key Time Extractor")

col1, col2 = st.columns(2)
# Mode selector
mode = col1.selectbox(
    "Select Mode:",
    ["Standard", "Time Synchronization"]
)

uploaded_file = col1.file_uploader("Upload a video", type=['mp4', 'avi', 'mov', 'mkv'], accept_multiple_files=mode == "Time Synchronization")
# weights_path = st.text_input("Model Weights Path", value="snap_model_iter_1012.pth")

action_button = col2.button("Find Key Time and Extract Clip")
clear_button = col2.button("Clear Uploaded Video")

if mode == "Standard" and uploaded_file is not None:
    # Save uploaded file to temporary location
    temp_video = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
    temp_video.write(uploaded_file.read())
    temp_video.close()

    ground_truth_time = float(col2.text_input("Ground Truth Time (seconds)") or 0)
    
    col1, col2 = st.columns(2)
    col1.subheader("Original Video")
    col1.video(temp_video.name)

    model = Model("https://clarifai.com/pff-org/labelstudio-unified/models/snap")

    if action_button:
        with st.spinner("Processing video..."):
            # Find key time
            start = perf_counter_ns()
            key_time, probs, votes = model.predict_proba_votes(
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
            ax1.grid(True, alpha=0.3)

            # Plot votes
            ax2.plot(votes, 'g-', linewidth=2)
            ax2.axvline(x=key_time * 30, color='r', linestyle='--', linewidth=2, label=f'Key Time: {key_time:.2f}s')
            ax2.set_xlabel('Time Steps')
            ax2.set_ylabel('Votes')
            ax2.set_title('Model Votes Over Time')
            ax2.set_xlim(ax1.get_xlim())
            ax2.grid(True, alpha=0.3)

            first_zero_to_left = -1
            for i in range(int(key_time * 30), -1, -1):
                if votes[i] == 0:
                    first_zero_to_left = i
                    break
            
            if first_zero_to_left != -1:
                ax1.axvline(x=first_zero_to_left, color='black', linestyle='--', linewidth=2, label=f'First Zero to Left: {first_zero_to_left/30:.2f}s')
                ax2.axvline(x=first_zero_to_left, color='black', linestyle='--', linewidth=2, label=f'First Zero to Left: {first_zero_to_left/30:.2f}s')

            if ground_truth_time > 0:
                ax1.axvline(x=ground_truth_time * 30, color='g', linestyle='--', linewidth=2, label=f'Ground Truth: {ground_truth_time:.2f}s')
                ax2.axvline(x=ground_truth_time * 30, color='g', linestyle='--', linewidth=2, label=f'Ground Truth: {ground_truth_time:.2f}s')
            
            ax1.legend()
            ax2.legend()

            plt.tight_layout()
            col2.pyplot(fig)

            # Clean up temporary clip file
            os.unlink(clip_path)

            clip_path = extract_clip(temp_video.name, first_zero_to_left / 30, clip_duration=2)
            col2.video(clip_path)
            os.unlink(clip_path)
    
    # Clean up temporary video file when done
    if clear_button:
        os.unlink(temp_video.name)
        st.rerun()
elif mode == "Time Synchronization" and uploaded_file is not None and len(uploaded_file) == 2:
    # Save uploaded files to temporary locations
    temp_videos = []
    for file in uploaded_file:
        temp_video = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
        temp_video.write(file.read())
        temp_video.close()
        temp_videos.append(temp_video.name)

    col1, col2, col3 = st.columns(3)
    col1.subheader("Uploaded Videos")
    for video_path in temp_videos:
        col1.video(video_path)

    if action_button:
        with st.spinner("Processing videos..."):
            import concurrent.futures

            # Process videos in parallel
            key_times = []
            inference_times = []

            def process_video(video_path):
                start = perf_counter_ns()
                key_time, probs, votes = infer_model("https://clarifai.com/pff-org/labelstudio-unified/models/snap", video_path)
                inference_time = (perf_counter_ns() - start) / 1e9
                return key_time, inference_time

            with ThreadPoolExecutor() as executor:
                futures = [executor.submit(process_video, video_path) for video_path in temp_videos]
                
                for future in concurrent.futures.as_completed(futures):
                    key_time, inference_time = future.result()
                    key_times.append(key_time)
                    inference_times.append(inference_time)
            
            col3.subheader("Key Times and Inference Times")
            for i, (kt, it) in enumerate(zip(key_times, inference_times)):
                col3.success(f"Video {i+1}: Key time found: {kt:.2f} seconds. Inference took: {it:.2f} seconds.")

            col2.subheader("Extracted Clips")
            clip_paths = []
            for i, video_path in enumerate(temp_videos):
                clip_path = extract_clip(video_path, key_times[i], clip_duration=None)
                col2.video(clip_path)
                clip_paths.append(clip_path)

            st.subheader("Synced")
            # Stack video clips vertically
            stacked_clips = []
            for clip_path in clip_paths:
                clip = VideoFileClip(clip_path)
                stacked_clips.append(clip)

            # Create stacked video
            stacked_video = CompositeVideoClip(
                [clip.with_position((i * clip.w, 'center')) for i, clip in enumerate(stacked_clips)],
                size=(sum(clip.w for clip in stacked_clips), max(clip.h for clip in stacked_clips))
            )

            # Save stacked video to temporary file
            temp_stacked = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
            stacked_video.write_videofile(temp_stacked.name)

            # Close clips
            for clip in stacked_clips:
                clip.close()
            stacked_video.close()

            st.video(temp_stacked.name)

            # Clean up stacked video file
            os.unlink(temp_stacked.name)

    
    # Clean up temporary video files when done
    if clear_button:
        for video_path in temp_videos:
            os.unlink(video_path)
        st.rerun()