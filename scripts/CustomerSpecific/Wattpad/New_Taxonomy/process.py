#!/usr/bin/env python3
"""
process.py - Simple one-shot processor for a list of image URLs using Clarifai mm-poly-8b model.

Usage examples:
  python process.py --input urls.csv --url-col "Image URL" --out results.json
  python process.py --input urls.txt --out results.json --prompt prompt.txt
  python process.py --input urls.csv --limit 50 --concurrency 4

"""
from __future__ import annotations
import argparse
import asyncio
import queue
import csv
import json
import io
import os
import sys
import time
import math
import traceback
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Iterable, Dict, Any

import requests
from PIL import Image

try:
    from clarifai.client.model import Model
    from clarifai.client.input import Inputs
except ImportError as e:
    print("Clarifai SDK not installed. Install with: pip install clarifai", file=sys.stderr)
    raise

DEFAULT_MODEL_NAME = "mm-poly-8b"

@dataclass
class ModelConfig:
    name: str
    url: str
    pat: str
    user_id: Optional[str]
    response_map: str
    reasoning_map: Optional[str]
    resize_to: Optional[int]
    needs_prompt: bool
    timeout: int

# ------------------------- Utility Functions ------------------------- #

def load_config(config_path: Path) -> ModelConfig:
    data = json.loads(config_path.read_text())
    # find mm-poly-8b
    model = next((m for m in data["models"] if m["name"] == DEFAULT_MODEL_NAME and m.get("enabled", True)), None)
    if not model:
        raise SystemExit(f"Model {DEFAULT_MODEL_NAME} not found or disabled in {config_path}")
    return ModelConfig(
        name=model['name'],
        url=model['url'],
        pat=model['pat'],
        user_id=model.get('user_id'),
        response_map=model['response_map'],
        reasoning_map=model.get('reasoning_map') or None,
        resize_to=model.get('resize_to'),
        needs_prompt=model.get('needs_prompt', False),
        timeout=int(model.get('timeout', 10))
    )

def load_prompt(prompt_arg: Optional[str], prompt_file: Optional[Path]) -> str:
    if prompt_arg:
        return prompt_arg
    if prompt_file and prompt_file.exists():
        return prompt_file.read_text(encoding='utf-8').strip()
    # fallback: look for prompt.txt next to script
    local = Path('prompt.txt')
    if local.exists():
        return local.read_text(encoding='utf-8').strip()
    return ""

def iter_urls(input_path: Path, url_col: str, limit: Optional[int]) -> Iterable[str]:
    if input_path.suffix.lower() in {'.txt', '.list'}:
        with input_path.open('r', encoding='utf-8', errors='ignore') as f:
            for i, line in enumerate(f):
                if limit and i >= limit: break
                url = line.strip()
                if url: yield url
        return
    # CSV
    with input_path.open('r', encoding='utf-8', errors='ignore') as f:
        reader = csv.DictReader(f)
        if url_col not in reader.fieldnames:
            raise SystemExit(f"URL column '{url_col}' not found. Fields: {reader.fieldnames}")
        for i, row in enumerate(reader):
            if limit and i >= limit: break
            url = (row.get(url_col) or '').strip()
            if url: yield url

# ------------------------- Image Handling ------------------------- #

def download_image(url: str, timeout: int = 10, retries: int = 2) -> bytes:
    last_error = None
    for attempt in range(retries+1):
        try:
            resp = requests.get(url, timeout=timeout)
            if resp.status_code != 200:
                raise RuntimeError(f"HTTP {resp.status_code}")
            content_type = resp.headers.get('content-type', '')
            if 'image' not in content_type:
                raise RuntimeError(f"Not an image content-type={content_type}")
            return resp.content
        except Exception as e:
            last_error = e
            if attempt < retries:
                time.sleep(2 ** attempt)
            else:
                raise last_error
    raise last_error  # never reached


def prepare_image(data: bytes, resize_to: Optional[int]) -> bytes:
    with Image.open(io.BytesIO(data)) as img:
        if img.mode != 'RGB':
            img = img.convert('RGB')
        if resize_to:
            # maintain aspect ratio
            ratio = min(resize_to / img.width, resize_to / img.height)
            if ratio < 1:
                new_size = (int(img.width * ratio), int(img.height * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=90)
        return buf.getvalue()

# ------------------------- Model Prediction ------------------------- #

def ensure_event_loop():
    """Ensure an asyncio event loop exists for libraries that implicitly expect it."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

def predict(model: Model, image_bytes: bytes, prompt: str, cfg: ModelConfig, debug: bool=False, raw_dump_cb=None) -> Dict[str, Any]:
    """Perform a prediction with retries and timeout using a per-call worker thread.

    We spawn a thread only to enforce a timeout while ensuring an asyncio event loop
    exists in that thread before calling Clarifai SDK (fixes previous event loop errors).
    """
    start = time.time()
    input_obj = (
        Inputs.get_multimodal_input(input_id="", image_bytes=image_bytes, raw_text=prompt)
        if cfg.needs_prompt else Inputs.get_input_from_bytes(input_id='', image_bytes=image_bytes)
    )
    inputs = [input_obj]

    for attempt in range(3):
        try:
            holder = {}
            def call():
                try:
                    ensure_event_loop()
                    holder['raw'] = model.predict(inputs=inputs)
                except Exception as e:
                    holder['err'] = e

            t = threading.Thread(target=call, daemon=True, name="predict-call")
            t.start()
            t.join(cfg.timeout)
            if t.is_alive():
                raise TimeoutError(f"Predict timeout after {cfg.timeout}s")
            if 'err' in holder:
                raise holder['err']
            raw = holder['raw']
            output = raw.outputs[0] if hasattr(raw, 'outputs') else raw[0]
            eval_ns = {'output': output, 'json': json, 'max': max, 'response': output}
            try:
                parsed = eval(cfg.response_map, eval_ns)
            except Exception as e:
                raise RuntimeError(f"response_map parse failed: {e}")
            reasoning = None
            if cfg.reasoning_map:
                try:
                    reasoning = eval(cfg.reasoning_map, eval_ns)
                except Exception:
                    reasoning = None
            
            # Extract text_found field from the JSON response
            text_found = None
            try:
                raw_text = output.data.text.raw
                if "```json" in raw_text:
                    json_part = raw_text.split("```json")[1].split("```")[0]
                    json_data = json.loads(json_part)
                    if isinstance(json_data, list) and len(json_data) > 0:
                        text_found = json_data[0].get("text_found", "")
            except Exception:
                text_found = None
            
            latency = round(time.time() - start, 2)
            if debug and raw_dump_cb:
                try:
                    raw_dump_cb({'raw': getattr(output.data, 'text', getattr(output, 'data', None)).raw if hasattr(getattr(output, 'data', None), 'text') else str(output)[:2000]})
                except Exception:
                    pass
            return {'result': parsed, 'reasoning': reasoning, 'text_found': text_found, 'latency_s': latency, 'error': None}
        except Exception as e:
            if attempt == 2:
                return {'result': None, 'reasoning': None, 'text_found': None, 'latency_s': round(time.time() - start, 2), 'error': f"{type(e).__name__}: {e}"[:600]}
            time.sleep(2 ** attempt)

# ------------------------- Processing Loop ------------------------- #

def process_urls(urls: Iterable[str], cfg: ModelConfig, prompt: str, concurrency: int, limit: Optional[int], progress: bool, debug: bool, raw_debug_dir: Optional[Path]) -> List[Dict[str, Any]]:
    from queue import Queue
    from tqdm import tqdm

    urls_list = list(urls)  # materialize for progress + concurrency
    if limit:
        urls_list = urls_list[:limit]

    q = Queue()
    for idx, u in enumerate(urls_list):
        q.put((idx, u))

    lock = threading.Lock()
    results: List[Optional[Dict[str, Any]]] = [None] * len(urls_list)

    model = Model(url=cfg.url, pat=cfg.pat, user_id=cfg.user_id)

    dump_lock = threading.Lock()
    if debug and raw_debug_dir:
        raw_debug_dir.mkdir(parents=True, exist_ok=True)
    def raw_dump_cb(obj: Dict[str, Any]):
        if not (debug and raw_debug_dir):
            return
        with dump_lock:
            idx = len(list(raw_debug_dir.glob('raw_*.json')))
            (raw_debug_dir / f"raw_{idx:04d}.json").write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')

    pbar = tqdm(total=len(urls_list), disable=not progress, desc="Images")

    def worker():
        while True:
            try:
                idx, url = q.get_nowait()
            except Exception:
                break
            started = time.time()
            out: Dict[str, Any]
            try:
                img_bytes = download_image(url)
                prepped = prepare_image(img_bytes, cfg.resize_to)
                out = predict(model, prepped, prompt, cfg, debug=debug, raw_dump_cb=raw_dump_cb)
            except Exception as e:
                out = {
                    'result': None,
                    'reasoning': None,
                    'text_found': None,
                    'latency_s': round(time.time() - started, 2),
                    'error': f"{type(e).__name__}: {e}"[:400]
                }
            out_record = {
                'index': idx,
                'url': url,
                'model': cfg.name,
                **out
            }
            with lock:
                results[idx] = out_record
                pbar.update(1)
            q.task_done()

    threads = [threading.Thread(target=worker, daemon=True, name=f"worker-{i}") for i in range(concurrency)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    pbar.close()

    # fill any None (should not happen) with error stubs
    final: List[Dict[str, Any]] = []
    for i, r in enumerate(results):
        if r is None:
            final.append({'index': i, 'url': urls_list[i], 'model': cfg.name, 'result': None, 'reasoning': None, 'text_found': None, 'latency_s': 0, 'error': 'InternalError: missing result'})
        else:
            final.append(r)
    return final

# ------------------------- Output Writing ------------------------- #

def write_output(data: List[Dict[str, Any]], output_path: Path, json_array: bool):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if json_array:
        output_path.write_text(json.dumps(data, indent=2), encoding='utf-8')
    else:
        with output_path.open('w', encoding='utf-8') as f:
            for row in data:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"Wrote {len(data)} records to {output_path}")

def write_csv(data: List[Dict[str, Any]], csv_path: Path, original_rows: Optional[List[Dict[str, Any]]]):
    import csv as _csv
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    # Base fields from original if available
    base_fields = []
    if original_rows:
        # Use union of original keys (excluding blanks)
        keys = set()
        for r in original_rows:
            keys.update(k for k in r.keys() if r.get(k) not in (None, ""))
        base_fields = [k for k in original_rows[0].keys() if k in keys]
    # Prediction fields
    pred_fields = [
        'result', 'reasoning', 'text_found', 'latency_s', 'error'
    ]
    extra_fields = ['index','url','model']
    fieldnames = extra_fields + base_fields + pred_fields
    seen = set()
    ordered = []
    for f in fieldnames:
        if f not in seen:
            ordered.append(f); seen.add(f)
    with csv_path.open('w', newline='', encoding='utf-8') as f:
        writer = _csv.DictWriter(f, fieldnames=ordered)
        writer.writeheader()
        for row in data:
            out = {k: row.get(k, '') for k in ordered}
            # Merge original row if matching by URL or index
            if original_rows:
                # try by index
                idx = row.get('index')
                if isinstance(idx, int) and idx < len(original_rows):
                    for k,v in original_rows[idx].items():
                        if k not in out or out[k] == '':
                            out[k] = v
            writer.writerow(out)
    print(f"Wrote CSV: {csv_path}")

# ------------------------- CLI ------------------------- #

def parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Process image URLs with mm-poly-8b Clarifai model")
    p.add_argument('--input', '-i', required=True, help='Input CSV or text file of URLs')
    p.add_argument('--url-col', default='Image URL', help='Column name containing URLs (CSV only)')
    p.add_argument('--out', '-o', default='results.jsonl', help='Output file path (.jsonl or .json)')
    p.add_argument('--json-array', action='store_true', help='Write a single JSON array instead of JSONL')
    p.add_argument('--csv-out', type=Path, help='Optional CSV output path (in addition to JSON)')
    p.add_argument('--prompt', help='Inline prompt text override')
    p.add_argument('--prompt-file', type=Path, help='Path to prompt file')
    p.add_argument('--config', type=Path, default=Path('config.json'), help='Path to config.json')
    p.add_argument('--concurrency', '-c', type=int, default=4, help='Number of download/predict worker threads')
    p.add_argument('--limit', type=int, help='Limit number of URLs processed')
    p.add_argument('--progress/--no-progress', dest='progress', default=True, action=argparse.BooleanOptionalAction, help='Show progress bar')
    p.add_argument('--debug', action='store_true', help='Enable debug mode (store raw model outputs)')
    p.add_argument('--debug-raw-dir', type=Path, default=Path('debug_raw'), help='Directory to dump raw outputs when --debug is set')
    return p.parse_args(argv)

# ------------------------- Main Entry ------------------------- #

def summarize(results: List[Dict[str, Any]]):
    total = len(results)
    errors = sum(1 for r in results if r['error'])
    avg_latency = round(sum(r['latency_s'] for r in results) / total, 2) if total else 0
    print("\nSummary:")
    print(f"  Total: {total}")
    print(f"  Errors: {errors} ({(errors/total*100):.1f}%)" if total else "  Errors: 0")
    print(f"  Avg latency: {avg_latency}s")


def main(argv: List[str] | None = None):
    args = parse_args(argv or sys.argv[1:])
    cfg = load_config(args.config)
    prompt = load_prompt(args.prompt, args.prompt_file)
    input_path = Path(args.input)
    # Load original rows if CSV so we can merge into CSV output
    original_rows: Optional[List[Dict[str, Any]]] = None
    if input_path.suffix.lower() not in {'.txt', '.list'}:
        with input_path.open('r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)
            original_rows = []
            for i,row in enumerate(reader):
                if args.limit and i >= args.limit: break
                # Only include rows with non-empty URLs to match iter_urls behavior
                url = (row.get(args.url_col) or '').strip()
                if url:
                    original_rows.append(row)
    urls = iter_urls(input_path, args.url_col, args.limit)
    results = process_urls(urls, cfg, prompt, args.concurrency, args.limit, args.progress, args.debug, args.debug_raw_dir if args.debug else None)
    out_path = Path(args.out)
    write_output(results, out_path, args.json_array or out_path.suffix == '.json')
    if args.csv_out:
        write_csv(results, args.csv_out, original_rows)
    summarize(results)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
    except Exception as e:
        print("Fatal error:")
        traceback.print_exc()
        sys.exit(1)
