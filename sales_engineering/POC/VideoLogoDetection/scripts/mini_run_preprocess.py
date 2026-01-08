"""Small runner to call preprocess endpoint for a video.

Usage: python scripts/mini_run_preprocess.py <project_id> <video_id>
"""
from __future__ import annotations

import sys
import requests


def main():
    if len(sys.argv) < 3:
        print("Usage: python scripts/mini_run_preprocess.py <project_id> <video_id>")
        return
    project_id = sys.argv[1]
    video_id = sys.argv[2]
    url = f"http://localhost:5000/api/projects/{project_id}/videos/{video_id}/preprocess"
    payload = {"clips": [{"start": 0.0, "end": 5.0}, {"start": 10.0, "end": 15.0}]}
    resp = requests.post(url, json=payload)
    print(resp.status_code)
    print(resp.text)


if __name__ == "__main__":
    main()
