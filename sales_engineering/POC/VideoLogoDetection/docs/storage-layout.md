# Media Storage Layout

The reference implementation stores video artifacts on the host filesystem so developers can inspect intermediate outputs without opening the DB.

```
media/
  project_<project_id>/
    video_<video_id>/
      original/              # original uploads or symlinks
      clips/                 # 20-second segments generated via FFmpeg
        clip_001.mp4
        clip_002.mp4
      frames/                # sampled frames (optional, future phase)
        frame_001.jpg
      reports/               # docx exports tied to this video/project
```

- `PROJECT_MEDIA_ROOT` config (default `media`) controls the root directory.
- Clip and frame names should remain deterministic (`clip_{index:03d}.mp4`, `frame_{second:03d}.jpg`) so agents can cross-reference logs.
- When testing without actual FFmpeg work, stub functions should still create empty files so the UI can render realistic paths.
