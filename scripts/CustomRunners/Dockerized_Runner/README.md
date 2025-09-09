
# Baseline Clarifai Runner (Dockerized)

A minimal Clarifai Local Runner implementation that echoes input, provides
endpoint introspection, and demonstrates how to package & deploy a Clarifai model in a
Docker container. This project is intended as a clean starting point for new models.

---

## ✨ Features

- Minimal dependency set (Clarifai SDK + Pydantic)
- Three example endpoints:
  - `predict` – echoes/parses prompt (JSON or plain text) and can list method metadata
  - `generate` – streams structured JSON chunks
  - `stream` – raw text streaming ("<input> Stream Hello World <i>") with optional batching (`batch_size`)
- Permissive prompt handling: raw strings, JSON objects, or other JSON values
- Built‑in method introspection (names, first doc line, parameters)
- Docker + docker‑compose for quick local deployment

---

## 📦 Project Structure

```
baseline_runner/
├── 1/
│   └── model.py            # Baseline model
├── Dockerfile              # Container image recipe
├── docker-compose.yml      # Local orchestration
├── requirements.txt        # Minimal Python deps
├── start_runner.sh         # Clarifai auth + runner startup
└── README.md               # This documentation

```

---

## 🚀 Quick Start

1. Copy `env.example` to `.env` and fill in ALL required variables:
```
CLARIFAI_PAT=your_pat_here
CLARIFAI_USER_ID=your_user_id
CLARIFAI_APP_ID=your_app_id
CLARIFAI_MODEL_ID=your_model_id
CLARIFAI_MODEL_TYPE_ID=text-to-text
CLARIFAI_DEPLOYMENT_ID=your_deployment_id
CLARIFAI_COMPUTE_CLUSTER_ID=your_compute_cluster_id
CLARIFAI_NODEPOOL_ID=your_nodepool_id
LOG_LEVEL=INFO
```
If any are missing, the startup script exits with an error.

2. Build & run:
```powershell
docker-compose up --build -d
```

3. View logs:
```powershell
docker logs clarifai-baseline-runner-docker
```

4. Use the model via Clarifai SDK (replace URL/deployment IDs per your workspace):
```python
from clarifai.client import Model

model = Model("https://clarifai.com/your-user/your-app/models/your-model", deployment_id="local-runner-deployment")

print(model.predict(prompt='{"message": "hello"}'))
for chunk in model.generate(prompt='{"message": "stream demo"}', steps=2):
    print(chunk)
```

---

## 🧪 Local Dev (without container)

```powershell
cd 1
python model.py
```

---

## 🧾 Prompt Handling Rules

| Input form                | Interpreted As                               |
|---------------------------|-----------------------------------------------|
| Empty / whitespace        | `{}`                                         |
| JSON object               | Parsed directly                              |
| JSON array / primitive    | `{ "value": <parsed> }`                     |
| Invalid JSON text         | `{ "message": "<original text>" }`        |

Examples:
```
hello world            -> {"message": "hello world"}
{"action":"list_methods"} -> same object
42                     -> {"value": 42}
```

---

## 🔍 Sample Outputs

Predict summary:
```json
{
  "endpoint": "predict",
  "status": "ok",
  "result": {"received_keys": ["message"], "message": "hello", "action": "echo"}
}
```

List methods (detail=full):
```json
{
  "endpoint": "predict",
  "status": "ok",
  "result": {"received_keys": ["action"], "action": "list_methods", "all_methods": {"predict": {"name": "predict", "doc_first_line": "Return basic information about provided prompt (JSON or raw string).", "parameters": {"prompt": "prompt: str = ''", "detail": "detail: str = Param(default='summary', description='summary or full', is_param=True)"}}}}
}
```

Generate stream:
```json
// Default (minimal=True)
{"endpoint":"generate","index":0,"text":"stream demo","final":false}
{"endpoint":"generate","index":1,"text":"stream demo","final":true}

// Verbose (minimal=False, include_methods=True, action=list_methods)
{"endpoint":"generate","status":"stream","index":0,"steps":2,"echo":"stream demo","methods":{...}}
{"endpoint":"generate","status":"complete","index":1,"steps":2,"echo":"stream demo","methods":null}
```

Generate parameters:
Raw text stream example (`stream`):
```text
alpha Stream Hello World 0
beta Stream Hello World 1
```
| Param | Default | Purpose |
|-------|---------|---------|
| prompt | "" | Raw string or JSON per rules above |
| steps | 3 | Number of chunks to emit |
| minimal | true | If true emit compact schema (endpoint,index,text,final) |
| include_methods | false | When minimal=False include method metadata in first chunk (or when action=list_methods) |
| (stream) batch_size | 1 | Number of inputs pulled from iterator before yielding them sequentially (each still yields separately) |

`stream` batching details:
- Inputs are collected up to `batch_size` then each is emitted with a monotonically increasing index.
- Output contract remains one line per original input (no aggregated JSON), preserving the simple example semantics.
- If `batch_size` < 1 it is coerced to 1.

---

## 🛠 Extending

1. Add or modify endpoints by decorating methods with `@ModelClass.method`.
2. Add your logic inside those methods (e.g., call external APIs, load models, etc.).
3. Keep dependencies minimal; update `requirements.txt` as needed.
4. Rebuild the container after changes: `docker-compose build`.

### Environment Variables (Strict)
The runner does NOT invent defaults. Provide everything in `.env`:

| Variable | Purpose |
|----------|---------|
| CLARIFAI_PAT | Auth token (personal access token) |
| CLARIFAI_USER_ID | Your Clarifai user/account id |
| CLARIFAI_APP_ID | App namespace for the model |
| CLARIFAI_MODEL_ID | Model identifier to bind to runner |
| CLARIFAI_MODEL_TYPE_ID | Model type (e.g. text-to-text) |
| CLARIFAI_DEPLOYMENT_ID | Deployment id mapping model version to compute |
| CLARIFAI_COMPUTE_CLUSTER_ID | Compute cluster id (created if absent) |
| CLARIFAI_NODEPOOL_ID | Nodepool id within the cluster |
| LOG_LEVEL | (Optional) Script logging verbosity |

---

## 🔐 Security Notes

- PAT is injected via `.env` (do not commit your real credentials).
- This baseline performs no network calls besides Clarifai runner operations unless you add them.
- Remove unused env vars if you fork from a template that included more (e.g., AWS_*).

---

## ❓ Troubleshooting

| Issue | Check |
|-------|-------|
| Container exits immediately | Is `CLARIFAI_PAT` set? Correct user ID? |
| SDK call fails | Verify model URL & deployment ID |
| Unexpected prompt output | Remember permissive wrapping rules above |

View logs:
```powershell
docker logs -f clarifai-baseline-runner-docker
```

---

## 📤 Sharing / Forking

- Replace the model namespace (user/app/model) in examples with your own.
- Update LICENSE if you need a different one (currently MIT).
- Add tests or CI as your project grows.

