from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import time
import uuid
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterator, Optional, List, Literal, Dict, Any

from dotenv import load_dotenv, find_dotenv
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.responses import StreamingResponse, JSONResponse

# Load environment variables from .env if present
load_dotenv(find_dotenv(), override=False)

CHUNK_SIZE = int(os.getenv("CHUNK_SIZE_BYTES", "1048576"))
MEDIA_ROOT = os.getenv("MEDIA_ROOT", "media")
DASH_ROOT = os.getenv("DASH_ROOT", str(Path(MEDIA_ROOT).resolve() / "dash"))
DASH_RETENTION_DAYS = int(os.getenv("DASH_RETENTION_DAYS", "0"))
HLS_ROOT = os.getenv("HLS_ROOT", str(Path(MEDIA_ROOT).resolve() / "hls"))
HLS_METADATA_FILE = Path(MEDIA_ROOT).resolve() / ".hls_streams.json"

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger("mp4_stream")

PACKAGING_METRICS = {
    "requests": 0,
    "success": 0,
    "failure": 0,
    "avg_duration_ms": 0.0,
}

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_dash_root = Path(DASH_ROOT).resolve()
_dash_root.mkdir(parents=True, exist_ok=True)
app.mount("/dash", StaticFiles(directory=str(_dash_root), html=False), name="dash")

_hls_root = Path(HLS_ROOT).resolve()
_hls_root.mkdir(parents=True, exist_ok=True)

# Track running ffmpeg PIDs for live HLS ingests
_hls_processes: Dict[str, subprocess.Popen] = {}


def _resolve_and_validate(path_str: str) -> Path:
    if not path_str:
        raise HTTPException(status_code=400, detail="path is required")
    root = Path(MEDIA_ROOT).resolve()
    candidate = Path(path_str)
    if not candidate.is_absolute():
        candidate = (root / candidate).resolve()
    else:
        candidate = candidate.resolve()
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("validating path=%s resolved=%s root=%s", path_str, candidate, root)
    try:
        common = os.path.commonpath([str(candidate), str(root)])
    except ValueError:
        raise HTTPException(status_code=403, detail="invalid path")
    if Path(common) != root:
        raise HTTPException(status_code=403, detail="forbidden path")
    if not candidate.is_file():
        raise HTTPException(status_code=404, detail="file not found")
    if candidate.suffix.lower() != ".mp4":
        raise HTTPException(status_code=400, detail="unsupported file type")
    return candidate


def _file_size(p: Path) -> int:
    return p.stat().st_size


def _range_parser(range_header: str, size: int) -> Optional[tuple[int, int]]:
    if not range_header or not range_header.startswith("bytes="):
        return None
    spec = range_header.split("=", 1)[1].strip()
    if "," in spec:
        raise HTTPException(status_code=416, detail="multiple ranges unsupported")
    start_str, end_str = (spec.split("-", 1) + [""])[:2]
    if start_str == "" and end_str == "":
        raise HTTPException(status_code=416, detail="invalid range")
    if start_str == "":
        length = int(end_str)
        start = size - length
        end = size - 1
    else:
        start = int(start_str)
        end = int(end_str) if end_str != "" else size - 1
    if start < 0 or end < start or start >= size:
        raise HTTPException(status_code=416, detail="range not satisfiable")
    end = min(end, size - 1)
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "parsed range header=%s start=%s end=%s size=%s",
            range_header,
            start,
            end,
            size,
        )
    return (start, end)


def _iter_file(p: Path, start: int = 0, end: Optional[int] = None) -> Iterator[bytes]:
    with p.open("rb") as f:
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "streaming file=%s start=%s end=%s chunk_size=%s",
                p,
                start,
                end,
                CHUNK_SIZE,
            )
        f.seek(start)
        remaining = None if end is None else (end - start + 1)
        while True:
            chunk_size = CHUNK_SIZE if remaining is None else min(CHUNK_SIZE, remaining)
            data = f.read(chunk_size)
            if not data:
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug("stream complete file=%s", p)
                break
            yield data
            if remaining is not None:
                remaining -= len(data)
                if remaining <= 0:
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug("stream finished range file=%s bytes_sent=%s", p, end - start + 1)
                    break


def _ensure_ffmpeg_available() -> None:
    if shutil.which("ffmpeg") is None:
        raise HTTPException(status_code=500, detail="ffmpeg is required for DASH packaging but was not found in PATH")


def _load_hls_streams() -> List[Dict[str, Any]]:
    if not HLS_METADATA_FILE.exists():
        return []
    try:
        with HLS_METADATA_FILE.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
            return data if isinstance(data, list) else []
    except Exception:
        logger.exception("failed to load HLS metadata")
        return []


def _save_hls_streams(streams: List[Dict[str, Any]]) -> None:
    try:
        with HLS_METADATA_FILE.open("w", encoding="utf-8") as fh:
            json.dump(streams, fh, indent=2)
    except Exception:
        logger.exception("failed to save HLS metadata")


def _validate_hls_url(value: str) -> str:
    if not value:
        raise HTTPException(status_code=400, detail="hls_url is required")
    parsed = value.strip()
    if not parsed.startswith("http://") and not parsed.startswith("https://"):
        raise HTTPException(status_code=400, detail="hls_url must be http(s)")
    if ".m3u8" not in parsed.lower():
        logger.warning("hls_url does not contain .m3u8 extension: %s", parsed)
    return parsed


def _is_pid_running(pid: Optional[int]) -> bool:
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def _build_hls_dash_command(source: str, manifest: Path, mode: Literal["live", "static"], segment_duration: float, window_size: int, extra_window_size: int) -> List[str]:
    media_template = "chunk-stream$RepresentationID$-$Number%05d$.m4s"
    init_template = "init-stream$RepresentationID$.m4s"
    cmd: List[str] = [
        "ffmpeg",
        "-y",
        "-i",
        source,
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
        "-c:v",
        "copy",
        "-c:a",
        "copy",
    ]

    dash_args: List[str] = [
        "-f",
        "dash",
        "-use_template",
        "1",
        "-use_timeline",
        "1",
        "-init_seg_name",
        init_template,
        "-media_seg_name",
        media_template,
    ]

    if mode == "live":
        dash_args.extend([
            "-seg_duration",
            str(segment_duration),
            "-streaming",
            "1",
            "-ldash",
            "1",
            "-window_size",
            str(window_size),
            "-extra_window_size",
            str(extra_window_size),
            "-remove_at_exit",
            "1",
        ])
    else:
        dash_args.extend([
            "-seg_duration",
            str(segment_duration),
            "-min_seg_duration",
            "2000000",
        ])

    cmd.extend(dash_args)
    cmd.append(str(manifest))
    return cmd


def _refresh_hls_status(streams: List[Dict[str, Any]]) -> None:
    updated = False
    for stream in streams:
        pid = stream.get("pid")
        status = stream.get("status")
        if pid:
            running = _is_pid_running(pid)
            if running and status not in {"running", "starting"}:
                stream["status"] = "running"
                updated = True
            if not running and status not in {"completed", "stopped", "error"}:
                stream["status"] = "stopped"
                updated = True
    if updated:
        _save_hls_streams(streams)


def _find_first_m3u8(directory: Path) -> Optional[Path]:
    for path in sorted(directory.rglob("*.m3u8")):
        if path.is_file():
            return path
    return None


def _package_hls_upload_to_dash(stream_id: str, playlist_path: Path, segment_duration: float = 4.0) -> Path:
    _ensure_ffmpeg_available()
    output_dir = _dash_root / stream_id
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = output_dir / "manifest.mpd"
    cmd = _build_hls_dash_command(str(playlist_path), manifest, "static", segment_duration, 6, 6)
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode("utf-8", errors="ignore") if exc.stderr else ""
        raise HTTPException(status_code=500, detail={"error": "ffmpeg packaging failed", "stderr": stderr})
    if not manifest.exists():
        raise HTTPException(status_code=500, detail="manifest not generated for uploaded HLS")
    return manifest


def _start_hls_ingest(request: HlsRegisterRequest) -> HlsStream:
    _ensure_ffmpeg_available()
    stream_id = uuid.uuid4().hex
    output_dir = _dash_root / stream_id
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = output_dir / "manifest.mpd"
    log_path = output_dir / "ffmpeg.log"
    cmd = _build_hls_dash_command(
        request.hls_url,
        manifest,
        request.mode,
        float(request.segment_duration_seconds or 4.0),
        int(request.window_size or 6),
        int(request.extra_window_size or (request.window_size or 6)),
    )

    if request.mode == "static":
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.decode("utf-8", errors="ignore") if exc.stderr else ""
            raise HTTPException(status_code=500, detail={"error": "ffmpeg packaging failed", "stderr": stderr})
        status = "completed"
        pid = None
    else:
        try:
            log_file = log_path.open("w", encoding="utf-8")
        except Exception:
            log_file = subprocess.DEVNULL
        try:
            proc = subprocess.Popen(cmd, stdout=log_file, stderr=log_file)
        except Exception as exc:
            raise HTTPException(status_code=500, detail={"error": "failed to start ffmpeg", "stderr": str(exc)})
        _hls_processes[stream_id] = proc
        status = "running"
        pid = proc.pid

    if not manifest.exists():
        logger.warning("manifest not yet generated for stream_id=%s mode=%s", stream_id, request.mode)

    mpd_path = f"/dash/{stream_id}/manifest.mpd"
    stream = HlsStream(
        stream_id=stream_id,
        name=request.name.strip(),
        origin="url",
        hls_url=request.hls_url,
        mpd_path=mpd_path,
        created_at=datetime.utcnow().isoformat() + "Z",
        mode=request.mode,
        status=status,
        pid=pid,
        log_path=str(log_path) if log_path else None,
    )
    return stream


class PackageOptions(BaseModel):
    mode: Literal["static", "dynamic"] = "dynamic"
    reencode: bool = False
    video_bitrate_kbps: Optional[int] = None
    audio_bitrate_kbps: Optional[int] = None
    segment_padding: Optional[int] = 5
    segment_template: Optional[str] = None
    init_segment_template: Optional[str] = None
    segment_duration_seconds: Optional[float] = None
    window_size: Optional[int] = None
    extra_window_size: Optional[int] = None
    minimum_update_period: Optional[float] = None
    suggested_presentation_delay: Optional[float] = None
    time_shift_buffer_depth: Optional[float] = None


def _format_bitrate_kbps(value: Optional[int], default: Optional[int]) -> Optional[str]:
    target = value if value is not None else default
    if target is None or target <= 0:
        return None
    return f"{target}k"


def _package_to_dash(source: Path, output_dir: Path, options: Optional[PackageOptions] = None) -> Path:
    _ensure_ffmpeg_available()
    opts = options or PackageOptions()
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "packaging DASH source=%s output_dir=%s mode=%s reencode=%s",
            source,
            output_dir,
            opts.mode,
            opts.reencode,
        )
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = output_dir / "manifest.mpd"

    segment_padding = opts.segment_padding if opts.segment_padding is not None else 5
    number_token = f"$Number%0{segment_padding}d$" if segment_padding and segment_padding > 0 else "$Number$"
    media_template = (
        opts.segment_template
        if opts.segment_template
        else f"chunk-stream$RepresentationID$-{number_token}.m4s"
    )
    init_template = opts.init_segment_template or "init-stream$RepresentationID$.m4s"

    cmd: List[str] = [
        "ffmpeg",
        "-y",
        "-i",
        str(source),
        "-map",
        "0:v",
        "-map",
        "0:a?",
    ]

    need_reencode = opts.reencode or opts.video_bitrate_kbps is not None or opts.audio_bitrate_kbps is not None
    if need_reencode:
        video_bitrate = _format_bitrate_kbps(opts.video_bitrate_kbps, 5500)
        audio_bitrate = _format_bitrate_kbps(opts.audio_bitrate_kbps, 192)
        cmd.extend([
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-profile:v",
            "main",
        ])
        segment_duration = opts.segment_duration_seconds or 4.0
        keyint = max(1, int(round(segment_duration * 2))) * 12
        cmd.extend(["-g", str(keyint)])
        if video_bitrate:
            cmd.extend(["-b:v", video_bitrate, "-maxrate", video_bitrate, "-bufsize", video_bitrate])
        else:
            cmd.extend(["-crf", "20"])
        cmd.extend(["-c:a", "aac"])
        if audio_bitrate:
            cmd.extend(["-b:a", audio_bitrate])
    else:
        cmd.extend(["-c:v", "copy", "-c:a", "copy"])

    dash_args: List[str] = [
        "-f",
        "dash",
        "-use_template",
        "1",
        "-use_timeline",
        "1",
        "-init_seg_name",
        init_template,
        "-media_seg_name",
        media_template,
    ]

    if opts.mode == "dynamic":
        dash_args.extend(["-streaming", "1", "-ldash", "1"])
        seg_duration = opts.segment_duration_seconds or 4.0
        dash_args.extend(["-seg_duration", f"{seg_duration}"])
        window_size = opts.window_size or 5
        extra_window_size = opts.extra_window_size or window_size
        dash_args.extend([
            "-window_size",
            str(window_size),
            "-extra_window_size",
            str(extra_window_size),
        ])
        # Use update_period instead of minimum_update_period (ffmpeg parameter name)
        if opts.minimum_update_period:
            dash_args.extend(["-update_period", str(int(opts.minimum_update_period))])
        # Note: suggested_presentation_delay and time_shift_buffer_depth are not directly
        # supported by ffmpeg's dash muxer - they would need post-processing of the MPD
        # or use of a different DASH packager like Shaka Packager or MP4Box
    else:
        dash_args.extend(["-min_seg_duration", "2000000"])

    cmd.extend(dash_args)
    cmd.append(str(manifest))

    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode("utf-8", errors="ignore") if exc.stderr else ""
        stderr_snippet = stderr.strip().splitlines()
        stderr_snippet = "\n".join(stderr_snippet[-10:]) if stderr_snippet else ""
        logger.error("ffmpeg packaging failed: %s", stderr_snippet or stderr)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "ffmpeg packaging failed",
                "stderr": stderr_snippet or stderr,
            },
        )
    if not manifest.exists():
        raise HTTPException(status_code=500, detail="manifest not generated")
    
    # Post-process MPD for dynamic mode to add missing attributes
    if opts.mode == "dynamic":
        _enhance_dynamic_mpd(manifest, opts)
    
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("dash manifest generated=%s", manifest)
    return manifest


def _enhance_dynamic_mpd(manifest_path: Path, opts: PackageOptions) -> None:
    """Add live streaming attributes not supported by ffmpeg's dash muxer"""
    try:
        import xml.etree.ElementTree as ET
        from datetime import datetime, timezone
        
        # Register namespaces to preserve them
        ET.register_namespace('', 'urn:mpeg:dash:schema:mpd:2011')
        ET.register_namespace('xsi', 'http://www.w3.org/2001/XMLSchema-instance')
        ET.register_namespace('xlink', 'http://www.w3.org/1999/xlink')
        
        # Parse the MPD
        tree = ET.parse(manifest_path)
        root = tree.getroot()
        
        # Change type from static to dynamic
        root.set('type', 'dynamic')
        
        # Remove mediaPresentationDuration (not used in dynamic manifests)
        if 'mediaPresentationDuration' in root.attrib:
            del root.attrib['mediaPresentationDuration']
        
        # Add minimum update period
        update_period = int(opts.minimum_update_period or 8)
        root.set('minimumUpdatePeriod', f'PT{update_period}S')
        
        # Add suggested presentation delay
        if opts.suggested_presentation_delay:
            delay_seconds = int(opts.suggested_presentation_delay)
            root.set('suggestedPresentationDelay', f'PT{delay_seconds}S')
        
        # Add time-shift buffer depth
        if opts.time_shift_buffer_depth:
            depth_seconds = int(opts.time_shift_buffer_depth)
            root.set('timeShiftBufferDepth', f'PT{depth_seconds}S')
        
        # Add availability start time (current time)
        avail_start = datetime.now(timezone.utc)
        root.set('availabilityStartTime', avail_start.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z')
        
        # Add publish time (current UTC time)
        publish_time = datetime.now(timezone.utc)
        root.set('publishTime', publish_time.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z')
        
        # Write back the modified MPD
        tree.write(manifest_path, encoding="utf-8", xml_declaration=True)
        
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("enhanced dynamic MPD with live streaming attributes")
    except Exception as e:
        logger.warning("failed to enhance dynamic MPD: %s", e)
        # Non-fatal - continue with basic MPD


def _record_packaging_metrics(success: bool, duration_ms: float) -> None:
    PACKAGING_METRICS["requests"] += 1
    if success:
        PACKAGING_METRICS["success"] += 1
    else:
        PACKAGING_METRICS["failure"] += 1
    prev = PACKAGING_METRICS["avg_duration_ms"]
    count = PACKAGING_METRICS["requests"]
    PACKAGING_METRICS["avg_duration_ms"] = prev + ((duration_ms - prev) / count)


def _cleanup_dash_outputs(retention_days: int) -> None:
    if retention_days <= 0:
        return
    cutoff = datetime.utcnow() - timedelta(days=retention_days)
    for child in _dash_root.iterdir():
        try:
            if not child.is_dir():
                continue
            modified = datetime.utcfromtimestamp(child.stat().st_mtime)
            if modified < cutoff:
                shutil.rmtree(child, ignore_errors=True)
                logger.info("pruned DASH output dir=%s older_than_days=%s", child.name, retention_days)
        except Exception:
            logger.exception("failed pruning DASH output dir=%s", child)


def _collect_media_files(base: Path, suffix: str, url_prefix: Optional[str] = None) -> List[dict]:
    results: List[dict] = []
    if not base.exists():
        return results
    for path in sorted(base.rglob(f"*{suffix}")):
        if not path.is_file():
            continue
        stat = path.stat()
        try:
            rel = str(path.relative_to(base))
        except ValueError:
            rel = path.name
        item = {
            "path": rel,
            "absolute_path": str(path),
            "size_bytes": stat.st_size,
            "modified_at": datetime.utcfromtimestamp(stat.st_mtime).isoformat() + "Z",
        }
        if url_prefix is not None:
            item["url"] = f"{url_prefix}/{rel}"
        results.append(item)
    return results


class PackageRequest(BaseModel):
    path: str
    stream_id: Optional[str] = None
    options: Optional[PackageOptions] = None


class PackageResponse(BaseModel):
    manifest: str
    output_dir: str


class MediaFile(BaseModel):
    path: str
    absolute_path: str
    size_bytes: int
    modified_at: str
    url: Optional[str] = None


class MediaListResponse(BaseModel):
    mp4: List[MediaFile]
    mpd: List[MediaFile]


class HlsRegisterRequest(BaseModel):
    name: str
    hls_url: str
    mode: Literal["live", "static"] = "live"
    segment_duration_seconds: Optional[float] = 4.0
    window_size: Optional[int] = 6
    extra_window_size: Optional[int] = 6


class HlsStream(BaseModel):
    stream_id: str
    name: str
    origin: Literal["url", "upload"]
    hls_url: Optional[str] = None
    hls_path: Optional[str] = None
    mpd_path: str
    created_at: str
    mode: Literal["live", "static"] = "live"
    status: Literal["starting", "running", "completed", "stopped", "error"] = "starting"
    last_error: Optional[str] = None
    pid: Optional[int] = None
    log_path: Optional[str] = None


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    range_header = request.headers.get("range")
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.exception(
            "request failed method=%s path=%s range=%s duration_ms=%.2f client=%s",
            request.method,
            request.url.path,
            range_header or "-",
            duration_ms,
            request.client.host if request.client else "-",
        )
        raise

    duration_ms = (time.perf_counter() - start) * 1000
    bytes_served = response.headers.get("content-length") or "-"
    logger.info(
        "handled request method=%s path=%s status=%s duration_ms=%.2f bytes=%s range=%s client=%s",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
        bytes_served,
        range_header or "-",
        request.client.host if request.client else "-",
    )
    return response


@app.get("/healthz")
async def healthz():
    return JSONResponse(
        {
            "status": "ok",
            "media_root": str(Path(MEDIA_ROOT).resolve()),
            "dash_root": str(_dash_root),
            "dash_retention_days": DASH_RETENTION_DAYS,
            "packaging_metrics": dict(PACKAGING_METRICS),
        }
    )


@app.get("/video")
async def video(request: Request, path: str):
    p = _resolve_and_validate(path)
    size = _file_size(p)
    range_header = request.headers.get("range")
    rng = _range_parser(range_header, size) if range_header else None
    headers = {"Content-Type": "video/mp4", "Accept-Ranges": "bytes"}
    if rng is None:
        headers["Content-Length"] = str(size)
        return StreamingResponse(_iter_file(p, 0, None), status_code=200, headers=headers)
    start, end = rng
    headers["Content-Range"] = f"bytes {start}-{end}/{size}"
    headers["Content-Length"] = str(end - start + 1)
    return StreamingResponse(_iter_file(p, start, end), status_code=206, headers=headers)


@app.get("/api/media", response_model=MediaListResponse)
async def list_media(request: Request):
    media_root = Path(MEDIA_ROOT).resolve()
    base_url = str(request.base_url).rstrip("/")
    mp4_files = _collect_media_files(media_root, ".mp4")
    mpd_files = _collect_media_files(_dash_root, ".mpd", url_prefix=f"{base_url}/dash")
    return MediaListResponse(mp4=mp4_files, mpd=mpd_files)


@app.post("/api/dash/package", response_model=PackageResponse)
async def package_dash(body: PackageRequest):
    source = _resolve_and_validate(body.path)
    subdir = body.stream_id or f"{source.stem}-{uuid.uuid4().hex[:6]}"
    output_dir = _dash_root / subdir
    start_time = time.perf_counter()
    try:
        manifest = _package_to_dash(source, output_dir, body.options)
    except HTTPException:
        duration_ms = (time.perf_counter() - start_time) * 1000
        _record_packaging_metrics(False, duration_ms)
        raise
    duration_ms = (time.perf_counter() - start_time) * 1000
    _record_packaging_metrics(True, duration_ms)
    if DASH_RETENTION_DAYS > 0:
        _cleanup_dash_outputs(DASH_RETENTION_DAYS)
    manifest_rel = manifest.relative_to(_dash_root)
    logger.info(
        "packaged DASH manifest=%s source=%s output=%s",
        manifest_rel,
        source,
        output_dir,
    )
    logger.debug(
        "packaging metrics updated duration_ms=%.2f requests=%s success=%s failure=%s",
        duration_ms,
        PACKAGING_METRICS["requests"],
        PACKAGING_METRICS["success"],
        PACKAGING_METRICS["failure"],
    )
    return PackageResponse(manifest=str(manifest_rel), output_dir=str(output_dir.relative_to(_dash_root)))


@app.post("/api/hls/register", response_model=HlsStream)
async def register_hls(body: HlsRegisterRequest):
    validated_url = _validate_hls_url(body.hls_url)
    request_model = HlsRegisterRequest(**{**body.dict(), "hls_url": validated_url})
    streams = _load_hls_streams()
    name_normalized = request_model.name.strip().lower()
    if any(s.get("name", "").lower() == name_normalized for s in streams):
        raise HTTPException(status_code=400, detail="A stream with that name already exists")
    stream = _start_hls_ingest(request_model)
    streams.append(stream.dict())
    _save_hls_streams(streams)
    return stream


@app.post("/api/hls/upload", response_model=HlsStream)
async def upload_hls(name: str = Form(...), file: UploadFile = File(...)):
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    _ensure_ffmpeg_available()
    if file.content_type not in {"application/zip", "application/octet-stream", "multipart/form-data", "binary/octet-stream"}:
        logger.warning("upload content type unexpected: %s", file.content_type)

    stream_id = uuid.uuid4().hex
    stream_dir = _hls_root / stream_id
    stream_dir.mkdir(parents=True, exist_ok=True)
    archive_path = stream_dir / (file.filename or "upload.zip")
    with archive_path.open("wb") as dest:
        dest.write(await file.read())

    try:
        with zipfile.ZipFile(archive_path, "r") as zf:
            for member in zf.infolist():
                resolved_target = (stream_dir / member.filename).resolve()
                try:
                    common = os.path.commonpath([str(resolved_target), str(stream_dir.resolve())])
                except ValueError:
                    raise HTTPException(status_code=400, detail="zip contains illegal paths")
                if Path(common) != stream_dir.resolve():
                    raise HTTPException(status_code=400, detail="zip contains illegal paths")
            zf.extractall(stream_dir)
    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=400, detail=f"invalid zip: {exc}")
    try:
        archive_path.unlink(missing_ok=True)
    except Exception:
        pass

    playlist = _find_first_m3u8(stream_dir)
    if playlist is None:
        raise HTTPException(status_code=400, detail="Uploaded archive does not contain an .m3u8 playlist")

    manifest = _package_hls_upload_to_dash(stream_id, playlist)
    rel_hls_path = None
    try:
        rel_hls_path = str(playlist.relative_to(_hls_root))
    except ValueError:
        rel_hls_path = str(playlist)

    stream = HlsStream(
        stream_id=stream_id,
        name=name.strip(),
        origin="upload",
        hls_path=rel_hls_path,
        mpd_path=f"/dash/{stream_id}/manifest.mpd",
        created_at=datetime.utcnow().isoformat() + "Z",
        mode="static",
        status="completed",
    )
    streams = _load_hls_streams()
    streams.append(stream.dict())
    _save_hls_streams(streams)
    return stream


@app.get("/api/hls/streams")
async def list_hls_streams():
    streams = _load_hls_streams()
    _refresh_hls_status(streams)
    return streams


@app.delete("/api/hls/streams/{stream_id}")
async def delete_hls_stream(stream_id: str):
    streams = _load_hls_streams()
    idx = next((i for i, s in enumerate(streams) if s.get("stream_id") == stream_id), None)
    if idx is None:
        raise HTTPException(status_code=404, detail="stream not found")

    entry = streams.pop(idx)
    pid = entry.get("pid")
    if pid and _is_pid_running(pid):
        try:
            os.kill(pid, 15)
        except Exception:
            logger.exception("failed to terminate ffmpeg pid=%s", pid)
        _hls_processes.pop(stream_id, None)

    dash_dir = _dash_root / stream_id
    if dash_dir.exists():
        shutil.rmtree(dash_dir, ignore_errors=True)

    hls_dir = _hls_root / stream_id
    if hls_dir.exists():
        shutil.rmtree(hls_dir, ignore_errors=True)

    _save_hls_streams(streams)
    return {"status": "deleted", "stream_id": stream_id}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=False)
