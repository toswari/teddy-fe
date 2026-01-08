# API Examples

These HTTPie and curl snippets exercise the reference endpoints so agents can quickly verify their environment before coding.

> Assumes `./setup-env.sh`, `podman-compose up -d db`, and `./start.sh` are already running.

## List Projects

```bash
http :5000/api/projects
```

```bash
curl -s http://localhost:5000/api/projects | jq
```

## Create Project

```bash
http POST :5000/api/projects name="Brand Sweep" description="Initial sweep for logos"
```

```bash
curl -s -X POST http://localhost:5000/api/projects \
  -H 'Content-Type: application/json' \
  -d '{"name": "Brand Sweep", "description": "Initial sweep for logos"}' | jq
```

## Register Video

```bash
http POST :5000/api/projects/1/videos source_path="/data/videos/storefront.mp4"
```

```bash
curl -s -X POST http://localhost:5000/api/projects/1/videos \
  -H 'Content-Type: application/json' \
  -d '{"source_path": "/data/videos/storefront.mp4"}' | jq
```

## Preprocess Video Window

```bash
http POST :5000/api/projects/1/videos/1/preprocess start_seconds:=120 duration_seconds:=1800 clip_length:=30
```

```bash
curl -s -X POST http://localhost:5000/api/projects/1/videos/1/preprocess \
  -H 'Content-Type: application/json' \
  -d '{"start_seconds": 120, "duration_seconds": 1800, "clip_length": 30}' | jq
```

## Trigger Inference (single model)

```bash
http POST :5000/api/projects/1/videos/1/multi-inference model_ids:='["logo-detector"]'
```

Combine these commands into a shell script to speed up local smoke tests before handing work to another agent.
