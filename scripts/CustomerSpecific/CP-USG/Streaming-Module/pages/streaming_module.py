import streamlit as st
import cv2
import numpy as np
import threading
import time
from queue import Queue, Empty
import os
from typing import Optional, List, Dict, Any
import tempfile
import asyncio
import json
from datetime import datetime
from urllib.parse import urlparse
try:
    import imageio_ffmpeg  # ensure ffmpeg binary is available for imageio
    _ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()
    if _ffmpeg_bin:
        os.environ.setdefault("IMAGEIO_FFMPEG_EXE", _ffmpeg_bin)
except Exception:
    # Fallback silently; imageio will attempt its own resolution
    pass
from clarifai.client.auth.helper import ClarifaiAuthHelper
from clarifai.client.model import Model
from clarifai.client.app import App
from clarifai.client.user import User
from clarifai.modules.css import ClarifaiStreamlitCSS
from google.protobuf import json_format
import hashlib
from dotenv import load_dotenv
from collections import deque

load_dotenv()

# Hardcoded initial prebuffer to avoid looking stuck even when user buffer is small/zero
INITIAL_PREBUFFER_SECONDS = 3.0

def hash_url(url):
    return hashlib.md5(url.encode()).hexdigest()[:8]

def sanitize_url(url: str) -> str:
    """Return the URL unchanged. We will try https upgrades as an alternative when opening.
    Avoid forcing https to preserve endpoints like plain http HLS/RTSP.
    """
    return url

def is_http_url(url: str) -> bool:
    return url.startswith("http://") or url.startswith("https://")

def is_rtsp_url(url: str) -> bool:
    return url.startswith("rtsp://")

def ensure_event_loop_in_thread():
    """Ensure an asyncio event loop exists in the current thread.
    Some I/O libs expect an event loop even when used synchronously.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop
    return asyncio.get_running_loop()

@st.cache_data(show_spinner=False, ttl=60)
def list_models(user_id: str, app_id: Optional[str], portal_base_host: Optional[str] = "clarifai.com"):
    """Return models available in the user's current Clarifai app.

    If app_id is falsy (empty), list models across all apps for the user.

    Output: List[{"Name": <model_id>, "Label": <display>, "URL": <model_url>, "ids": {...}}]
    """
    try:
        if not user_id:
            return []
        usermodels = []
        if app_id:
            apps_to_check = [(app_id, App(user_id=user_id, app_id=app_id))]
        else:
            # Enumerate all apps for the user
            apps_to_check = []
            try:
                for app in User(user_id=user_id).list_apps():
                    app_id_item = getattr(app, "app_id", None) or getattr(app, "id", None)
                    apps_to_check.append(
                        (app_id_item, App(user_id=user_id, app_id=app_id_item))
                    )
            except Exception:
                # If listing apps fails, fall back to none
                apps_to_check = []

        for app_id_item, app_obj in apps_to_check:
            if not app_id_item:
                continue
            try:
                all_models = list(app_obj.list_models())
            except Exception:
                continue
            for model in all_models:
                model_id = getattr(model, "id", None) or getattr(model, "model_id", None)
                if not model_id:
                    continue
                base_host = portal_base_host or "clarifai.com"
                model_url = f"https://{base_host}/{user_id}/{app_id_item}/models/{model_id}"
                usermodels.append({
                    "Name": model_id,
                    "Label": f"{app_id_item}:{model_id}",
                    "URL": model_url,
                    "ids": {"user_id": user_id, "app_id": app_id_item, "model_id": model_id},
                })
        # Provide a stable label for single-app case as well
        if app_id and usermodels:
            for m in usermodels:
                m.setdefault("Label", m["Name"])  # Label == Name when single app
        usermodels.sort(key=lambda m: m.get("Label", m["Name"]).lower())
        return usermodels
    except Exception as e:
        # Return empty on errors; caller can surface message
        return []

def draw_box_corners(frame, left, top, right, bottom, color, thickness=1, corner_length=15):
    cv2.line(frame, (left, top), (left + corner_length, top), color, thickness)  # Top-left horizontal
    cv2.line(frame, (left, top), (left, top + corner_length), color, thickness)  # Top-left vertical
    cv2.line(frame, (right, top), (right - corner_length, top), color, thickness)  # Top-right horizontal
    cv2.line(frame, (right, top), (right, top + corner_length), color, thickness)  # Top-right vertical
    cv2.line(frame, (left, bottom), (left + corner_length, bottom), color, thickness)  # Bottom-left horizontal
    cv2.line(frame, (left, bottom), (left, bottom - corner_length), color, thickness)  # Bottom-left vertical
    cv2.line(frame, (right, bottom), (right - corner_length, bottom), color, thickness)  # Bottom-right horizontal
    cv2.line(frame, (right, bottom), (right, bottom - corner_length), color, thickness)  # Bottom-right vertical

def extract_regions_from_response(prediction_response) -> List[Dict[str, Any]]:
    regions_out: List[Dict[str, Any]] = []
    outputs = getattr(prediction_response, "outputs", None) or []
    if not outputs:
        return regions_out
    data = getattr(outputs[0], "data", None)
    regions = getattr(data, "regions", None) or []
    for region in regions:
        bbox = region.region_info.bounding_box
        concepts = [(c.name, float(c.value)) for c in getattr(region.data, "concepts", [])]
        regions_out.append({
            "bbox": (
                float(bbox.top_row), float(bbox.left_col), float(bbox.bottom_row), float(bbox.right_col)
            ),
            "concepts": concepts,
        })
    return regions_out

def draw_regions_on_frame(frame, regions: List[Dict[str, Any]], det_threshold: float, color=(0, 255, 0), model_name: Optional[str] = None):
    out = frame.copy()
    if model_name:
        cv2.putText(out, model_name, (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2, cv2.LINE_AA)
    h, w = out.shape[:2]
    for reg in regions or []:
        top_row, left_col, bottom_row, right_col = reg["bbox"]
        left = int(left_col * w)
        top = int(top_row * h)
        right = int(right_col * w)
        bottom = int(bottom_row * h)
        draw_box_corners(out, left, top, right, bottom, color)
        for name, value in reg.get("concepts", []):
            if value >= det_threshold:
                text_position = (left + (right - left) // 4, max(10, top - 10))
                cv2.putText(out, f"{name}:{value:.4f}", text_position, cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2, cv2.LINE_AA)
    return out

def run_model_inference(det_threshold, frame, model_option, color=(0, 255, 0)):
    """Run inference and draw boxes. Never call Streamlit APIs here.

    Returns: (processed_frame, prediction_response, regions)
    Raises: Exception on failure
    """
    frame_bytes = cv2.imencode('.jpg', frame)[1].tobytes()
    # Prefer ID-based initialization to honor custom base_url/PAT
    if isinstance(model_option, dict) and "ids" in model_option:
        ids = model_option["ids"]
        detector_model = Model(
            user_id=ids.get("user_id"),
            app_id=ids.get("app_id"),
            model_id=ids.get("model_id"),
        )
    else:
        model_url = model_option['URL']
        detector_model = Model(url=model_url)
    prediction_response = detector_model.predict_by_bytes(frame_bytes, input_type="image")
    regions = extract_regions_from_response(prediction_response)
    processed = draw_regions_on_frame(frame, regions, det_threshold, color=color, model_name=model_option['Name'])
    return processed, prediction_response, regions

def verify_json_responses(sources):
    """Offer a download button for the last 100 detections per video.

    Sources is a list of video URLs or filenames corresponding to indices.
    """
    json_by_video = st.session_state.get("json_by_video", {})
    if not json_by_video:
        return
    export = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "videos": []
    }
    for idx in sorted(json_by_video.keys()):
        frames = json_by_video[idx][-100:]
        export["videos"].append({
            "index": idx + 1,
            "source": sources[idx] if idx < len(sources) else None,
            "detections": frames
        })
    data = json.dumps(export, indent=2)
    file_name = f"detections_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    st.download_button(
        label="Download detections (JSON)",
        data=data,
        file_name=file_name,
        mime="application/json"
    )

st.set_page_config(layout="wide")
ClarifaiStreamlitCSS.insert_default_css(st)

auth = ClarifaiAuthHelper.from_streamlit(st)
userDataObject = auth.get_user_app_id_proto()

# Allow user to provide custom Clarifai credentials
with st.expander("Authentication (Clarifai)", expanded=False):
    default_user_id = getattr(userDataObject, "user_id", "")
    default_app_id = getattr(userDataObject, "app_id", "")

    if "auth_use_custom" not in st.session_state:
        st.session_state.auth_use_custom = False
        st.session_state.auth_user_id = default_user_id
        st.session_state.auth_app_id = default_app_id
        st.session_state.auth_base_url = os.environ.get("CLARIFAI_BASE_URL", "https://api.clarifai.com")
        st.session_state.auth_pat = os.environ.get("CLARIFAI_PAT", "")
        # Derive a default portal host from base URL (strip leading 'api.' if present)
        try:
            parsed = urlparse(st.session_state.auth_base_url)
            host = parsed.hostname or "api.clarifai.com"
            if host.startswith("api."):
                host = host[len("api."):]
            st.session_state.portal_base_host = host
        except Exception:
            st.session_state.portal_base_host = "clarifai.com"

    st.session_state.auth_use_custom = st.checkbox("Use custom credentials", value=st.session_state.auth_use_custom)
    
    st.session_state.auth_user_id = st.text_input("User ID", value=st.session_state.auth_user_id)
    st.session_state.auth_app_id = st.text_input("App ID", value=st.session_state.auth_app_id)
    st.session_state.auth_pat = st.text_input("PAT (Personal Access Token)", value=st.session_state.auth_pat, type="password")
    st.session_state.portal_base_host = st.text_input(
        "Portal base host",
        value=st.session_state.get("portal_base_host", "clarifai.com"),
        help="Used to build model URLs, e.g. clarifai.com, dev.clarifai.com, or a custom domain like dev2.example.com"
    )
    st.session_state.auth_base_url = st.text_input("Portal base API endpoint", value=st.session_state.auth_base_url, help="e.g. https://api.clarifai.com")
    if st.button("Apply credentials"):
        if st.session_state.auth_use_custom:
            if not (st.session_state.auth_user_id and st.session_state.auth_pat):
                st.error("User ID and PAT are required when using custom credentials. App ID is optional.")
            else:
                os.environ["CLARIFAI_PAT"] = st.session_state.auth_pat
                if st.session_state.auth_base_url:
                    os.environ["CLARIFAI_BASE_URL"] = st.session_state.auth_base_url
                try:
                    list_models.clear()
                except Exception:
                    pass
                st.success("Credentials applied. Reloading...")
                try:
                    st.experimental_rerun()
                except Exception:
                    pass
        else:
            # Revert to defaults provided by the helper / environment
            for k in ("CLARIFAI_PAT", "CLARIFAI_BASE_URL"):
                if k in os.environ:
                    del os.environ[k]
            try:
                list_models.clear()
            except Exception:
                pass
            st.success("Using default credentials. Reloading...")
            try:
                st.experimental_rerun()
            except Exception:
                pass

st.title("Streaming Video Processing")

# Usage & Supported Sources
with st.expander("Usage & Supported Sources", expanded=False):
    st.markdown(
        """
        Supported inputs:
        - HTTP(S) files: mp4, mov, mkv, avi (e.g. https://.../video.mp4)
        - HLS live streams: .m3u8 playlists (e.g. https://.../playlist.m3u8)
        - RTSP cameras: rtsp://host:port/path (TCP transport)

        Tips:
        - Live streams benefit from a playback buffer. Increase "Playback buffer (seconds)" for smoother viewing at the cost of latency.
        - "Max display FPS" throttles rendering; if your source FPS is lower, consider reducing this to avoid buffer drain.
        - "Skip model inference" helps isolate decode issues. If video doesn’t show, try enabling it to test the stream.
        - Use the Stop button to end processing. Then use "Download detections (JSON)" to export the last 100 detections per video.

        Troubleshooting:
        - For HLS/RTSP that stall, try increasing buffer seconds or lowering max display FPS.
        - Ensure Clarifai credentials are valid and a model is selected per video.
        """
    )

video_option = st.radio("Choose Video Input:", ("Supported Video URLs","Local Video Files"), horizontal=True)

if video_option == "Supported Video URLs":
    video_urls = st.text_area(
        "Enter video URLs (one per line):",
        value="http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4\nhttp://playertest.longtailvideo.com/adaptive/wowzaid3/playlist.m3u8\nrtsp://example.com:554/stream",
        help="One URL per line. Supports HTTP(S) files (mp4/mov/mkv/avi), HLS (.m3u8) live streams, and RTSP (rtsp://)."
    )
    frame_skip = st.slider(
        "Select how many frames to skip:",
        min_value=1, max_value=120, value=30,
        help="Run inference every N frames (all frames are displayed). Lower values increase model load and latency."
    )
    det_threshold = st.slider(
        "Select detection threshold:",
        min_value=0.01, max_value=1.00, value=0.5,
        help="Only show labels/concepts with confidence >= threshold."
    )
    buffer_seconds = st.slider(
        "Playback buffer (seconds)",
        min_value=0, max_value=15, value=10,
        help="Adds constant playback delay to smooth network jitter. Increase for HLS/RTSP; set 0 for lowest latency."
    )
    max_display_fps = st.slider(
        "Max display FPS", min_value=5, max_value=60, value=15,
        help="Upper bound on rendering rate. If the source is slower, reduce this to help the buffer remain filled."
    )
    skip_inference = st.checkbox(
        "Skip model inference (show raw frames)", value=False,
        help="Decode-only mode to validate streams without calling the model."
    )
    # Fetch models dynamically for current or custom user/app
    if st.session_state.get("auth_use_custom"):
        user_id = st.session_state.get("auth_user_id")
        app_id = st.session_state.get("auth_app_id")
    else:
        user_id = getattr(userDataObject, "user_id", None)
        app_id = getattr(userDataObject, "app_id", None)
    with st.spinner("Loading models..."):
        available_models = list_models(user_id, app_id, st.session_state.get("portal_base_host", "clarifai.com"))
    cols_actions = st.columns([1,1,6])
    with cols_actions[0]:
        if st.button("Refresh Models"):
            list_models.clear()  # clear cache
            available_models = list_models(user_id, app_id, st.session_state.get("portal_base_host", "clarifai.com"))
    with cols_actions[1]:
        # Cooperative stop flag across reruns
        if "stop_event" not in st.session_state:
            st.session_state.stop_event = threading.Event()
        if st.button("Stop Processing", type="secondary"):
            st.session_state.stop_event.set()
    # Always offer latest detections download (if any), even outside processing
    try:
        sources_preview = [u.strip() for u in video_urls.split('\n') if u.strip()]
        verify_json_responses(sources_preview)
    except Exception:
        pass
    # App override if cross-app listing returns nothing (apply before empty check)
    app_override = st.text_input(
        "App ID override (optional): load models from this app if cross-app listing is empty",
        value="", key="app_override_urls",
        help="If your user has multiple apps and cross-app listing is empty, specify a single App ID to pull models from."
    )
    if not available_models and app_override.strip():
        available_models = list_models(user_id, app_override.strip(), st.session_state.get("portal_base_host", "clarifai.com"))
    # Fallback to helper's default app if still empty and we have one
    if not available_models and not app_override.strip():
        helper_app_id = getattr(userDataObject, "app_id", None)
        if helper_app_id:
            available_models = list_models(user_id, helper_app_id, st.session_state.get("portal_base_host", "clarifai.com"))
    # Type-ahead style filter for large model sets
    model_filter = st.text_input(
        "Filter models (type to narrow list)",
        value=st.session_state.get("model_filter", ""),
        key="model_filter",
        placeholder="e.g. app-id or model-id",
        help="Type to filter by app or model ID. Each video can use a different model."
    )
    if model_filter:
        _q = model_filter.strip().lower()
        filtered_models = [m for m in available_models if _q in m.get("Label", m["Name"]).lower()]
        st.caption(f"Showing {len(filtered_models)} of {len(available_models)} models matching '{model_filter}'.")
    else:
        filtered_models = available_models
    if not available_models:
        st.warning("No models found in your Clarifai app. Create or deploy a model in your app, then click Refresh Models.")
        st.stop()
    url_list = [url.strip() for url in video_urls.split('\n') if url.strip()]
    # Per-video model selection from user's available models (Standard URLs)
    model_options = []
    # Fallback if filter yields no results
    if not filtered_models:
        st.info("No models match the current filter. Showing all models.")
        filtered_models = available_models
    model_labels = [m.get("Label", m["Name"]) for m in filtered_models]
    for idx, url in enumerate(url_list):
        sel_label = st.selectbox(
            f"Select a model for Video {idx + 1}:",
            model_labels,
            key=f"model_{idx}_{hash_url(url)}"
        )
        model_options.append(next(m for m in filtered_models if m.get("Label", m["Name"]) == sel_label))

    if st.button("Process Videos"):
        frame_placeholder = st.empty()
        error_placeholder = st.empty()
        status_placeholder = st.empty()
        try:
            # Clear previous stop signal
            if "stop_event" not in st.session_state:
                st.session_state.stop_event = threading.Event()
            else:
                st.session_state.stop_event.clear()
            # Reset rolling JSON buffers for this run
            st.session_state["json_by_video"] = {}
            # Thread-safe queues for frames and messages
            target_q_size = max(2, int((buffer_seconds if buffer_seconds else 0) * 30 + 60))
            frame_queues = [Queue(maxsize=target_q_size) for _ in range(len(url_list))]
            msg_queue = Queue()  # tuples: (kind, index, payload)

            def safe_put(q: Queue, item):
                try:
                    q.put_nowait(item)
                except Exception:
                    try:
                        q.get_nowait()
                    except Exception:
                        pass
                    try:
                        q.put_nowait(item)
                    except Exception:
                        pass

            def process_video(video_url, index, model_option, stop_event: threading.Event):
                # Create event loop if library depends on asyncio in this thread
                try:
                    ensure_event_loop_in_thread()
                except Exception:
                    pass
                original_url = video_url
                sanitized = sanitize_url(video_url)
                tried = []
                api_ffmpeg = getattr(cv2, "CAP_FFMPEG", None)

                def try_open(url, use_ffmpeg=False):
                    cap_local = None
                    try:
                        cap_local = cv2.VideoCapture(url) if not use_ffmpeg else cv2.VideoCapture(url, api_ffmpeg)
                    except Exception:
                        cap_local = None
                    return cap_local

                is_hls = original_url.lower().endswith('.m3u8')
                is_rtsp = is_rtsp_url(original_url)
                # Prefer OpenCV(FFmpeg) quick try for streams, else imageio; for files/HTTP try OpenCV first.
                cap = None
                if is_hls or is_rtsp:
                    # Quick attempt with OpenCV FFmpeg backend
                    for use_ff in (True, False):
                        cap = try_open(original_url, use_ff)
                        if cap is not None and cap.isOpened():
                            if use_ff and api_ffmpeg is not None:
                                msg_queue.put(("info", index, "Opened stream with primary backend."))
                            break
                        if cap is not None:
                            try:
                                cap.release()
                            except Exception:
                                pass
                        cap = None
                    if cap is None or not cap.isOpened():
                        msg_queue.put(("info", index, "Switching to secondary decoder for stream..."))
                else:
                    # Try OpenCV first for local/HTTP
                    candidates = [original_url]
                    if original_url.startswith("http://"):
                        candidates.insert(0, "https://" + original_url[len("http://"):])
                    for candidate_url in candidates:
                        for use_ff in (False, True):
                            tried.append((candidate_url, use_ff))
                            cap = try_open(candidate_url, use_ff)
                            if cap is not None and cap.isOpened():
                                if candidate_url != original_url:
                                    msg_queue.put(("info", index, f"Using alternative URL {candidate_url}"))
                                if use_ff and api_ffmpeg is not None:
                                    msg_queue.put(("info", index, "Opened with primary backend."))
                                break
                            if cap is not None:
                                try:
                                    cap.release()
                                except Exception:
                                    pass
                            cap = None
                        if cap is not None and cap.isOpened():
                            break
                    if cap is None or not cap.isOpened():
                        msg_queue.put(("info", index, "Switching to secondary decoder..."))
                frame_count = 0
                frames_produced = 0
                start_time = time.time()
                read_timeout = 12.0 if (is_http_url(original_url) or is_rtsp or is_hls) else 6.0
                last_regions = []
                if cap is not None and cap.isOpened():
                    try:
                        while cap.isOpened() and not stop_event.is_set():
                            ret, frame = cap.read()
                            if not ret:
                                if frame_count == 0:
                                    msg_queue.put(("error", index, "Stream opened but returned no frames. This may be a codec issue. Please contact Clarifai support."))
                                break
                            frame_ts = time.time()
                            try:
                                if not skip_inference and (frame_count % frame_skip == 0):
                                    processed_frame, prediction_response, last_regions = run_model_inference(det_threshold, frame, model_option)
                                    if prediction_response:
                                        msg_queue.put(("json", index, (frame_ts, json_format.MessageToJson(prediction_response))))
                                else:
                                    # Draw previous detections over current frame
                                    processed_frame = draw_regions_on_frame(frame, last_regions, det_threshold, model_name=model_option['Name'])
                                rgb_frame = cv2.cvtColor(processed_frame, cv2.COLOR_BGR2RGB)
                                safe_put(frame_queues[index], (frame_ts, rgb_frame))
                                msg_queue.put(("frame", index, frame_ts))
                                frames_produced += 1
                            except Exception as inf_err:
                                msg_queue.put(("error", index, str(inf_err)))
                            frame_count += 1
                            # If no frames within timeout, break to fallback
                            if frames_produced == 0 and (time.time() - start_time) > read_timeout:
                                msg_queue.put(("info", index, "No frames within timeout; switching decoder..."))
                                break
                    finally:
                        cap.release()
                # If nothing produced, try imageio fallback readers (supports HLS .m3u8 and RTSP)
                if frames_produced == 0 and not stop_event.is_set():
                    try:
                        msg_queue.put(("info", index, "Falling back to imageio decoder..."))
                        import imageio.v3 as iio
                        src = original_url
                        is_hls = src.lower().endswith('.m3u8')
                        im_idx = 0
                        iterator = iio.imiter(src, plugin='ffmpeg') if (is_hls or is_rtsp) else iio.imiter(src)
                        for frm in iterator:
                            if stop_event.is_set():
                                break
                            try:
                                frame_ts = time.time()
                                frame_bgr = cv2.cvtColor(frm, cv2.COLOR_RGB2BGR)
                                if not skip_inference and (im_idx % frame_skip == 0):
                                    processed_frame, prediction_response, last_regions = run_model_inference(det_threshold, frame_bgr, model_option)
                                    if prediction_response:
                                        msg_queue.put(("json", index, (frame_ts, json_format.MessageToJson(prediction_response))))
                                else:
                                    processed_frame = draw_regions_on_frame(frame_bgr, last_regions, det_threshold, model_name=model_option['Name'])
                                rgb_frame = cv2.cvtColor(processed_frame, cv2.COLOR_BGR2RGB)
                                safe_put(frame_queues[index], (frame_ts, rgb_frame))
                                msg_queue.put(("frame", index, frame_ts))
                            except Exception as inf_err:
                                msg_queue.put(("error", index, str(inf_err)))
                            im_idx += 1
                    except Exception as fb_err:
                        try:
                            import imageio
                            msg_queue.put(("info", index, "Trying imageio v2 reader..."))
                            src = original_url
                            # Add ffmpeg params only for network streams (HTTP/RTSP/HLS)
                            if is_http_url(src) or is_rtsp_url(src) or is_hls:
                                ff_params = [
                                    '-user_agent', 'Mozilla/5.0',
                                    '-rw_timeout', '15000000',
                                    '-reconnect', '1',
                                    '-reconnect_streamed', '1',
                                    '-reconnect_delay_max', '5',
                                    '-protocol_whitelist', 'file,http,https,tcp,tls,crypto'
                                ]
                                if is_rtsp:
                                    ff_params += ['-rtsp_transport', 'tcp']
                                reader = imageio.get_reader(src, 'ffmpeg', ffmpeg_params=ff_params)
                            else:
                                reader = imageio.get_reader(src)
                            im_idx = 0
                            for frm in reader:
                                if stop_event.is_set():
                                    break
                                try:
                                    frame_ts = time.time()
                                    frame_bgr = cv2.cvtColor(frm, cv2.COLOR_RGB2BGR)
                                    if not skip_inference and (im_idx % frame_skip == 0):
                                        processed_frame, prediction_response, last_regions = run_model_inference(det_threshold, frame_bgr, model_option)
                                        if prediction_response:
                                            msg_queue.put(("json", index, (frame_ts, json_format.MessageToJson(prediction_response))))
                                    else:
                                        processed_frame = draw_regions_on_frame(frame_bgr, last_regions, det_threshold, model_name=model_option['Name'])
                                    rgb_frame = cv2.cvtColor(processed_frame, cv2.COLOR_BGR2RGB)
                                    safe_put(frame_queues[index], (frame_ts, rgb_frame))
                                    msg_queue.put(("frame", index, frame_ts))
                                except Exception as inf_err:
                                    msg_queue.put(("error", index, str(inf_err)))
                                im_idx += 1
                            try:
                                reader.close()
                            except Exception:
                                pass
                        except Exception as fb2_err:
                            msg_queue.put(("error", index, f"Fallback decoder failed: {fb_err}; v2 also failed: {fb2_err}"))
                msg_queue.put(("done", index, None))

            threads = []
            for index, (video_url, model_option) in enumerate(zip(url_list, model_options)):
                t = threading.Thread(target=process_video, args=(video_url, index, model_option, st.session_state.stop_event), name=f"process_video_{index}")
                t.start()
                threads.append(t)

            active = set(range(len(threads)))
            last_frames = [None] * len(frame_queues)
            target_height = 360  # normalize display height
            frames_seen = [0] * len(frame_queues)
            # Per-video display placeholders
            video_placeholders = [st.empty() for _ in range(len(frame_queues))]
            loading_placeholders = [st.empty() for _ in range(len(frame_queues))]
            loading_placeholders = [st.empty() for _ in range(len(frame_queues))]
            loading_placeholders = [st.empty() for _ in range(len(frame_queues))]
            loading_placeholders = [st.empty() for _ in range(len(frame_queues))]
            # Per-video playback buffers (timestamped frames)
            play_buffers = [deque() for _ in range(len(frame_queues))]
            # Per-video display schedule
            frame_interval = 1.0 / float(max_display_fps) if max_display_fps > 0 else 1.0 / 15.0
            next_display_ts = [0.0] * len(frame_queues)  # wallclock time for next render
            last_display_frames = [None] * len(frame_queues)
            # Buffer growth tracking to avoid getting stuck
            last_buf_len = [0] * len(frame_queues)
            last_buf_change_ts = [time.time()] * len(frame_queues)
            # Initial prebuffer state per video
            initial_met = [False] * len(frame_queues)

            def resize_keep_aspect(img, target_h):
                h, w = img.shape[:2]
                scale = target_h / float(h)
                new_w = max(1, int(w * scale))
                return cv2.resize(img, (new_w, target_h), interpolation=cv2.INTER_AREA)

            while active and not st.session_state.stop_event.is_set():
                # Drain message queue
                drained = 0
                while True:
                    try:
                        kind, idx, payload = msg_queue.get_nowait()
                        drained += 1
                    except Empty:
                        break
                    else:
                        if kind == "error":
                            error_placeholder.error(f"Video {idx + 1}: {payload}")
                        elif kind == "json":
                            # Store last 100 JSON entries per video, honoring producer timestamp when provided
                            if isinstance(payload, tuple) and len(payload) == 2:
                                ts_val, data_val = payload
                            else:
                                ts_val, data_val = time.time(), payload
                            try:
                                obj = json.loads(data_val) if isinstance(data_val, str) else data_val
                            except Exception:
                                obj = data_val
                            entry = {"ts": ts_val, "data": obj}
                            jmap = st.session_state.setdefault("json_by_video", {})
                            lst = jmap.setdefault(idx, [])
                            lst.append(entry)
                            if len(lst) > 100:
                                del lst[:-100]
                        elif kind == "frame":
                            if 0 <= idx < len(frames_seen):
                                frames_seen[idx] += 1
                        elif kind == "done":
                            active.discard(idx)

                # Pull latest frames from queues into playback buffers (use producer timestamps)
                for i, fq in enumerate(frame_queues):
                    try:
                        while True:
                            item = fq.get_nowait()
                            if isinstance(item, tuple) and len(item) == 2:
                                ts, f = item
                            else:
                                ts, f = time.time(), item
                            play_buffers[i].append((ts, f))
                            last_frames[i] = f
                    except Empty:
                        pass

                # Show each video respecting constant-latency buffering and fixed display cadence
                now_ts = time.time()
                for i in range(len(play_buffers)):
                    frame_to_show = None
                    init_delay = max(buffer_seconds, INITIAL_PREBUFFER_SECONDS)
                    # Update buffer growth tracking
                    cur_len = len(play_buffers[i])
                    if cur_len != last_buf_len[i]:
                        last_buf_len[i] = cur_len
                        last_buf_change_ts[i] = now_ts
                    # Check if initial prebuffer met; if stalled >2s but frames exist, grace-start
                    if not initial_met[i]:
                        if play_buffers[i] and (now_ts - play_buffers[i][0][0]) >= init_delay:
                            initial_met[i] = True
                        elif play_buffers[i] and (now_ts - last_buf_change_ts[i]) > 2.0:
                            initial_met[i] = True
                    # Determine target latency
                    delay = buffer_seconds if initial_met[i] else init_delay
                    # Throttle rendering by max FPS
                    if now_ts >= next_display_ts[i]:
                        # Select the latest frame with ts <= now - delay
                        target_ts = now_ts - delay
                        candidate = None
                        while play_buffers[i] and play_buffers[i][0][0] <= target_ts:
                            _, candidate = play_buffers[i].popleft()
                        if candidate is not None:
                            frame_to_show = candidate
                        else:
                            frame_to_show = last_display_frames[i] if last_display_frames[i] is not None else last_frames[i]
                        next_display_ts[i] = now_ts + frame_interval
                    else:
                        # Not time to render yet; keep last
                        frame_to_show = last_display_frames[i] if last_display_frames[i] is not None else last_frames[i]
                    # Loading indicator during initial prebuffer
                    buf_fill = (now_ts - play_buffers[i][0][0]) if play_buffers[i] else 0.0
                    if not initial_met[i]:
                        loading_placeholders[i].info(f"Video {i+1} buffering… {min(buf_fill, init_delay):.1f}/{init_delay:.1f}s")
                    else:
                        loading_placeholders[i].empty()
                    # Caption
                    if buffer_seconds > 0:
                        caption = f"Video {i+1} • Buffer {min(buffer_seconds, max(0.0, buf_fill)):.1f}/{buffer_seconds}s • {max_display_fps} FPS"
                    else:
                        caption = f"Video {i+1} • {max_display_fps} FPS"
                    if frame_to_show is not None:
                        last_display_frames[i] = frame_to_show
                        video_placeholders[i].image(resize_keep_aspect(frame_to_show, target_height), caption=caption)

                counts = ", ".join([f"V{i+1}:{c}" for i, c in enumerate(frames_seen)])
                status_placeholder.info(f"Active videos: {len(active)} | Frames: [{counts}] | {time.strftime('%H:%M:%S')}")
                # Small sleep to avoid busy-loop; display cadence handled per-video
                time.sleep(0.01)

            # If stopped early, signal threads to exit and join
            if st.session_state.stop_event.is_set():
                status_placeholder.warning("Stopping processing...")
            for t in threads:
                t.join(timeout=0.5)
            # If nothing was decoded, surface a tip
            if sum(frames_seen) == 0 and not st.session_state.stop_event.is_set():
                error_placeholder.warning("No frames were decoded. If you are on Windows, ensure 'opencv-python' (not headless) is installed to include FFmpeg codecs. You can also toggle 'Skip model inference' to isolate decoding issues.")
        except Exception as e:
            st.error(e)
    # JSON download is shown above in the always-visible section
elif video_option == "Local Video Files":
    uploaded = st.file_uploader(
        "Upload one or more video files",
        type=["mp4","mov","avi","mkv"], accept_multiple_files=True,
        help="Supported: mp4, mov, mkv, avi. Files are saved to a temp path and streamed from disk."
    )
    frame_skip = st.slider(
        "Select how many frames to skip:", min_value=1, max_value=120, value=30,
        help="Run inference every N frames (all frames are displayed)."
    )
    det_threshold = st.slider(
        "Select detection threshold:", min_value=0.01, max_value=1.00, value=0.5,
        help="Only show labels/concepts with confidence >= threshold."
    )
    buffer_seconds = st.slider(
        "Playback buffer (seconds)", min_value=0, max_value=15, value=10,
        help="Adds constant playback delay to smooth jitter. Increase for smoother playback; set 0 for lowest latency."
    )
    max_display_fps = st.slider(
        "Max display FPS", min_value=5, max_value=60, value=15,
        help="Upper bound on rendering rate. Reduce if you want the buffer to remain filled."
    )
    skip_inference = st.checkbox(
        "Skip model inference (show raw frames)", value=False,
        help="Decode-only mode to validate file playback without calling the model."
    )
    # Persist uploaded files to temp paths
    url_list = []
    file_names = []  # Keep stable identifiers for widget keys
    if uploaded:
        for up in uploaded:
            try:
                suffix = os.path.splitext(up.name)[1] or ".mp4"
                tf = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                tf.write(up.read())
                tf.flush(); tf.close()
                url_list.append(tf.name)
                file_names.append(up.name)
            except Exception as up_err:
                st.error(f"Failed to save uploaded file {up.name}: {up_err}")
    # Fetch models dynamically for current or custom user/app
    if st.session_state.get("auth_use_custom"):
        user_id = st.session_state.get("auth_user_id")
        app_id = st.session_state.get("auth_app_id")
    else:
        user_id = getattr(userDataObject, "user_id", None)
        app_id = getattr(userDataObject, "app_id", None)
    with st.spinner("Loading models..."):
        available_models = list_models(user_id, app_id, st.session_state.get("portal_base_host", "clarifai.com"))
    cols_actions = st.columns([1,1,6])
    with cols_actions[0]:
        if st.button("Refresh Models"):
            list_models.clear(); available_models = list_models(user_id, app_id, st.session_state.get("portal_base_host", "clarifai.com"))
    with cols_actions[1]:
        if "stop_event" not in st.session_state:
            st.session_state.stop_event = threading.Event()
        if st.button("Stop Processing", type="secondary"):
            st.session_state.stop_event.set()
    # Always offer latest detections download (if any), even outside processing
    try:
        sources_preview_local = file_names if file_names else url_list
        verify_json_responses(sources_preview_local)
    except Exception:
        pass
    # App override if cross-app listing returns nothing (apply before empty check)
    app_override_local = st.text_input("App ID override (optional): load models from this app if cross-app listing is empty", value="", key="app_override_local")
    if not available_models and app_override_local.strip():
        available_models = list_models(user_id, app_override_local.strip(), st.session_state.get("portal_base_host", "clarifai.com"))
    # Fallback to helper's default app if still empty
    if not available_models and not app_override_local.strip():
        helper_app_id = getattr(userDataObject, "app_id", None)
        if helper_app_id:
            available_models = list_models(user_id, helper_app_id, st.session_state.get("portal_base_host", "clarifai.com"))
    if not available_models:
        st.warning("No models found. Provide an App ID override above or ensure your account has access to at least one app with models.")
        st.stop()
    # Filter not as necessary here but keep consistent
    model_filter = st.text_input(
        "Filter models (type to narrow list)",
        value=st.session_state.get("model_filter_local", ""), key="model_filter_local",
        placeholder="e.g. app-id or model-id",
        help="Type to filter by app or model ID."
    )
    filtered_models = [m for m in available_models if model_filter.strip().lower() in m.get("Label", m["Name"]).lower()] if model_filter else available_models
    if not filtered_models:
        filtered_models = available_models
    # Per-video model selection from user's available models
    model_options = []
    # Fallback if filter yields no results
    if not filtered_models:
        st.info("No models match the current filter. Showing all models.")
        filtered_models = available_models
    model_labels = [m.get("Label", m["Name"]) for m in filtered_models]
    for idx, url in enumerate(url_list):
        # Use original filename to keep the widget key stable across reruns (temp paths change)
        base_name = file_names[idx] if idx < len(file_names) else os.path.basename(url)
        stable_key = f"model_local_{idx}_{hash_url(base_name)}"

        # Remember per-video selection by label; map to current filtered options when list changes.
        # If previous selection isn't available after filtering, drop it so 'index' takes effect.
        prev_label = st.session_state.get(stable_key)
        if prev_label is not None and prev_label not in model_labels:
            try:
                del st.session_state[stable_key]
            except Exception:
                pass
            prev_label = None

        if prev_label in model_labels:
            default_index = model_labels.index(prev_label)
        else:
            default_index = 0 if model_labels else None

        sel_label = st.selectbox(
            f"Select a model for Video {idx + 1}:",
            model_labels,
            index=default_index if default_index is not None else 0,
            key=stable_key
        )
        model_options.append(next(m for m in filtered_models if m.get("Label", m["Name"]) == sel_label))

    # Note: In Streamlit, the script blocks while running; a Stop button won't be effective during processing.
    if st.button("Process Videos"):
        frame_placeholder = st.empty()
        error_placeholder = st.empty()
        status_placeholder = st.empty()
        try:
            # Clear previous stop signal
            if "stop_event" not in st.session_state:
                st.session_state.stop_event = threading.Event()
            else:
                st.session_state.stop_event.clear()
            # Reset rolling JSON buffers for this run
            st.session_state["json_by_video"] = {}
            # Thread-safe queues for frames and messages
            target_q_size = max(2, int((buffer_seconds if buffer_seconds else 0) * 30 + 60))
            frame_queues = [Queue(maxsize=target_q_size) for _ in range(len(url_list))]
            msg_queue = Queue()  # tuples: (kind, index, payload)

            def safe_put(q: Queue, item):
                try:
                    q.put_nowait(item)
                except Exception:
                    try:
                        q.get_nowait()
                    except Exception:
                        pass
                    try:
                        q.put_nowait(item)
                    except Exception:
                        pass

            def process_video(video_url, index, model_option, stop_event: threading.Event):
                # Create event loop if library depends on asyncio in this thread
                try:
                    ensure_event_loop_in_thread()
                except Exception:
                    pass
                original_url = video_url
                sanitized = sanitize_url(video_url)
                tried = []
                api_ffmpeg = getattr(cv2, "CAP_FFMPEG", None)

                def try_open(url, use_ffmpeg=False):
                    cap_local = None
                    try:
                        cap_local = cv2.VideoCapture(url) if not use_ffmpeg else cv2.VideoCapture(url, api_ffmpeg)
                    except Exception:
                        cap_local = None
                    return cap_local

                is_hls = original_url.lower().endswith('.m3u8')
                is_rtsp = is_rtsp_url(original_url)
                cap = None
                if is_hls or is_rtsp:
                    # Quick attempt with OpenCV FFmpeg backend
                    for use_ff in (True, False):
                        cap = try_open(original_url, use_ff)
                        if cap is not None and cap.isOpened():
                            if use_ff and api_ffmpeg is not None:
                                msg_queue.put(("info", index, "Opened stream with FFmpeg backend."))
                            break
                        if cap is not None:
                            try:
                                cap.release()
                            except Exception:
                                pass
                        cap = None
                    if cap is None or not cap.isOpened():
                        msg_queue.put(("info", index, "Switching to imageio decoder for stream..."))
                else:
                    # Try OpenCV first for local/HTTP
                    candidates = [original_url]
                    if original_url.startswith("http://"):
                        candidates.insert(0, "https://" + original_url[len("http://"):])
                    for candidate_url in candidates:
                        for use_ff in (False, True):
                            tried.append((candidate_url, use_ff))
                            cap = try_open(candidate_url, use_ff)
                            if cap is not None and cap.isOpened():
                                if candidate_url != original_url:
                                    msg_queue.put(("info", index, f"Using alternative URL {candidate_url}"))
                                if use_ff and api_ffmpeg is not None:
                                    msg_queue.put(("info", index, "Opened with FFmpeg backend."))
                                break
                            if cap is not None:
                                try:
                                    cap.release()
                                except Exception:
                                    pass
                            cap = None
                        if cap is not None and cap.isOpened():
                            break
                    if cap is None or not cap.isOpened():
                        msg_queue.put(("info", index, "Switching to imageio decoder..."))
                frame_count = 0
                frames_produced = 0
                start_time = time.time()
                last_frame_time = start_time
                read_timeout = 12.0 if (is_http_url(original_url) or is_rtsp or is_hls) else 6.0
                last_regions = []
                if cap is not None and cap.isOpened():
                    try:
                        while cap.isOpened() and not stop_event.is_set():
                            ret, frame = cap.read()
                            if not ret:
                                if frame_count == 0:
                                    msg_queue.put(("error", index, "Stream opened but returned no frames. This may be a codec issue."))
                                break
                            last_frame_time = time.time()
                            try:
                                if not skip_inference and (frame_count % frame_skip == 0):
                                    processed_frame, prediction_response, last_regions = run_model_inference(det_threshold, frame, model_option)
                                    if prediction_response:
                                        msg_queue.put(("json", index, json_format.MessageToJson(prediction_response)))
                                else:
                                    processed_frame = draw_regions_on_frame(frame, last_regions, det_threshold, model_name=model_option['Name'])
                                rgb_frame = cv2.cvtColor(processed_frame, cv2.COLOR_BGR2RGB)
                                safe_put(frame_queues[index], rgb_frame)
                                # Notify main thread that a frame was posted
                                msg_queue.put(("frame", index, None))
                                frames_produced += 1
                            except Exception as inf_err:
                                msg_queue.put(("error", index, str(inf_err)))
                            frame_count += 1
                            # If no frames within timeout, break to fallback
                            if frames_produced == 0 and (time.time() - start_time) > read_timeout:
                                msg_queue.put(("info", index, "No frames within timeout; switching decoder..."))
                                break
                    finally:
                        cap.release()
                # If nothing produced, try imageio-ffmpeg fallback (supports HLS .m3u8 and RTSP)
                if frames_produced == 0 and not stop_event.is_set():
                    try:
                        msg_queue.put(("info", index, "Falling back to imageio decoder..."))
                        # Try imageio v3 first
                        import imageio.v3 as iio
                        ff_params = [
                            '-user_agent', 'Mozilla/5.0',
                            '-rw_timeout', '15000000',
                            '-reconnect', '1',
                            '-reconnect_streamed', '1',
                            '-reconnect_delay_max', '5',
                            '-protocol_whitelist', 'file,http,https,tcp,tls,crypto'
                        ]
                        if is_rtsp:
                            ff_params += ['-rtsp_transport', 'tcp']
                        im_idx = 0
                        iterator = iio.imiter(original_url, plugin='ffmpeg') if (is_hls or is_rtsp) else iio.imiter(original_url)
                        for frm in iterator:
                            if stop_event.is_set():
                                break
                            try:
                                # imageio frames are RGB; convert to BGR for OpenCV ops
                                frame_bgr = cv2.cvtColor(frm, cv2.COLOR_RGB2BGR)
                                if not skip_inference and (im_idx % frame_skip == 0):
                                    processed_frame, prediction_response, last_regions = run_model_inference(det_threshold, frame_bgr, model_option)
                                    if prediction_response:
                                        msg_queue.put(("json", index, json_format.MessageToJson(prediction_response)))
                                else:
                                    processed_frame = draw_regions_on_frame(frame_bgr, last_regions, det_threshold, model_name=model_option['Name'])
                                rgb_frame = cv2.cvtColor(processed_frame, cv2.COLOR_BGR2RGB)
                                safe_put(frame_queues[index], rgb_frame)
                                msg_queue.put(("frame", index, None))
                            except Exception as inf_err:
                                msg_queue.put(("error", index, str(inf_err)))
                            im_idx += 1
                    except Exception as fb_err:
                        # Try imageio v2 with custom ffmpeg parameters (headers/timeouts) for network
                        try:
                            import imageio
                            msg_queue.put(("info", index, "Trying imageio v2 reader..."))
                            if is_http_url(original_url) or is_rtsp_url(original_url) or is_hls:
                                ff_params = [
                                    '-user_agent', 'Mozilla/5.0',
                                    '-rw_timeout', '15000000',
                                    '-reconnect', '1',
                                    '-reconnect_streamed', '1',
                                    '-reconnect_delay_max', '5',
                                    '-protocol_whitelist', 'file,http,https,tcp,tls,crypto'
                                ]
                                if is_rtsp:
                                    ff_params += ['-rtsp_transport', 'tcp']
                                reader = imageio.get_reader(original_url, 'ffmpeg', ffmpeg_params=ff_params)
                            else:
                                reader = imageio.get_reader(original_url)
                            im_idx = 0
                            for frm in reader:
                                if stop_event.is_set():
                                    break
                                try:
                                    frame_bgr = cv2.cvtColor(frm, cv2.COLOR_RGB2BGR)
                                    if not skip_inference and (im_idx % frame_skip == 0):
                                        processed_frame, prediction_response, last_regions = run_model_inference(det_threshold, frame_bgr, model_option)
                                        if prediction_response:
                                            msg_queue.put(("json", index, json_format.MessageToJson(prediction_response)))
                                    else:
                                        processed_frame = draw_regions_on_frame(frame_bgr, last_regions, det_threshold, model_name=model_option['Name'])
                                    rgb_frame = cv2.cvtColor(processed_frame, cv2.COLOR_BGR2RGB)
                                    safe_put(frame_queues[index], rgb_frame)
                                    msg_queue.put(("frame", index, None))
                                except Exception as inf_err:
                                    msg_queue.put(("error", index, str(inf_err)))
                                im_idx += 1
                            try:
                                reader.close()
                            except Exception:
                                pass
                        except Exception as fb2_err:
                            msg_queue.put(("error", index, f"Fallback decoder failed: {fb_err}; v2 also failed: {fb2_err}"))
                msg_queue.put(("done", index, None))

            threads = []
            for index, (video_url, model_option) in enumerate(zip(url_list, model_options)):
                t = threading.Thread(target=process_video, args=(video_url, index, model_option, st.session_state.stop_event), name=f"process_video_{index}")
                t.start()
                threads.append(t)

            active = set(range(len(threads)))
            last_frames = [None] * len(frame_queues)
            target_height = 360  # normalize display height
            frames_seen = [0] * len(frame_queues)
            # Per-video display placeholders
            video_placeholders = [st.empty() for _ in range(len(frame_queues))]
            loading_placeholders = [st.empty() for _ in range(len(frame_queues))]
            # Per-video playback buffers (timestamped frames)
            play_buffers = [deque() for _ in range(len(frame_queues))]
            # Per-video display schedule
            frame_interval = 1.0 / float(max_display_fps) if max_display_fps > 0 else 1.0 / 15.0
            next_display_ts = [0.0] * len(frame_queues)
            last_display_frames = [None] * len(frame_queues)
            # Buffer growth tracking to avoid getting stuck
            last_buf_len = [0] * len(frame_queues)
            last_buf_change_ts = [time.time()] * len(frame_queues)
            initial_met = [False] * len(frame_queues)

            def resize_keep_aspect(img, target_h):
                h, w = img.shape[:2]
                scale = target_h / float(h)
                new_w = max(1, int(w * scale))
                return cv2.resize(img, (new_w, target_h), interpolation=cv2.INTER_AREA)

            while active and not st.session_state.stop_event.is_set():
                # Drain message queue
                drained = 0
                while True:
                    try:
                        kind, idx, payload = msg_queue.get_nowait()
                        drained += 1
                    except Empty:
                        break
                    else:
                        if kind == "error":
                            error_placeholder.error(f"Video {idx + 1}: {payload}")
                        elif kind == "info":
                            error_placeholder.info(f"Video {idx + 1}: {payload}")
                        elif kind == "json":
                            # Store last 100 JSON entries per video, honoring producer timestamp when provided
                            if isinstance(payload, tuple) and len(payload) == 2:
                                ts_val, data_val = payload
                            else:
                                ts_val, data_val = time.time(), payload
                            try:
                                obj = json.loads(data_val) if isinstance(data_val, str) else data_val
                            except Exception:
                                obj = data_val
                            entry = {"ts": ts_val, "data": obj}
                            jmap = st.session_state.setdefault("json_by_video", {})
                            lst = jmap.setdefault(idx, [])
                            lst.append(entry)
                            if len(lst) > 100:
                                del lst[:-100]
                        elif kind == "frame":
                            if 0 <= idx < len(frames_seen):
                                frames_seen[idx] += 1
                        elif kind == "done":
                            active.discard(idx)

                # Pull latest frames from queues into playback buffers (use producer timestamps)
                for i, fq in enumerate(frame_queues):
                    try:
                        while True:
                            item = fq.get_nowait()
                            if isinstance(item, tuple) and len(item) == 2:
                                ts, f = item
                            else:
                                ts, f = time.time(), item
                            play_buffers[i].append((ts, f))
                            last_frames[i] = f
                    except Empty:
                        pass

                # Show each video respecting constant-latency buffering and fixed display cadence
                now_ts = time.time()
                for i in range(len(play_buffers)):
                    frame_to_show = None
                    init_delay = max(buffer_seconds, INITIAL_PREBUFFER_SECONDS)
                    # Update buffer growth tracking and initial prebuffer status
                    cur_len = len(play_buffers[i])
                    if cur_len != last_buf_len[i]:
                        last_buf_len[i] = cur_len
                        last_buf_change_ts[i] = now_ts
                    if not initial_met[i]:
                        if play_buffers[i] and (now_ts - play_buffers[i][0][0]) >= init_delay:
                            initial_met[i] = True
                        elif play_buffers[i] and (now_ts - last_buf_change_ts[i]) > 2.0:
                            initial_met[i] = True
                    delay = buffer_seconds if initial_met[i] else init_delay
                    if now_ts >= next_display_ts[i]:
                        target_ts = now_ts - delay
                        candidate = None
                        while play_buffers[i] and play_buffers[i][0][0] <= target_ts:
                            _, candidate = play_buffers[i].popleft()
                        if candidate is not None:
                            frame_to_show = candidate
                        else:
                            frame_to_show = last_display_frames[i] if last_display_frames[i] is not None else last_frames[i]
                        next_display_ts[i] = now_ts + frame_interval
                    else:
                        frame_to_show = last_display_frames[i] if last_display_frames[i] is not None else last_frames[i]
                    buf_fill = (now_ts - play_buffers[i][0][0]) if play_buffers[i] else 0.0
                    if not initial_met[i]:
                        loading_placeholders[i].info(f"Video {i+1} buffering… {min(buf_fill, init_delay):.1f}/{init_delay:.1f}s")
                    else:
                        loading_placeholders[i].empty()
                    if buffer_seconds > 0:
                        caption = f"Video {i+1} • Buffer {min(buffer_seconds, max(0.0, buf_fill)):.1f}/{buffer_seconds}s • {max_display_fps} FPS"
                    else:
                        caption = f"Video {i+1} • {max_display_fps} FPS"
                    if frame_to_show is not None:
                        last_display_frames[i] = frame_to_show
                        video_placeholders[i].image(resize_keep_aspect(frame_to_show, target_height), caption=caption)

                counts = ", ".join([f"V{i+1}:{c}" for i, c in enumerate(frames_seen)])
                status_placeholder.info(f"Active videos: {len(active)} | Frames: [{counts}] | {time.strftime('%H:%M:%S')}")
                time.sleep(0.01)

            # If stopped early, signal threads to exit and join
            if st.session_state.stop_event.is_set():
                status_placeholder.warning("Stopping processing...")
            for t in threads:
                t.join(timeout=0.5)
            # If nothing was decoded, surface a tip
            if sum(frames_seen) == 0 and not st.session_state.stop_event.is_set():
                error_placeholder.warning("No frames were decoded. You can also toggle 'Skip model inference' to isolate decoding issues. For all other issues contact Clarifai Support")
        except Exception as e:
            st.error(e)

