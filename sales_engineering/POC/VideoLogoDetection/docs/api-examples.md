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
http POST :5000/api/videos project_id==1 source_path="/data/videos/storefront.mp4"
```

## Trigger Inference (single model)

```bash
http POST :5000/api/videos/1/inference model_ids:='["logo-detector"]'
```

Combine these commands into a shell script to speed up local smoke tests before handing work to another agent.
