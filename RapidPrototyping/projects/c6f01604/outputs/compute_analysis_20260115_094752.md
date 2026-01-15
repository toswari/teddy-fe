# Clarifai Compute Orchestration Analysis

**Customer:** Hirtz and Carter
**Date:** January 15, 2026

---


## Executive Summary

This analysis provides GPU reservation recommendations for Hirtz and Carter. 
Clarifai Compute Orchestration handles all infrastructure - you simply reserve the capacity you need.

**Full Documentation:** https://docs.clarifai.com/

## Your Requirements

{
  "gpu_type": "",
  "gpu_count": "",
  "commitment": ""
}

**Project Goals:** Create Image analysis system that can detect image problem (image QA) 

---

## Trending Open-Source Models (From Hugging Face)

Based on your project goals, here are recommended open-source models available on Clarifai:


### Recommended Primary Models (Based on Your Use Case)

| Model | Parameters | License | GPU Requirement | Link |
|-------|------------|---------|-----------------|------|
| **mm-poly-8b** *(Clarifai)* | 8B | clarifai | Standard (24GB) | [mm-poly-8b](https://clarifai.com/clarifai/mm-poly/models/mm-poly-8b) ⭐ |
| llava-1.5-7b-hf | 7B | llama2 | Standard (24GB) | [llava-1.5-7b-hf](https://huggingface.co/llava-hf/llava-1.5-7b-hf) |
| Llama-3.2-11B-Vision-Instruct | 11B | llama3.2 | Standard (24GB) or Performance (48GB) | [Llama-3.2-11B-Vision-Instruct](https://huggingface.co/meta-llama/Llama-3.2-11B-Vision-Instruct) |

*⭐ = Recommended Clarifai model, ready to use. Check all models at [clarifai.com/explore](https://clarifai.com/explore)*

### Embedding Models (For RAG/Search)

| Model | Parameters | License | GPU Requirement | Link |
|-------|------------|---------|-----------------|------|
| all-MiniLM-L6-v2 | 22M | apache-2.0 | Entry (16GB) or CPU | [all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) |
| bge-large-en-v1.5 | 335M | mit | Entry (16GB) | [bge-large-en-v1.5](https://huggingface.co/BAAI/bge-large-en-v1.5) |

*⭐ = Recommended Clarifai model, ready to use. Check all models at [clarifai.com/explore](https://clarifai.com/explore)*

### Alternative Model Options

| Model | Parameters | License | GPU Requirement | Link |
|-------|------------|---------|-----------------|------|
| llava-v1.6-mistral-7b-hf | 7B | apache-2.0 | Standard (24GB) | [llava-v1.6-mistral-7b-hf](https://huggingface.co/llava-hf/llava-v1.6-mistral-7b-hf) |
| Qwen2-VL-7B-Instruct | 7B | apache-2.0 | Standard (24GB) | [Qwen2-VL-7B-Instruct](https://huggingface.co/Qwen/Qwen2-VL-7B-Instruct) |
| Phi-3-vision-128k-instruct | 4.2B | mit | Entry (16GB) | [Phi-3-vision-128k-instruct](https://huggingface.co/microsoft/Phi-3-vision-128k-instruct) |

*⭐ = Recommended Clarifai model, ready to use. Check all models at [clarifai.com/explore](https://clarifai.com/explore)*

### GPU Requirements Summary

Based on the recommended models:

- **Standard (24GB)**: mm-poly-8b, llava-1.5-7b-hf, llava-v1.6-mistral-7b-hf, Qwen2-VL-7B-Instruct
- **Standard (24GB) or Performance (48GB)**: Llama-3.2-11B-Vision-Instruct
- **Entry (16GB) or CPU**: all-MiniLM-L6-v2
- **Entry (16GB)**: bge-large-en-v1.5, Phi-3-vision-128k-instruct

## Clarifai Platform Capabilities

| Capability | Use For | Documentation |
|------------|---------|---------------|
| **Model Library** | Pre-built VLMs, LLMs, CV models | [clarifai.com/explore](https://clarifai.com/explore) |
| **Workflows** | Multi-model pipelines | [docs.clarifai.com/create/workflows](https://docs.clarifai.com/create/workflows/) |
| **AI Agents** | Autonomous multi-step tasks | [docs.clarifai.com/compute/agents](https://docs.clarifai.com/compute/agents/) |
| **Vector Search** | RAG, semantic search | [docs.clarifai.com/create/search](https://docs.clarifai.com/create/search/) |
| **Pipelines** | Async MLOps workflows | [docs.clarifai.com/compute/pipelines](https://docs.clarifai.com/compute/pipelines/) |

## Recommended Approach

### 1. Start with Model Evaluation

Before reserving GPUs, evaluate Vision-Language Models (VLMs) against your data:
- Start with Clarifai's mm-poly-8b for vision tasks
- Test 2-3 alternative models for comparison
- Measure accuracy on your specific use cases

### Model Size → GPU Selection

Choose your GPU tier based on the model size you need:

| Model Size | VRAM (FP16) | VRAM (INT8) | Recommended GPU | Examples |
|------------|-------------|-------------|-----------------|----------|
| 1-3B | 6-8 GB | 3-4 GB | T4 16GB | Small VLMs, embedders |
| 7-8B | 14-16 GB | 7-8 GB | T4/L4 16-24GB | Llama 3.1 8B, Mistral 7B |
| 13-14B | 26-28 GB | 13-14 GB | L4/L40S 24-48GB | Llama 2 13B |
| 30-34B | 60-70 GB | 30-35 GB | L40S/A100 48-80GB | CodeLlama 34B |
| 70B | 140 GB | 70 GB | A100 80GB or Multi-GPU | Llama 3.1 70B |
| 100B+ | 200+ GB | 100+ GB | Multi-GPU (2-8x H100) | Large models |

**Tip:** Use INT8 quantization to reduce VRAM ~50% with minimal quality loss.

### 2. Integrate via Clarifai API

Use Clarifai's managed API - no custom infrastructure needed:

```python
from clarifai.client import Model

model = Model(url="https://clarifai.com/user/app/models/model-id")
response = model.predict(inputs=[your_data])
```

**Documentation:** https://docs.clarifai.com/compute/inference/

**SDK Options:**
- Python: `pip install clarifai` (recommended)
- Node.js: `npm install clarifai`
- OpenAI-compatible: `https://api.clarifai.com/v2/ext/openai/v1`
- LiteLLM, Vercel AI SDK also supported

### 3. Reserve GPU Capacity

Based on your workload, reserve appropriate capacity:

| Phase | GPUs | Tier | Monthly Cost |
|-------|------|------|--------------|
| Pilot (Months 1-3) | 1-2 | Standard (24GB) | ~$1,469 |
| Production (Months 4-6) | 2-3 | Standard/Performance | ~$3,396 |
| Scale (Months 7-12) | 3-4+ | Performance (48GB) | ~$6,793 |

**Estimated Year 1 Investment:** ~$55,351

## GPU Tier Reference

| Tier | VRAM | Annual Cost | Best For |
|------|------|-------------|----------|
| Entry | 16GB | ~$5,000-6,000 | Development, testing |
| Standard | 24GB | ~$8,000-13,000 | Production inference |
| Performance | 48GB | ~$18,000-25,000 | LLM inference, high throughput |
| Enterprise | 80GB+ | ~$21,000-65,000 | Large models, enterprise scale |

## Compute Orchestration Benefits

([Full details](https://docs.clarifai.com/compute/overview))

- **Auto-scaling**: Scale from zero to infinity based on demand
- **GPU Fractioning**: Run multiple models per GPU
- **Model Packing**: Up to 3.7x compute efficiency
- **Cost Savings**: 60-90% savings vs. raw cloud GPUs

## What Clarifai Handles

- ✅ GPU provisioning and management
- ✅ Infrastructure scaling (auto-scale to zero)
- ✅ Model hosting and serving
- ✅ API availability and uptime
- ✅ Security and compliance
- ✅ Updates and maintenance

## What You Do

- ✅ Select models from Clarifai's library
- ✅ Integrate SDK/API into your application
- ✅ Reserve GPU capacity based on needs
- ✅ Monitor usage and adjust as needed

## Next Steps

1. **Model Evaluation** - Test VLMs on your data (start with mm-poly-8b)
2. **Integration** - Use Clarifai SDK (Python, Node.js, or REST)
3. **GPU Reservation** - Reserve capacity based on evaluation results
4. **Go Live** - Deploy and scale as needed

**Resources:**
| Resource | Link |
|----------|------|
| API Docs | https://docs.clarifai.com/ |
| Model Library | https://clarifai.com/explore |
| Inference | https://docs.clarifai.com/compute/inference/ |
| Workflows | https://docs.clarifai.com/create/workflows/ |
| Compute Orchestration | https://docs.clarifai.com/compute/overview |


---

## Technical Architecture Recommendation

# Hirtz & Carter – Automated Image‑QA Solution  
**Industry:** Retail (e‑commerce)  
**Date:** 15 Jan 2026  

---  

## 1. Architecture Overview  

| **Goal** | Detect image‑quality problems (background, colour, retouching, compliance) automatically, return a **structured JSON verdict with a human‑readable explanation**, and feed the result back to the existing DAM / CMS. |
|----------|----------------------------------------------------------------------------------------------------------------------------------------------------|
| **Core Principle** | **Vision‑Language Model (VLM)** for high‑level reasoning **+** lightweight detection models only when visual localisation is required. |
| **Compute Model** | Clarifai **Compute Orchestration** – managed GPU pool, auto‑scaling, reservation option for predictable spend. |
| **Key Benefits** | • Explainable decisions (text only – VLM limitation)  <br>• No custom infra – everything runs on Clarifai SaaS  <br>• Scalable from 10 k to > 1 M images / month  <br>• Cost‑optimised by reserving a modest GPU fleet. |

### 1.1 High‑Level Diagram  

```mermaid
graph TD
    A[Source DAM / S3 / CMS] --> B[Ingestion Service (Clarifai SDK / webhook)]
    B --> C[Pre‑process (Resize, Validate, Metadata enrichment)]
    C --> D[Stage‑1: VLM (mm‑poly‑8b)]
    D --> E{VLM flags “needs visual localisation”?}
    E -- Yes --> F[Stage‑2: Detection Models]
    E -- No  --> G[Aggregate JSON Verdict]
    F --> G
    G --> H[Post‑process (format, confidence thresholds)]
    H --> I[Webhook / REST API to DAM / CMS]
    H --> J[Dashboard / Reporting (Grafana/Clarifai Insights)]
```

*All arrows represent asynchronous Clarifai workflow steps; each step can run in parallel on a shared GPU pool.*

---  

## 2. Data Flow  

| **Stage** | **Description** | **Formats / Tools** |
|-----------|----------------|---------------------|
| **Ingestion** | Pull new images from the customer’s DAM (REST API), S3 bucket, or direct upload via Clarifai SDK. | JPEG/PNG/TIFF/PSD (max 5 MB after pre‑resize). |
| **Pre‑processing** | • Convert to RGB  <br>• Resize to ≤ 1024 px (preserves VLM quality)  <br>• Validate file integrity, colour profile (RGB). | Clarifai **pre‑process operator** (built‑in). |
| **Stage‑1 VLM** | Single‑pass multimodal inference that reads the image *and* the textual QA checklist (prompt). Returns: <br>‑ `overall_status` (PASS/FAIL) <br>‑ `defect_list` (array of issue codes) <br>‑ `explanation` (natural‑language rationale). | Model: **mm‑poly‑8b** (frontier VLM). |
| **Conditional Stage‑2** | If VLM returns a “needs localisation” flag (e.g., *shadow detected*), invoke: <br>‑ **Background‑Detector** (object detector) – returns bounding box & confidence for background‑colour deviation, shadows, stray objects. <br>‑ **Colour‑Accuracy‑Classifier** – verifies colour match against reference swatches. | Models: `clarifai-retail-bg-detector` (YOLO‑style) + `clarifai-color-accuracy-cls`. |
| **Aggregation** | Merge VLM text verdict with any detection outputs into a single JSON payload. | Custom **workflow operator** (simple Python script). |
| **Delivery** | POST JSON to the customer’s webhook endpoint; also write to a **Clarifai dataset** for audit and future retraining. | REST webhook, optional Kafka / SQS for downstream pipelines. |
| **Reporting** | Real‑time dashboards (through Clarifai Insights) show pass‑rate, defect categories, latency, and cost. | Grafana‑compatible metrics, exported to CSV/Excel on demand. |

---  

## 3. Clarifai Components  

| **Component** | **Why Chosen** | **Configuration** |
|----------------|----------------|-------------------|
| **mm‑poly‑8b** (Frontier Multimodal) | - Handles complex visual reasoning (e.g., “Is lighting natural?”). <br>- Returns **textual explanations** (VLM output limitation). <br>- No need for model fine‑tuning for the first 90 % of checklist items. | - Prompt template includes the full QA checklist (≈ 200 tokens). <br>- Batch size = 4–8 per GPU for throughput. |
| **clarifai‑retail‑bg‑detector** (Object Detection) | - Provides bounding‑box evidence for background‑colour, shadows, stray objects – the only visual localisation the VLM cannot output. | - Confidence threshold = 0.65. <br>- Runs only when VLM flags `needs_localisation = true`. |
| **clarifai‑color‑accuracy‑cls** (Classification) | - Quick, low‑latency check that colour matches brand swatches (important for colour‑accuracy checklist). | - Uses embedded reference colour vectors stored in a Clarifai dataset. |
| **Workflow** (`image_qa_pipeline`) | Orchestrates the three steps, handles branching, retries, dead‑letter routing. | - Sequential: Pre‑process → VLM → Conditional detection → Aggregation → Webhook. |
| **Dataset “image_qa_ground_truth”** | Stores every image + VLM verdict + detection results for audit and future fine‑tuning. | - Auto‑append via workflow operator. |
| **Agents (optional)** | If future “suggest corrective action” is required, an **MCP agent** can be added to call image‑editing tools. | Not in MVP. |

**Custom Training?** – Not required for MVP. If after evaluation the VLM misses > 5 % of critical defects, a **fine‑tune** on the 5 k labelled images can be performed (Clarifai Custom Model service) – budgeted for Phase 2.

---  

## 4. Integration Design  

| **Aspect** | **Details** |
|------------|--------------|
| **Incoming API** | `POST /v2/users/{user_id}/apps/{app_id}/inputs` (Clarifai SDK) – bulk upload of image URLs or base64. |
| **Outgoing API** | Customer‑provided webhook: `POST https://<customer>/image-qa-callback` with JSON payload:<br>`{ "image_id": "...", "status": "PASS", "defects": [...], "explanation": "...", "detections": [{ "type":"shadow", "bbox":[x1,y1,x2,y2], "confidence":0.78 }] }` |
| **Authentication** | Clarifai **Personal Access Token (PAT)** for inbound calls. <br>Customer webhook uses **HMAC‑SHA256 signature** (shared secret) – verified by the customer’s server. |
| **Error Handling** | - **Retry policy**: 3× exponential back‑off for webhook failures. <br>- **Dead‑letter queue** (Clarifai “failed‑events” dataset) for manual review. <br>- **Workflow fallback**: if VLM returns an error, automatically route to a *fallback* simple classifier (`zero‑shot‑image‑classifier`) to give a minimal PASS/FAIL. |
| **SDK Samples** | Python example for bulk upload & webhook registration (provided in the Implementation Guide). |
| **Versioning** | Model version stored in workflow metadata; change logs kept in a `model_registry` dataset. |

---  

## 5. Infrastructure  

### 5.1 Compute Requirements  

| **Metric** | **Assumption** | **Result** |
|------------|----------------|------------|
| **Peak image rate** | 300 imgs / min (= 5 imgs / s) |
| **VLM latency** | 1.2 s per image on a **Standard‑tier** GPU (NVIDIA A10, FP16) |
| **GPU‑seconds per image** | 1.2 GPU‑s |
| **Total GPU‑seconds per second** | 5 imgs × 1.2 = 6 GPU‑s |
| **GPUs needed (continuous)** | 6 GPU‑seconds / 1 GPU‑second ≈ 6 GPUs (Standard tier) |
| **Detection models** | Run only on ~30 % of images, each ≈ 0.4 s, negligible extra capacity. |
| **Utilisation pattern** | • Steady‑state 5 imgs/s → 6 GPUs fully utilised. <br>• Off‑peak (night) < 1 img/s → utilisation drops to < 15 %. |
| **GPU type** | **Standard tier** (24 GB VRAM, A10) – sufficient for **mm‑poly‑8b** (requires ~14 GB FP16 + 20 % KV cache). |
| **Reservation vs On‑Demand** | • On‑Demand price (approx.) = $0.008 / GPU‑sec → 6 GPUs × 86400 s × 30 days ≈ $124,416 / month. <br>• 12‑month **reserved capacity** (30 % discount) ≈ $87,091 / month → **$1.05 M / year**. <br>• If peak usage only 30 % of the month, a **mixed model** (reserve 3 GPUs, burst up to 6 on‑demand) reduces annual spend to **≈ $720 k**. |
| **ROI Calculation** | - **Manual QA cost**: 2 FTE × $80 k / yr ≈ $160 k (250 imgs/FTE‑day). <br>- **Re‑work cost saved**: 30 % reduction on $22 k / mo ≈ $79 k / yr. <br>- **Total annual benefit** ≈ $239 k. <br>- **Net cost** (mixed reservation) ≈ $720 k → **Payback ≈ 3.0 yr**. <br>- If throughput can be reduced to 2 imgs/s (e.g., batch‑only at night) the required GPUs drop to 2‑3, cutting cost to **≈ $350 k / yr**, **payback < 2 yr**. |
| **Recommendation** | Start with a **mixed reservation**: **3 Standard‑tier GPUs reserved** (covers average load) + **burst pool of up to 6 GPUs on‑demand** for peak spikes. This gives a **~40 % cost saving** vs pure on‑demand while guaranteeing SLA. |

### 5.2 Deployment Topology  

```
+-------------------+      +--------------------+      +----------------------+
|   Customer DAM / | ---> |   Clarifai Ingest   | ---> |  Clarifai GPU Pool   |
|   S3 / CMS       |      |   (SDK / webhook)   |      | (Standard‑tier)      |
+-------------------+      +--------------------+      +----------+-----------+
                                                          |
                                                          v
                                                +-------------------+
                                                |  Workflow Engine  |
                                                +-------------------+
                                                          |
                +-------------------+---------------------+-------------------+
                |                   |                     |                   |
                v                   v                     v                   v
          VLM (mm‑poly‑8b)   Detection (bg‑det)   Detection (colour)   Aggregator
                |                   |                     |                   |
                +-------------------+---------------------+-------------------+
                                                          |
                                                          v
                                                +-------------------+
                                                |   Webhook / API   |
                                                +-------------------+
```

*All services are fully managed by Clarifai (SaaS). No customer‑owned servers needed.*

### 5.3 High‑Availability  

* **GPU pool** – Clarifai automatically spreads workloads across the reserved GPU nodes; if a node fails, the scheduler re‑routes jobs to the burst pool.  
* **Workflow retries** – built‑in exponential back‑off (max 5 attempts).  
* **Data durability** – Input images stored in Clarifai’s immutable “input” store; results persisted in a dedicated dataset with 7‑day versioning.  

---  

## 6. Security  

| **Area** | **Controls** |
|----------|--------------|
| **Data in transit** | TLS 1.2+ for all API calls (both inbound to Clarifai and outbound webhook). |
| **Data at rest** | Images stored encrypted (AES‑256) in Clarifai’s object store; customer can enable **customer‑managed keys (CMK)** if required. |
| **Authentication** | PAT for Clarifai SDK; HMAC‑SHA256 signature for outbound webhook. |
| **Authorization** | Role‑Based Access Control (RBAC) within Clarifai app – only QA engineers can view raw images; analysts can view only JSON verdicts. |
| **Compliance** | GDPR‑compliant data handling; can be deployed in **EU‑region** VPC if needed. |
| **Audit** | All inference calls logged with user, timestamp, model version; exportable audit logs for compliance teams. |

---  

## 7. Monitoring & Observability  

| **Metric** | **Source** | **Target / Alert** |
|------------|------------|--------------------|
| **Requests / sec** | Workflow engine | > 5 req/s → scale‑up alert. |
| **Average latency** (VLM) | GPU utilization logs | > 2 s → investigate GPU saturation. |
| **GPU utilization %** | Clarifai Compute Dashboard | > 85 % → auto‑scale burst pool. |
| **Error rate** (inference failures) | Workflow dead‑letter queue | > 0.5 % → raise ticket. |
| **Pass‑rate** (overall_status) | Dataset “image_qa_ground_truth” | Sudden drop > 10 % → QA rule drift alert. |
| **Cost per 1 k images** | Billing API | > $12 → cost‑optimisation review. |
| **Webhook delivery success** | Outbound webhook logs | < 99 % success → retry escalation. |

*All metrics are visualised in a Grafana dashboard (Clarifai Insights integration). Alerts are routed to Slack, PagerDuty, or email per the customer’s preference.*

---  

## 8. Implementation Phases  

| **Phase** | **Duration** | **Key Deliverables** | **Dependencies** |
|-----------|--------------|----------------------|------------------|
| **0 – Kick‑off & Requirements** | 1 wk | Signed requirements doc, access to DAM, webhook URL, reference QA checklist. | Customer provides PAT, webhook secret. |
| **1 – Data Prep & Ground‑Truth Set** | 2 wks | 5 k labelled images (PASS/FAIL + defect tags) stored in `image_qa_ground_truth`. | Access to historical QA logs. |
| **2 – Model Evaluation** | 3 wks | Benchmark report for `mm‑poly‑8b` vs 2 alternatives (e.g., `LLaVA‑1.5‑8b`, `open‑clip‑v2`). Decision matrix. | Compute budget for evaluation (on‑demand). |
| **3 – Workflow Build (MVP)** | 2 wks | Working Clarifai workflow (`image_qa_pipeline`) in **staging**; webhook test harness. | Model versions selected. |
| **4 – Integration & UI** | 2 wks | SDK wrapper for bulk upload, webhook consumer, simple React dashboard (optional). | Customer’s CMS/DAM API. |
| **5 – Performance Tuning & Scaling** | 1 wk | GPU count finalised, reservation plan signed, auto‑scale thresholds set. | Billing approval. |
| **6 – UAT & Sign‑off** | 1 wk | End‑to‑end test with 10 k live images, accuracy ≥ 90 % on critical defects, latency ≤ 2 s. | QA team validation. |
| **7 – Production Roll‑out** | 1 wk | Reserved GPUs provisioned, workflow switched to prod, monitoring enabled. | Change‑management approval. |
| **8 – Phase‑2 Enhancements** (optional) | 4 wks | Fine‑tune VLM on H&C data, add “suggest corrective action” agent, integrate with ticketing system. | Positive MVP metrics. |

### Risk Mitigation  

| **Risk** | **Mitigation** |
|----------|----------------|
| **VLM latency exceeds SLA** | Batch inference, reserve extra GPU headroom, fallback to lightweight classifier for non‑critical images. |
| **Insufficient labelled data** | Use synthetic augmentation (lighting, background swaps) + active‑learning loop (human‑in‑the‑loop for low‑confidence cases). |
| **Data‑privacy restrictions** | Deploy Clarifai **private VPC** in the EU region; enable CMK encryption. |
| **Model drift** | Monthly re‑evaluation against ground‑truth set; automated retraining pipeline (Phase‑2). |
| **Budget overruns** | Start with mixed reservation (3 GPUs reserved) and monitor; adjust reservation up/down quarterly. |

---  

## 9. Summary & Recommendations  

| **What** | **Why** | **Action** |
|----------|----------|------------
