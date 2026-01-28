import json
import os
import shutil
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterator, List
from string import Template
from urllib.parse import urlparse

from dotenv import find_dotenv, load_dotenv
import requests
import streamlit as st
from requests.auth import HTTPBasicAuth

st.set_page_config(page_title="MP4 Stream Manager", layout="wide")

# Load .env if present so UI reflects local configuration without manual exports
load_dotenv(find_dotenv(), override=False)

# Streamlit 1.31+ renamed experimental_rerun -> rerun; support both for compatibility.
if hasattr(st, "rerun"):
    _rerun = st.rerun
else:
    _rerun = st.experimental_rerun

# Detect backend URL based on browser context
def get_default_backend() -> str:
    """Auto-detect backend URL based on how the UI is accessed."""
    env_backend = os.getenv("BACKEND_URL", "")
    if env_backend:
        return env_backend
    
    # Try to detect from Streamlit's session info
    try:
        # Check if we have query params that might indicate the browser origin
        query_params = st.query_params
        # Streamlit doesn't expose the full browser URL directly, but we can use a workaround
        # via custom component or session state
    except:
        pass
    
    # Check for PUBLIC_HTTPS_ORIGIN env var
    public_origin = os.getenv("PUBLIC_HTTPS_ORIGIN", "")
    if public_origin:
        # If PUBLIC_HTTPS_ORIGIN is set, assume we're behind nginx and use it
        return public_origin
    
    # Default fallback
    return "http://localhost:8000"

DEFAULT_BACKEND = get_default_backend()
MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", "media")).resolve()
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
STREAMS_FILE = MEDIA_ROOT / ".streams.json"
DASH_ROOT = Path(os.getenv("DASH_ROOT", str(MEDIA_ROOT / "dash"))).resolve()
DASH_ROOT.mkdir(parents=True, exist_ok=True)
MAX_PLAYERS = int(os.getenv("MAX_CONCURRENT_PLAYERS", "4"))
BITRATE_SAMPLE_BYTES = int(os.getenv("BITRATE_SAMPLE_BYTES", "65536"))
BASIC_AUTH_USER = os.getenv("BASIC_AUTH_USER") or os.getenv("BASIC_AUTH_USERNAME")
BASIC_AUTH_PASS = os.getenv("BASIC_AUTH_PASS") or os.getenv("BASIC_AUTH_PASSWORD")


def _ensure_leading_slash(value: str) -> str:
    if not value:
        return value
    return value if value.startswith("/") else f"/{value}"


def to_backend_absolute(url: str) -> str:
    if not url:
        return url
    parsed = urlparse(url)
    if parsed.scheme in ("http", "https"):
        return url
    path = _ensure_leading_slash(url)
    base = DEFAULT_BACKEND.rstrip("/")
    return f"{base}{path}"


def split_relative_absolute(url: str | None) -> tuple[str | None, str | None]:
    if not url:
        return None, None
    parsed = urlparse(url)
    if parsed.scheme in ("http", "https"):
        return None, url
    path = _ensure_leading_slash(url)
    return path, to_backend_absolute(path)


def parse_error_response(resp) -> dict[str, str | None]:
    try:
        payload = resp.json()
    except Exception:
        return {"message": resp.text.strip(), "stderr": None}
    detail = payload.get("detail") if isinstance(payload, dict) else payload
    stderr = None
    message = detail
    if isinstance(detail, dict):
        message = detail.get("error") or detail.get("message") or json.dumps(detail)
        stderr = detail.get("stderr")
    elif isinstance(detail, list):
        message = "; ".join(str(item) for item in detail)
    elif detail is None:
        message = resp.text.strip()
    return {"message": str(message), "stderr": stderr}


def get_auth() -> HTTPBasicAuth | None:
    if BASIC_AUTH_USER and BASIC_AUTH_PASS:
        return HTTPBasicAuth(BASIC_AUTH_USER, BASIC_AUTH_PASS)
    return None


def fetch_hls_streams(base_url: str) -> List[dict]:
    try:
        auth = get_auth()
        resp = requests.get(f"{base_url.rstrip('/')}/api/hls/streams", timeout=5, auth=auth)
        if resp.status_code != 200:
            return []
        data = resp.json()
        return data if isinstance(data, list) else []
    except Exception:
        return []


def to_absolute_mpd_url(backend_url: str, mpd_path: str | None) -> str | None:
    if not mpd_path:
        return None
    if mpd_path.startswith("http://") or mpd_path.startswith("https://"):
        return mpd_path
    if mpd_path.startswith("/"):
        return f"{backend_url.rstrip('/')}{mpd_path}"
    return f"{backend_url.rstrip('/')}/{mpd_path}"


def within_media_root(candidate: Path) -> bool:
    root = MEDIA_ROOT
    try:
        candidate.relative_to(root)
        return True
    except ValueError:
        return False


def load_streams() -> List[Dict[str, str]]:
    if not STREAMS_FILE.exists():
        return []
    try:
        with STREAMS_FILE.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
            if isinstance(data, list):
                return [s for s in data if "streamId" in s and "filePath" in s]
    except Exception:
        pass
    return []


def save_streams(streams: List[Dict[str, str]]) -> None:
    with STREAMS_FILE.open("w", encoding="utf-8") as fh:
        json.dump(streams, fh, indent=2)


def register_stream(streams: List[Dict[str, str]], name: str, file_path: str) -> tuple[bool, str]:
    if not name:
        return False, "Stream name is required."
    normalized = name.strip()
    if any(s.get("name", "").lower() == normalized.lower() for s in streams):
        return False, "A stream with that name already exists."
    path = Path(file_path).resolve()
    if not path.exists() or not path.is_file():
        return False, "Selected file does not exist."
    if not within_media_root(path):
        return False, "File must reside under MEDIA_ROOT."
    if path.suffix.lower() != ".mp4":
        return False, "Only MP4 files are supported."
    stream = {
        "streamId": uuid.uuid4().hex,
        "name": normalized,
        "filePath": str(path),
        "createdAt": datetime.utcnow().isoformat() + "Z",
    }
    streams.append(stream)
    save_streams(streams)
    return True, f"Stream '{normalized}' added."


def set_stream_manifest(streams: List[Dict[str, str]], stream_id: str, manifest_rel: str) -> None:
    for stream in streams:
        if stream.get("streamId") == stream_id:
            stream["dashManifest"] = manifest_rel
            stream["dashPackagedAt"] = datetime.utcnow().isoformat() + "Z"
            save_streams(streams)
            return


def clear_stream_manifest(streams: List[Dict[str, str]], stream_id: str) -> None:
    for stream in streams:
        if stream.get("streamId") == stream_id:
            stream.pop("dashManifest", None)
            stream.pop("dashPackagedAt", None)
            save_streams(streams)
            return


def remove_stream(streams: List[Dict[str, str]], stream_id: str, delete_file: bool = False) -> tuple[bool, str]:
    idx = next((i for i, s in enumerate(streams) if s.get("streamId") == stream_id), None)
    if idx is None:
        return False, "Stream not found."
    entry = streams.pop(idx)
    save_streams(streams)
    dash_manifest = entry.get("dashManifest")
    if dash_manifest:
        dash_path = (DASH_ROOT / dash_manifest).resolve()
        dash_dir = dash_path.parent if dash_path.name.endswith(".mpd") else dash_path
        if dash_dir.exists() and dash_dir.is_dir():
            try:
                dash_dir.relative_to(DASH_ROOT)
            except ValueError:
                pass
            else:
                shutil.rmtree(dash_dir, ignore_errors=True)
    if delete_file:
        try:
            path = Path(entry["filePath"]).resolve()
            if within_media_root(path) and path.exists():
                path.unlink()
        except Exception as exc:
            return True, f"Stream removed. File delete failed: {exc}"
    return True, "Stream removed."


def chunked(items: List[Dict[str, str]], size: int) -> Iterator[List[Dict[str, str]]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


@st.cache_data(ttl=30)
def estimate_bitrate(stream_id: str, url: str) -> float | None:
    headers = {"Range": f"bytes=0-{BITRATE_SAMPLE_BYTES - 1}"}
    try:
        start = time.perf_counter()
        with requests.get(url, headers=headers, stream=True, timeout=5) as resp:
            if resp.status_code not in (200, 206):
                return None
            total = 0
            for chunk in resp.iter_content(chunk_size=8192):
                if not chunk:
                    break
                total += len(chunk)
                if total >= BITRATE_SAMPLE_BYTES:
                    break
        duration = time.perf_counter() - start
        if duration <= 0 or total <= 0:
            return None
        return total / duration
    except Exception:
        return None


@st.cache_data(ttl=30)
def fetch_manifest_text(url: str) -> str | None:
    if not url:
        return None
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code != 200:
            return None
        text = resp.text.strip()
        if len(text) > 20000:
            return text[:20000] + "\n... (truncated)"
        return text
    except Exception:
        return None


def render_video_player_html(element_key: str, relative_url: str | None, absolute_url: str | None, height: int = 40) -> str:
    rel_js = json.dumps(relative_url) if relative_url else "null"
    abs_js = json.dumps(absolute_url) if absolute_url else "null"
    video_id = f"{element_key}-video"
    link_id = f"{element_key}-link"
    return f"""
        <div>
            <video id="{video_id}" controls preload="metadata" style="width:100%; max-height:{height}vh; background:#000"></video>
            <div style="margin-top:8px; font-family: ui-sans-serif; font-size:0.85rem">URL: <a id="{link_id}" href="#" target="_blank" rel="noreferrer noopener">resolving…</a></div>
        </div>
        <script>
        (function() {{
            var relativeUrl = {rel_js};
            var absoluteUrl = {abs_js};
            var target = (window.location.protocol === 'https:' && relativeUrl) ? relativeUrl : (absoluteUrl || relativeUrl || '');
            if (!target) {{
                console.warn('[MP4] Unable to resolve media URL.');
                return;
            }}
            var videoEl = document.getElementById('{video_id}');
            if (videoEl) {{
                videoEl.src = target;
            }}
            var linkEl = document.getElementById('{link_id}');
            if (linkEl) {{
                linkEl.href = target;
                linkEl.textContent = target;
            }}
        }})();
        </script>
    """
def render_dash_player(component_key: str, mpd_url: str, height: int = 480) -> None:
    safe_key = "".join(ch if ch.isalnum() else "-" for ch in component_key)
    player_id = f"dash-player-{safe_key}"
    stats_id = f"dash-stats-{safe_key}"
    http_id = f"dash-http-{safe_key}"
    controls_id = f"dash-controls-{safe_key}"
    manifest_id = f"dash-manifest-{safe_key}"
    events_id = f"dash-events-{safe_key}"
    mpd_relative, mpd_absolute = split_relative_absolute(mpd_url)
    manifest_source = mpd_absolute or mpd_relative or mpd_url
    manifest_text = fetch_manifest_text(manifest_source) if manifest_source else None
    manifest_js = json.dumps(manifest_text) if manifest_text is not None else "null"
    mpd_relative_js = json.dumps(mpd_relative) if mpd_relative else "null"
    mpd_absolute_js = json.dumps(mpd_absolute) if mpd_absolute else "null"
    link_id = f"{controls_id}-mpd-link"
    
    dash_html = f"""
        <div class="dash-player-shell" style="border:1px solid #333;border-radius:6px;padding:10px;background:#10131c;color:#f3f4f6">
            <div id="{player_id}"></div>
            <div id="{controls_id}" style="display:flex;flex-wrap:wrap;gap:8px;margin-top:10px">
                <button id="{controls_id}-reload" class="dash-btn">Reload</button>
                <button id="{controls_id}-play" class="dash-btn">Play/Pause</button>
                <button id="{controls_id}-reset" class="dash-btn">Reset</button>
                <button id="{controls_id}-mute" class="dash-btn">Mute/Unmute</button>
                <button id="{controls_id}-manifest" class="dash-btn">Refresh MPD</button>
                <button id="{controls_id}-copy" class="dash-btn">Copy MPD URL</button>
            </div>
            <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px;margin-top:10px">
                <pre id="{stats_id}" style="margin:0;padding:8px;background:#0b0f1a;border-radius:4px;font-family:SFMono-Regular,Consolas,Monaco,monospace;font-size:0.8rem;min-height:140px;white-space:pre-wrap">Collecting metrics...</pre>
                <pre id="{http_id}" style="margin:0;padding:8px;background:#0b0f1a;border-radius:4px;font-family:SFMono-Regular,Consolas,Monaco,monospace;font-size:0.8rem;min-height:140px;white-space:pre-wrap">Waiting for segment data...</pre>
            </div>
            <details style="margin-top:10px" open>
                <summary style="cursor:pointer;font-weight:600">MPD Preview</summary>
                <pre id="{manifest_id}" style="margin:10px 0 0;padding:8px;background:#0b0f1a;border-radius:4px;font-family:SFMono-Regular,Consolas,Monaco,monospace;font-size:0.78rem;max-height:220px;overflow:auto;white-space:pre-wrap">Loading manifest...</pre>
            </details>
            <div id="{events_id}" style="margin-top:8px;font-family:ui-sans-serif;font-size:0.85rem;color:#fbbf24"></div>
            <div style="margin-top:6px;font-family:ui-sans-serif;font-size:0.85rem">MPD URL: <a id="{link_id}" href="#" target="_blank" rel="noreferrer noopener">resolving…</a></div>
        </div>
        <style>
        .dash-btn {{padding:5px 12px;border-radius:4px;border:1px solid #4b5563;background:#1f2937;color:#f9fafb;font-size:0.85rem;cursor:pointer}}
        .dash-btn:hover {{background:#374151}}
        </style>
        <script src="https://cdn.dashjs.org/latest/dash.all.min.js"></script>
        <script>
        (function() {{
        console.log('[DASH] Starting player initialization');
        var mpdRelative = {mpd_relative_js};
        var mpdAbsolute = {mpd_absolute_js};
        var mpdUrl = (window.location.protocol === 'https:' && mpdRelative) ? mpdRelative : (mpdAbsolute || mpdRelative);
        if (!mpdUrl) {{
            mpdUrl = mpdAbsolute || mpdRelative;
        }}
        console.log('[DASH] MPD resolved URL:', mpdUrl, 'relative:', mpdRelative, 'absolute:', mpdAbsolute);
        var manifestCache = {manifest_js};
        var container = document.getElementById('{player_id}');
        console.log('[DASH] Location href:', window.location && window.location.href);
        console.log('[DASH] Document baseURI:', document && document.baseURI);
        console.log('[DASH] DOMParser available:', typeof DOMParser);
        console.log('[DASH] crypto.randomUUID available:', !!(window.crypto && window.crypto.randomUUID));
        if (!container) {{
            console.error('[DASH] Container element not found: {player_id}');
            return;
        }}
        console.log('[DASH] Container found');
        var linkEl = document.getElementById('{link_id}');
        if (linkEl && mpdUrl) {{
            linkEl.href = mpdUrl;
            linkEl.textContent = mpdUrl;
        }}
        container.innerHTML = '';
        var video = document.createElement('video');
        video.controls = true;
        video.style.width = '100%';
        video.style.maxHeight = '40vh';
        video.style.background = '#000';
        container.appendChild(video);
        if (!window.dashjs) {{
            console.error('[DASH] dash.js library not loaded');
            container.innerHTML = '<p>dash.js failed to load.</p>';
            return;
        }}
        if (dashjs.Debug && typeof dashjs.Debug.setLogToBrowserConsole === 'function') {{
            try {{
                dashjs.Debug.setLogToBrowserConsole(true);
            }} catch (err) {{
                console.warn('[DASH] Failed to raise dash.js log level:', err);
            }}
        }}
        console.log('[DASH] dash.js library loaded, version:', dashjs.Version);
        var statsEl = document.getElementById('{stats_id}');
        var httpEl = document.getElementById('{http_id}');
        var eventsEl = document.getElementById('{events_id}');
        var manifestEl = document.getElementById('{manifest_id}');
        var player = dashjs.MediaPlayer().create();
        console.log('[DASH] Player created, initializing with URL:', mpdUrl);
        player.initialize(video, mpdUrl, false);
        console.log('[DASH] Player initialized');

        function logEvent(msg, isError) {{
            console.log('[DASH] Event:', msg, isError ? "(ERROR)" : "");
            if (!eventsEl) return;
            eventsEl.textContent = (isError ? "Error: " : "") + msg;
            eventsEl.style.color = isError ? "#f87171" : "#fbbf24";
        }}

        function formatBitrate(bits) {{
            if (!bits || isNaN(bits)) return 'n/a';
            if (bits >= 1000000) return (bits / 1000000).toFixed(2) + ' Mbps';
            return (bits / 1000).toFixed(0) + ' kbps';
        }}

        function setManifest(text) {{
            if (!manifestEl) return;
            manifestEl.textContent = text || 'Manifest unavailable.';
        }}

        if (manifestCache) {{
            console.log('[DASH] Using cached manifest');
            setManifest(manifestCache);
        }} else {{
            console.log('[DASH] Fetching manifest from:', mpdUrl);
            fetch(mpdUrl, {{cache: 'no-store'}})
                .then(function(resp) {{
                    console.log('[DASH] Manifest fetch response:', resp.status, resp.statusText);
                    return resp.ok ? resp.text() : Promise.reject(resp.status);
                }})
                .then(function(text) {{
                    console.log('[DASH] Manifest fetched, length:', text.length);
                    try {{
                        var parser = new DOMParser();
                        var doc = parser.parseFromString(text, 'application/xml');
                        var errs = doc && doc.getElementsByTagName('parsererror');
                        var hasErrors = errs && errs.length > 0;
                        console.log('[DASH] DOMParser errors present:', hasErrors);
                        if (hasErrors) {{
                            console.log('[DASH] First parser error snippet:', errs[0].textContent);
                        }}
                    }} catch (parseErr) {{
                        console.warn('[DASH] DOMParser threw:', parseErr);
                    }}
                    console.log('[DASH] Manifest preview head:', text.slice(0, 160));
                    setManifest(text);
                }})
                .catch(function(err) {{
                    console.error('[DASH] Manifest fetch failed:', err);
                    setManifest('Manifest fetch failed.');
                }});
        }}

        function refreshStats() {{
            if (!statsEl || !player || typeof player.getDashMetrics !== 'function') {{
                console.log('[DASH] refreshStats - missing dependencies');
                return;
            }}
            if (typeof player.isReady === 'function' && !player.isReady()) {{
                statsEl.textContent = 'Initializing player...';
                return;
            }}
            var metrics = player.getDashMetrics();
            var adapter = player.getDashAdapter ? player.getDashAdapter() : null;
            var active = player.getActiveStream && player.getActiveStream();
            var streamInfo = active && active.getStreamInfo ? active.getStreamInfo() : null;
            if (!metrics || !adapter || !streamInfo) {{
                statsEl.textContent = 'Collecting metrics...';
                return;
            }}
            var videoSwitch = metrics.getCurrentRepresentationSwitch('video', true);
            var audioSwitch = metrics.getCurrentRepresentationSwitch('audio', true);
            var videoBandwidth = videoSwitch ? adapter.getBandwidthForRepresentation(videoSwitch.to, streamInfo) : null;
            var audioBandwidth = audioSwitch ? adapter.getBandwidthForRepresentation(audioSwitch.to, streamInfo) : null;
            var videoBuffer = metrics.getCurrentBufferLevel('video');
            var audioBuffer = metrics.getCurrentBufferLevel('audio');
            var dropped = metrics.getCurrentDroppedFrames();
            var droppedCount = dropped && dropped.count ? dropped.count : 0;
            var liveLatency = typeof player.getCurrentLiveLatency === 'function' ? player.getCurrentLiveLatency() : null;
            var text = [
                'Video bitrate: ' + formatBitrate(videoBandwidth),
                'Audio bitrate: ' + formatBitrate(audioBandwidth),
                'Buffer (video/audio): ' + (videoBuffer ? videoBuffer.toFixed(2) : '0.00') + ' s / ' + (audioBuffer ? audioBuffer.toFixed(2) : '0.00') + ' s',
                'Dropped frames: ' + droppedCount,
                'Playback position: ' + (video.currentTime || 0).toFixed(2) + ' s',
                'Playback rate: ' + video.playbackRate.toFixed(2),
                'Resolution: ' + ((video.videoWidth && video.videoHeight) ? (video.videoWidth + 'x' + video.videoHeight) : 'n/a'),
                'Live latency: ' + (liveLatency ? liveLatency.toFixed(2) + ' s' : 'n/a'),
                'Muted: ' + (video.muted ? 'yes' : 'no')
            ].join('\\n');
            statsEl.textContent = text;
        }}

        function refreshHttp() {{
            if (!httpEl || !player || typeof player.getDashMetrics !== 'function') return;
            var metrics = player.getDashMetrics();
            if (!metrics || !metrics.getHttpRequests) {{
                httpEl.textContent = 'Waiting for segment data...';
                return;
            }}
            var requests = metrics.getHttpRequests('video');
            if (!requests || !requests.length) {{
                httpEl.textContent = 'Waiting for segment data...';
                return;
            }}
            var last = requests[requests.length - 1];
            var latency = (last.tresponse && last.trequest) ? Math.max(0, Math.round(last.tresponse - last.trequest)) : null;
            var bytes = 0;
            if (last.trace && last.trace.length) {{
                for (var i = 0; i < last.trace.length; i++) {{
                    bytes += last.trace[i].b || 0;
                }}
            }}
            var name = last.url ? last.url.split('/').pop() : 'n/a';
            var text = [
                'Segment: ' + name,
                'HTTP status: ' + (last.responsecode || 'n/a'),
                'Latency: ' + (latency !== null ? latency + ' ms' : 'n/a'),
                'Downloaded: ' + (bytes ? bytes + ' B' : 'n/a')
            ].join('\\n');
            httpEl.textContent = text;
        }}

        setInterval(refreshStats, 1000);
        setInterval(refreshHttp, 1500);
        refreshStats();
        refreshHttp();

        var reloadBtn = document.getElementById('{controls_id}-reload');
        if (reloadBtn) {{
            reloadBtn.addEventListener('click', function() {{
                player.attachSource(mpdUrl);
                logEvent('Stream reloaded', false);
            }});
        }}
        var playBtn = document.getElementById('{controls_id}-play');
        if (playBtn) {{
            playBtn.addEventListener('click', function() {{
                if (video.paused) {{
                    video.play();
                }} else {{
                    video.pause();
                }}
            }});
        }}
        var resetBtn = document.getElementById('{controls_id}-reset');
        if (resetBtn) {{
            resetBtn.addEventListener('click', function() {{
                player.reset();
                player = dashjs.MediaPlayer().create();
                player.initialize(video, mpdUrl, false);
                logEvent('Player reset', false);
            }});
        }}
        var muteBtn = document.getElementById('{controls_id}-mute');
        if (muteBtn) {{
            muteBtn.addEventListener('click', function() {{
                video.muted = !video.muted;
                refreshStats();
            }});
        }}
        var copyBtn = document.getElementById('{controls_id}-copy');
        if (copyBtn) {{
            copyBtn.addEventListener('click', function() {{
                var urlToCopy = mpdUrl || mpdAbsolute || mpdRelative || '';
                if (!urlToCopy) {{
                    logEvent('No URL to copy', true);
                    return;
                }}
                
                // Try modern clipboard API first
                if (navigator.clipboard && navigator.clipboard.writeText) {{
                    navigator.clipboard.writeText(urlToCopy).then(function() {{
                        logEvent('MPD URL copied to clipboard', false);
                    }}).catch(function(err) {{
                        console.warn('[DASH] Clipboard API failed:', err);
                        fallbackCopy(urlToCopy);
                    }});
                }} else {{
                    fallbackCopy(urlToCopy);
                }}
                
                function fallbackCopy(text) {{
                    // Fallback: create temporary textarea and use execCommand
                    var textarea = document.createElement('textarea');
                    textarea.value = text;
                    textarea.style.position = 'fixed';
                    textarea.style.top = '-9999px';
                    textarea.style.left = '-9999px';
                    document.body.appendChild(textarea);
                    textarea.select();
                    try {{
                        var success = document.execCommand('copy');
                        if (success) {{
                            logEvent('MPD URL copied (fallback method)', false);
                        }} else {{
                            logEvent('Copy failed - please copy manually', true);
                        }}
                    }} catch (err) {{
                        console.error('[DASH] Fallback copy failed:', err);
                        logEvent('Copy failed - please copy manually', true);
                    }} finally {{
                        document.body.removeChild(textarea);
                    }}
                }}
            }});
        }}
        var manifestBtn = document.getElementById('{controls_id}-manifest');
        if (manifestBtn) {{
            manifestBtn.addEventListener('click', function() {{
                setManifest('Refreshing manifest...');
                fetch(mpdUrl + '?ts=' + Date.now(), {{cache: 'no-store'}})
                    .then(function(resp) {{ return resp.ok ? resp.text() : Promise.reject(resp.status); }})
                    .then(function(text) {{
                        setManifest(text);
                        logEvent('Manifest refreshed', false);
                    }})
                    .catch(function() {{
                        setManifest('Manifest fetch failed.');
                        logEvent('Manifest refresh failed', true);
                    }});
            }});
        }}

        player.on(dashjs.MediaPlayer.events.ERROR, function(evt) {{
            console.error('[DASH] Player error event:', evt);
            if (evt && evt.error) {{
                console.error('[DASH] Error details:', {{
                    code: evt.error.code,
                    message: evt.error.message,
                    data: evt.error.data
                }});
            }}
            var message = 'Unknown error';
            if (evt && evt.error) {{
                if (evt.error.message) {{
                    message = evt.error.message;
                }} else if (evt.error.code) {{
                    message = 'Error code: ' + evt.error.code;
                }}
            }}
            logEvent(message, true);
        }});
        player.on(dashjs.MediaPlayer.events.STREAM_INITIALIZED, function() {{
            console.log('[DASH] Stream initialized event');
            logEvent('Stream initialized', false);
        }});
        player.on(dashjs.MediaPlayer.events.PLAYBACK_PLAYING, function() {{
            console.log('[DASH] Playback playing event');
            logEvent('Playback started', false);
        }});
        player.on(dashjs.MediaPlayer.events.PLAYBACK_PAUSED, function() {{
            console.log('[DASH] Playback paused event');
            logEvent('Playback paused', false);
        }});
        player.on(dashjs.MediaPlayer.events.MANIFEST_LOADED, function(evt) {{
            console.log('[DASH] Manifest loaded event:', evt);
        }});
        player.on(dashjs.MediaPlayer.events.STREAM_INITIALIZING, function() {{
            console.log('[DASH] Stream initializing event');
        }});
        console.log('[DASH] All event listeners attached');
        }})();
        </script>
        """
    
    st.components.v1.html(dash_html, height=height)


# Auto-detect browser origin and set backend URL
if "detected_backend" not in st.session_state:
    detect_script = """
    <script>
        const origin = window.location.origin;
        const protocol = window.location.protocol;
        const hostname = window.location.hostname;
        const port = window.location.port;
        
        // If accessed via HTTPS or non-standard port, use same origin for backend
        let backendUrl;
        if (protocol === 'https:' || (port && port !== '80' && port !== '8501')) {
            backendUrl = origin;
        } else {
            // Default to localhost:8000 for local development
            backendUrl = 'http://localhost:8000';
        }
        
        // Store in session storage
        sessionStorage.setItem('backendUrl', backendUrl);
        console.log('[Backend Detection] Browser origin:', origin, '-> Backend URL:', backendUrl);
        
        // Signal Streamlit to rerun with the detected URL
        window.parent.postMessage({
            type: 'streamlit:setComponentValue',
            value: backendUrl
        }, '*');
    </script>
    """
    st.components.v1.html(detect_script, height=0)
    st.session_state.detected_backend = True
    _rerun()

# Use detected backend URL as default
if "backend_url_override" not in st.session_state:
    # Try to get from PUBLIC_HTTPS_ORIGIN first
    public_origin = os.getenv("PUBLIC_HTTPS_ORIGIN", "")
    if public_origin:
        st.session_state.backend_url_override = public_origin
    else:
        st.session_state.backend_url_override = DEFAULT_BACKEND

st.sidebar.title("Server")
backend_url = st.sidebar.text_input("Backend URL", st.session_state.backend_url_override)
health_placeholder = st.sidebar.empty()

# Add link to API media endpoint
api_media_url = f"{backend_url.rstrip('/')}/api/media"
st.sidebar.markdown(f"[View all streams (API)]({api_media_url})", unsafe_allow_html=False)

# Add logout button (for nginx basic auth)
if st.sidebar.button("🔒 Logout", help="Clear authentication and logout"):
    st.markdown(
        '<meta http-equiv="refresh" content="0; url=/logout" />',
        unsafe_allow_html=True
    )


def check_health(url: str) -> bool:
    try:
        auth = get_auth()
        r = requests.get(f"{url}/healthz", timeout=3, auth=auth)
        if r.status_code == 200:
            data = r.json()
            health_placeholder.success(f"OK · {data.get('media_root', '')}")
            return True
        health_placeholder.error(f"Error {r.status_code}")
        return False
    except Exception:
        health_placeholder.warning("Unavailable")
        return False


healthy = check_health(backend_url)
st.title("MP4 Streaming Control Panel")

streams = load_streams()
media_files = sorted(MEDIA_ROOT.rglob("*.mp4"))
hls_streams: List[dict] = fetch_hls_streams(backend_url) if healthy else []

left, right = st.columns([3, 2])

with left:
    st.subheader("Streams")
    if streams:
        labels = [f"{s['name']} · {Path(s['filePath']).name}" for s in streams]
        selected_labels = st.multiselect(
            "Select streams to play",
            options=labels,
            default=labels[:1],
        )
        label_to_stream = {label: stream for label, stream in zip(labels, streams)}
        selected_streams = [label_to_stream[label] for label in selected_labels]
        if len(selected_streams) > MAX_PLAYERS:
            st.warning(f"Limiting to first {MAX_PLAYERS} streams to prevent overload.")
            selected_streams = selected_streams[:MAX_PLAYERS]
    else:
        st.info("No streams yet. Add one from the right panel.")
        selected_streams = []

    if selected_streams:
        cols_count = min(4, max(1, len(selected_streams)))
        for row in chunked(selected_streams, cols_count):
            cols = st.columns(len(row))
            for col, stream in zip(cols, row):
                with col:
                    file_path = Path(stream["filePath"]).resolve()
                    # Use relative path to avoid exposing full server directory structure
                    relative_path = file_path.relative_to(MEDIA_ROOT) if file_path.is_relative_to(MEDIA_ROOT) else file_path.name
                    # Construct video URL using backend_url with relative path
                    video_url = f"{backend_url.rstrip('/')}/video?path={relative_path}"
                    dash_manifest = stream.get("dashManifest")
                    # Construct MPD URL using backend_url instead of hardcoded localhost
                    mpd_url = f"{backend_url.rstrip('/')}/dash/{dash_manifest}" if dash_manifest else None
                    exists = file_path.exists()
                    st.markdown(f"### {stream['name']}")
                    if not exists:
                        st.error("File missing.")
                        continue
                    tabs = st.tabs(["MP4", "MPEG-DASH"])
                    with tabs[0]:
                        st.code(f"Backend URL: {video_url}", language="text")
                        html = render_video_player_html(f"{stream['streamId']}-mp4", None, video_url, height=40)
                        st.components.v1.html(html, height=340)
                    with tabs[1]:
                        if mpd_url:
                            st.code(f"Backend URL: {mpd_url}", language="text")
                            render_dash_player(stream["streamId"], mpd_url, height=520)
                        else:
                            st.info("Package this stream to enable DASH playback.")
                    size_bytes = file_path.stat().st_size
                    bitrate = estimate_bitrate(stream["streamId"], video_url) if healthy else None
                    stats = {
                        "File": file_path.name,
                        "Size": f"{size_bytes / (1024 * 1024):.2f} MB",
                        "Approx Bitrate": f"{(bitrate * 8) / 1000:.1f} kbps" if bitrate else "N/A",
                        "Created": stream["createdAt"],
                    }
                    if mpd_url:
                        stats["MPD"] = mpd_url
                    if stream.get("dashPackagedAt"):
                        stats["Packaged"] = stream["dashPackagedAt"]
                    st.write(stats)
    else:
        st.info("Select streams to preview.")

    st.subheader("Environment")
    if st.button("Recheck Health"):
        healthy = check_health(backend_url)
        time.sleep(0.3)
    st.write({
        "Backend": backend_url,
        "Media Root": str(MEDIA_ROOT),
        "Max Players": MAX_PLAYERS,
    })

    st.subheader("HLS Streams (DASH)")
    if not hls_streams:
        st.info("No HLS streams yet. Register a URL or upload an archive.")
    for entry in hls_streams:
        mpd_url = to_absolute_mpd_url(backend_url, entry.get("mpd_path"))
        status = entry.get("status", "-")
        origin = entry.get("origin", "-")
        name = entry.get("name", "")
        stream_id = entry.get("stream_id", "")
        st.markdown(f"#### {name} ({stream_id[:8]})")
        st.write({
            "Origin": origin,
            "Status": status,
            "HLS": entry.get("hls_url") or entry.get("hls_path"),
            "MPD": mpd_url,
            "Last Error": entry.get("last_error"),
        })
        if mpd_url:
            render_dash_player(f"hls-{stream_id}", mpd_url, height=420)
        delete = st.button(f"Delete {name}", key=f"del-hls-{stream_id}")
        if delete:
            try:
                auth = get_auth()
                resp = requests.delete(
                    f"{backend_url.rstrip('/')}/api/hls/streams/{stream_id}",
                    timeout=10,
                    auth=auth,
                )
                if resp.status_code == 200:
                    st.success("Deleted HLS stream")
                    _rerun()
                else:
                    parsed = parse_error_response(resp)
                    st.error(f"Delete failed: {parsed['message']}")
            except Exception as exc:
                st.error(f"Delete failed: {exc}")
        st.divider()

with right:
    st.subheader("Upload MP4")
    uploaded = st.file_uploader("Select an MP4", type=["mp4"], accept_multiple_files=False)
    if uploaded is not None:
        target = MEDIA_ROOT / uploaded.name
        with target.open("wb") as fh:
            fh.write(uploaded.read())
        st.success(f"Uploaded to {target}")
        media_files = sorted(MEDIA_ROOT.rglob("*.mp4"))

    st.subheader("Add Stream")
    if media_files:
        with st.form("add-stream-form"):
            name_input = st.text_input("Stream Name")
            file_choice = st.selectbox(
                "Source File",
                options=[path for path in media_files],
                format_func=lambda p: str(p.relative_to(MEDIA_ROOT)) if within_media_root(p) else str(p),
            )
            submit = st.form_submit_button("Save Stream")
        if submit:
            ok, msg = register_stream(streams, name_input, str(file_choice))
            if ok:
                st.success(msg)
                _rerun()
            else:
                st.error(msg)
    else:
        st.info("Upload an MP4 to create a stream.")

    with st.expander("Manage Streams", expanded=False):
        if streams:
            for stream in streams:
                file_path = Path(stream["filePath"]).resolve()
                details = f"**{stream['name']}** — {file_path.name if file_path.exists() else 'missing'}"
                st.markdown(details)
                manifest_rel = stream.get("dashManifest")
                # Use relative URL for nginx compatibility
                manifest_url = f"/dash/{manifest_rel}" if manifest_rel else None
                with st.form(f"package-{stream['streamId']}"):
                    st.caption(f"MPD: {manifest_rel or 'not generated'}")
                    show_advanced = st.checkbox(
                        "Show advanced packaging options",
                        value=False,
                        key=f"pkg-show-adv-{stream['streamId']}",
                        help="Enable advanced MPEG-DASH tuning options like live MPD, segment duration, templates, and re-encode bitrates.",
                    )
                    if show_advanced:
                        dynamic_manifest = st.checkbox(
                            "Produce dynamic/live MPD",
                            value=True,
                            key=f"pkg-dynamic-{stream['streamId']}",
                            help="Generate live-streaming manifest with rolling segment window and time-shift DVR capability",
                        )
                        segment_duration = st.number_input(
                            "Segment duration (seconds)",
                            min_value=1.0,
                            max_value=30.0,
                            value=4.0,
                            step=0.5,
                            key=f"pkg-segdur-{stream['streamId']}",
                        )
                        
                        # Live streaming specific options (only show when dynamic mode is enabled)
                        if dynamic_manifest:
                            st.markdown("**📡 Live Streaming Options**")
                            minimum_update_period = st.number_input(
                                "Minimum update period (seconds)",
                                min_value=1.0,
                                max_value=60.0,
                                value=8.0,
                                step=1.0,
                                key=f"pkg-minupdate-{stream['streamId']}",
                                help="How often players should refetch the manifest (default: 8s)",
                            )
                            suggested_presentation_delay = st.number_input(
                                "Suggested presentation delay (seconds)",
                                min_value=1.0,
                                max_value=60.0,
                                value=8.0,
                                step=1.0,
                                key=f"pkg-delay-{stream['streamId']}",
                                help="Latency buffer to prevent buffering issues (default: 8s)",
                            )
                            time_shift_buffer_depth = st.number_input(
                                "Time-shift buffer depth (seconds)",
                                min_value=60.0,
                                max_value=7200.0,
                                value=3600.0,
                                step=60.0,
                                key=f"pkg-timeshift-{stream['streamId']}",
                                help="DVR window - how far back users can rewind (default: 1 hour)",
                            )
                        else:
                            minimum_update_period = None
                            suggested_presentation_delay = None
                            time_shift_buffer_depth = None
                        
                        window_size = st.number_input(
                            "Window size (segments)",
                            min_value=2,
                            max_value=60,
                            value=6,
                            step=1,
                            key=f"pkg-window-{stream['streamId']}",
                            help="Number of segments to keep in manifest",
                        )
                        extra_window_size = st.number_input(
                            "Extra window size",
                            min_value=2,
                            max_value=60,
                            value=6,
                            step=1,
                            key=f"pkg-extra-window-{stream['streamId']}",
                            help="Additional segments beyond window for smoother playback",
                        )
                        segment_padding = st.number_input(
                            "Segment number padding (0 = none)",
                            min_value=0,
                            max_value=10,
                            value=5,
                            step=1,
                            key=f"pkg-pad-{stream['streamId']}",
                        )
                        segment_template_override = st.text_input(
                            "Media segment template override",
                            value="",
                            help="Leave blank for default. Example: people_1920_1080_30fps_chunk_$RepresentationID$_$Number$.m4s",
                            key=f"pkg-media-template-{stream['streamId']}",
                        )
                        init_template_override = st.text_input(
                            "Init segment template override",
                            value="",
                            help="Leave blank for default. Example: people_1920_1080_30fps_init_$RepresentationID$.m4s",
                            key=f"pkg-init-template-{stream['streamId']}",
                        )
                        reencode = st.checkbox(
                            "Re-encode video/audio (libx264 + AAC)",
                            value=False,
                            key=f"pkg-reencode-{stream['streamId']}",
                        )
                        video_bitrate = st.number_input(
                            "Video bitrate (kbps)",
                            min_value=500,
                            max_value=50000,
                            value=5500,
                            step=100,
                            key=f"pkg-video-br-{stream['streamId']}",
                            disabled=not reencode,
                        )
                        audio_bitrate = st.number_input(
                            "Audio bitrate (kbps)",
                            min_value=32,
                            max_value=1024,
                            value=192,
                            step=32,
                            key=f"pkg-audio-br-{stream['streamId']}",
                            disabled=not reencode,
                        )
                    else:
                        # Defaults when advanced options are hidden
                        dynamic_manifest = True
                        segment_duration = 4.0
                        minimum_update_period = 8.0
                        suggested_presentation_delay = 8.0
                        time_shift_buffer_depth = 3600.0
                        window_size = 6
                        extra_window_size = 6
                        segment_padding = 5
                        segment_template_override = ""
                        init_template_override = ""
                        reencode = False
                        video_bitrate = 5500
                        audio_bitrate = 192

                    st.caption("ℹ️ Converts MP4 to MPEG-DASH format (MPD + segments) for adaptive streaming. Use advanced options above to customize.")
                    package = st.form_submit_button("Package to DASH")
                if package:
                    payload = {"path": stream["filePath"], "stream_id": stream["streamId"]}
                    options: Dict[str, object] = {}
                    if dynamic_manifest:
                        options["mode"] = "dynamic"
                        options["segment_duration_seconds"] = float(segment_duration)
                        options["window_size"] = int(window_size)
                        options["extra_window_size"] = int(extra_window_size)
                        # Add live streaming specific options
                        if minimum_update_period:
                            options["minimum_update_period"] = float(minimum_update_period)
                        if suggested_presentation_delay:
                            options["suggested_presentation_delay"] = float(suggested_presentation_delay)
                        if time_shift_buffer_depth:
                            options["time_shift_buffer_depth"] = float(time_shift_buffer_depth)
                    if int(segment_padding) != 5:
                        options["segment_padding"] = int(segment_padding)
                    if segment_template_override.strip():
                        options["segment_template"] = segment_template_override.strip()
                    if init_template_override.strip():
                        options["init_segment_template"] = init_template_override.strip()
                    if reencode:
                        options["reencode"] = True
                        options["video_bitrate_kbps"] = int(video_bitrate)
                        options["audio_bitrate_kbps"] = int(audio_bitrate)
                    if options:
                        payload["options"] = options
                    try:
                        with st.spinner("Packaging to DASH (requires ffmpeg)..."):
                            resp = requests.post(
                                f"{backend_url.rstrip('/')}/api/dash/package",
                                json=payload,
                                timeout=120,
                            )
                        if resp.status_code == 200:
                            data = resp.json()
                            manifest_path = data.get("manifest")
                            set_stream_manifest(streams, stream["streamId"], manifest_path)
                            # Update manifest_url to use backend_url instead of hardcoded localhost
                            if manifest_path:
                                manifest_url = f"{backend_url.rstrip('/')}{manifest_path}"
                            st.success("DASH packaging complete.")
                            _rerun()
                        else:
                            parsed = parse_error_response(resp)
                            st.error(f"Packaging failed ({resp.status_code}): {parsed['message']}")
                            if parsed["stderr"]:
                                st.caption("ffmpeg stderr")
                                st.code(parsed["stderr"], language="text")
                    except Exception as exc:
                        st.error(f"Packaging request failed: {exc}")
                if manifest_url:
                    st.caption("MPD URL (for external players/clients):")
                    st.code(manifest_url, language="text")
                with st.form(f"delete-{stream['streamId']}"):
                    delete_file = st.checkbox(
                        "Also delete file",
                        value=False,
                        help="When checked, deletes both the stream registration and the original MP4 file. When unchecked, only removes the stream from the registry while keeping the source file.",
                    )
                    delete = st.form_submit_button("Delete Stream")
                if delete:
                    ok, msg = remove_stream(streams, stream["streamId"], delete_file)
                    if ok:
                        st.success(msg)
                        _rerun()
                    else:
                        st.error(msg)
                st.divider()
        else:
            st.info("No streams registered yet.")

    st.subheader("Register HLS Stream (URL)")
    with st.form("register-hls-url-form"):
        hls_name = st.text_input("Stream Name", key="hls-name")
        hls_url = st.text_input("Public HLS URL (.m3u8)", key="hls-url")
        hls_mode = st.selectbox("Mode", options=["live", "static"], index=0)
        hls_seg = st.number_input("Segment duration (s)", min_value=1.0, max_value=20.0, value=4.0, step=0.5)
        hls_window = st.number_input("Window size", min_value=2, max_value=60, value=6, step=1)
        hls_extra = st.number_input("Extra window size", min_value=2, max_value=120, value=6, step=1)
        submit_hls = st.form_submit_button("Register HLS URL")
    if submit_hls:
        if not hls_name or not hls_url:
            st.error("Name and HLS URL are required")
        else:
            payload = {
                "name": hls_name.strip(),
                "hls_url": hls_url.strip(),
                "mode": hls_mode,
                "segment_duration_seconds": float(hls_seg),
                "window_size": int(hls_window),
                "extra_window_size": int(hls_extra),
            }
            try:
                with st.spinner("Registering HLS stream..."):
                    auth = get_auth()
                    resp = requests.post(
                        f"{backend_url.rstrip('/')}/api/hls/register",
                        json=payload,
                        timeout=20,
                        auth=auth,
                    )
                if resp.status_code in (200, 201):
                    data = resp.json()
                    st.success(f"Registered. MPD: {data.get('mpd_path')}")
                    _rerun()
                else:
                    parsed = parse_error_response(resp)
                    st.error(f"Failed: {parsed['message']}")
                    if parsed["stderr"]:
                        st.caption("ffmpeg stderr")
                        st.code(parsed["stderr"], language="text")
            except Exception as exc:
                st.error(f"Request failed: {exc}")

    st.subheader("Upload HLS Files (ZIP)")
    with st.form("upload-hls-form"):
        upload_hls_name = st.text_input("Stream Name", key="upload-hls-name")
        upload_hls_file = st.file_uploader("HLS archive (.zip with .m3u8 + .ts)", type=["zip"], key="upload-hls-zip")
        submit_upload_hls = st.form_submit_button("Upload & Convert")
    if submit_upload_hls:
        if not upload_hls_name or not upload_hls_file:
            st.error("Name and zip file are required")
        else:
            files = {"file": (upload_hls_file.name, upload_hls_file.getvalue(), "application/zip")}
            data = {"name": upload_hls_name.strip()}
            try:
                with st.spinner("Uploading and converting to DASH..."):
                    auth = get_auth()
                    resp = requests.post(
                        f"{backend_url.rstrip('/')}/api/hls/upload",
                        files=files,
                        data=data,
                        timeout=60,
                        auth=auth,
                    )
                if resp.status_code in (200, 201):
                    payload = resp.json()
                    st.success(f"Uploaded. MPD: {payload.get('mpd_path')}")
                    _rerun()
                else:
                    parsed = parse_error_response(resp)
                    st.error(f"Upload failed: {parsed['message']}")
                    if parsed["stderr"]:
                        st.caption("ffmpeg stderr")
                        st.code(parsed["stderr"], language="text")
            except Exception as exc:
                st.error(f"Upload failed: {exc}")

    st.subheader("Diagnostics")
    st.info("🔍 Test the video streaming endpoint directly. Verifies backend connectivity, path validation, and range request handling. Shows raw HTTP response details useful for debugging infrastructure issues.", icon="ℹ️")
    with st.form("diagnostics-form"):
        if media_files:
            file_options = [str(p.relative_to(MEDIA_ROOT)) if within_media_root(p) else str(p) for p in media_files]
            diag_path = st.selectbox("Path to test", options=file_options)
        else:
            diag_path = st.text_input("Path to test", value="", placeholder="No MP4 files available")
        diag_range = st.text_input("Range header (optional)", value="bytes=0-0")
        submit_diag = st.form_submit_button("Test Stream")
    if submit_diag:
        params = {"path": diag_path}
        headers = {}
        if diag_range.strip():
            headers["Range"] = diag_range.strip()
        try:
            auth = get_auth()
            resp = requests.get(
                f"{backend_url}/video",
                params=params,
                headers=headers,
                stream=True,
                timeout=5,
                auth=auth,
            )
            status = resp.status_code
            info = {
                "Status": status,
                "Content-Type": resp.headers.get("content-type"),
                "Accept-Ranges": resp.headers.get("accept-ranges"),
                "Content-Range": resp.headers.get("content-range"),
                "Content-Length": resp.headers.get("content-length"),
            }
            st.write(info)
            if status in (200, 206):
                st.success("Stream serving correctly.")
            else:
                try:
                    detail = resp.json()
                except Exception:
                    detail = resp.text[:300]
                st.error(f"Error {status}: {detail}")
        except Exception as exc:
            st.error(f"Request failed: {exc}")
        finally:
            try:
                resp.close()
            except Exception:
                pass
