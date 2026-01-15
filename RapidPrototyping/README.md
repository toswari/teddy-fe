# Clarifai Rapid Prototyping Framework

An AI-powered framework for Solution Engineers to rapidly generate project proposals, technical guides, and deliverables for Clarifai customers.

## 🎯 Purpose

This framework acts as an intelligent assistant for Clarifai Solution Engineers in pre/post-sales roles, helping to:

- Analyze customer requirements and documentation
- Generate comprehensive project proposals
- Create technical implementation guides (SE Guides)
- Identify key discovery questions and clarifications needed
- Generate compute analysis and ROI calculations
- Recommend appropriate models (VLMs over legacy CV)
- Process multimodal inputs (documents, images, PDFs, DOCX)

## 🚀 Quick Start

### Using Docker Compose (Recommended)

```bash
# Set your Clarifai API key
export CLARIFAI_API_KEY=your_api_key

# Build and run
docker-compose up -d --build

# Access the web interface
open http://localhost:8080
```

### Local Development

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
.\venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export CLARIFAI_API_KEY=your_api_key

# Run the application
cd src/web && uvicorn app:app --reload --port 8080
```

## 🖥️ Web Interface

The web UI is built with **Alpine.js** and **Tailwind CSS**, providing a modern single-page application experience.

### Main Features

| Tab | Description |
|-----|-------------|
| **Projects** | View and manage all customer projects |
| **New Project** | Create a new project with customer details |
| **Discovery Questions** | Browse industry-specific discovery questions |
| **GPU Pricing** | Interactive GPU pricing table with filtering |

### 6-Step Project Workflow

The project modal guides users through a structured workflow:

| Step | Name | Description |
|------|------|-------------|
| 1 | **Upload Documents** | Upload RFPs, requirements, meeting notes (PDF, DOCX, MD, TXT) |
| 2 | **Generate Questions** | AI generates tailored discovery questions based on materials |
| 3 | **Upload Answers** | Upload notes from customer discovery call |
| 4 | **Generate Proposal** | AI creates comprehensive project proposal |
| 5 | **Upload Feedback** | (Optional) Upload customer feedback for revisions |
| 6 | **Generate Final Docs** | Generate Compute Analysis, ROI, and SE Implementation Guide |

**Progress Persistence:** Users can leave at any time and resume where they left off. The system automatically determines the appropriate step based on project state.

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `?` | Toggle help overlay |
| `ESC` | Close modals |

## 📄 Document Generation

### Discovery Questions
Generates industry-specific discovery questions to gather customer requirements. Questions are categorized by:
- Business requirements
- Technical requirements
- Compute/infrastructure needs
- Budget/timeline
- Integration requirements

### Project Proposal
Comprehensive proposal document including:
- Executive summary
- Solution architecture
- Model recommendations (VLMs prioritized)
- Implementation phases
- Timeline and milestones
- Risk assessment

### Compute Analysis & ROI
Detailed analysis including:
- GPU recommendations by workload type
- Cost comparison across regions
- Annual commitment savings (30-40% discount)
- ROI calculations
- Scaling recommendations

### SE Implementation Guide
Step-by-step technical guide for Solution Engineers:
- 6-phase implementation plan with code examples
- Python SDK snippets for all operations
- Industry-specific prompts
- API quick reference
- Best practices and tips

### Download All ZIP (PDF/DOCX)
- Step 6 now includes **Download All** controls that bundle every generated Markdown deliverable into a single ZIP.
- The backend converts Markdown → HTML once and then:
  - Renders PDFs via **WeasyPrint** for print-ready exports.
  - Builds DOCX files via **python-docx**/**html2docx** for easy editing in Word.
- Added Python dependencies: `markdown`, `weasyprint`, `html2docx`, `python-docx` (already listed in `requirements.txt`).
- Local OS prerequisites for WeasyPrint (install via your package manager): `cairo`, `pango`, `gdk-pixbuf` (Linux), or `brew install cairo pango gdk-pixbuf` (macOS).
- The UI lets users choose PDF or DOCX output and shows loading/error states while the ZIP streams down.
- API endpoint: `GET /api/projects/{project_id}/outputs/zip`
  - Query params:
    - `format=pdf|docx` (default `pdf`).
    - `include_md=true|false` (defaults to the environment toggle described below).
  - Response: `application/zip` with filenames such as `discovery_<timestamp>.pdf`.
- Environment toggles:
  - `DOWNLOAD_PAGE_SIZE=LETTER|A4` sets the `@page` size used by WeasyPrint (default `LETTER`).
  - `DOWNLOAD_INCLUDE_MD=true|false` controls whether raw Markdown files are bundled when the query param is omitted (default `false`).

## 🤖 Model Recommendations

The framework prioritizes **Vision-Language Models (VLMs)** over legacy computer vision approaches:

### Primary Recommended Model
| Model | Type | Use Cases |
|-------|------|-----------|
| **mm-poly-8b** ⭐ | VLM | Image understanding, document analysis, visual QA |

> ⚠️ **Important**: VLMs like mm-poly-8b return **text/JSON responses only**. They describe what they see but do NOT generate visual outputs (no heatmaps, attention maps, or bounding boxes). For visual annotations, use dedicated detection or segmentation models.

### Model Selection Philosophy
1. **VLMs First** - Use multimodal models for vision tasks
2. **Custom Training** - Only when VLMs don't meet accuracy requirements
3. **Clarifai Models** - Prioritized in all recommendations

### Available Model APIs

| Endpoint | Description |
|----------|-------------|
| `GET /api/models/vlms` | List all Vision-Language Models |
| `GET /api/models/llms` | List all Large Language Models |
| `GET /api/models/embeddings` | List embedding models |
| `GET /api/models/search?use_case=X` | Search models by use case |
| `GET /api/models/recommendations/{project_id}` | Get project-specific recommendations |
| `GET /api/models/tasks` | List all supported model tasks |

## 💰 GPU Pricing Data

Pricing data is stored in [config/pricing.json](config/pricing.json) for easy updates without code changes.

### Updating Pricing
1. Edit `config/pricing.json`
2. Restart the application (or call the reload endpoint)

### GPU Tiers
| Tier | VRAM | Example GPUs | Use Cases |
|------|------|--------------|-----------|
| Entry | 16GB | T4, RTX 4000 | Development, small models |
| Standard | 24GB | L4, RTX 4090 | Production inference, 7B models |
| Professional | 48GB | L40, A40 | Fine-tuning, 13B models |
| Enterprise | 80GB | A100, H100 | Large models, training |

### Pricing APIs

| Endpoint | Description |
|----------|-------------|
| `GET /api/pricing/gpus` | All GPU pricing with filters |
| `GET /api/pricing/cpus` | CPU instance pricing |
| `GET /api/pricing/regions` | Available regions |
| `GET /api/pricing/tiers` | GPU tier definitions |
| `GET /api/pricing/recommendations?workload=X` | Workload-based recommendations |
| `GET /api/pricing/compare?gpus=A,B` | Compare specific GPUs |

## 🏭 Industry Questions

Pre-configured discovery questions for common industries:

- **Retail/E-commerce** - Product recognition, inventory, recommendations
- **Manufacturing** - Quality inspection, defect detection, safety
- **Healthcare** - Medical imaging, diagnostics, compliance
- **Logistics** - Package tracking, route optimization, damage detection
- **Financial Services** - Document processing, fraud detection
- **Media/Entertainment** - Content moderation, tagging, search

### Industry APIs

| Endpoint | Description |
|----------|-------------|
| `GET /api/industries` | List all industries |
| `GET /api/industries/{industry}/questions` | Get questions for industry |
| `POST /api/industries/{industry}/questions` | Add custom questions |
| `POST /api/industries/{industry}/questions/generate` | AI-generate questions |

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Web Interface                            │
│              (Alpine.js + Tailwind CSS + FastAPI)                │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │  Document   │  │  Proposal   │  │   Discovery Question    │  │
│  │  Processor  │  │  Generator  │  │      Generator          │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │  Compute    │  │  SE Guide   │  │   Model Discovery       │  │
│  │  Analyzer   │  │  Generator  │  │   (Hugging Face)        │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│                      Clarifai Client Layer                       │
│  ┌─────────────────────┐  ┌─────────────────────────────────┐   │
│  │   GPT-OSS-120B      │  │      MM-Poly-8B                 │   │
│  │   (Text/Reasoning)  │  │  (Multimodal: Image/Video/Audio)│   │
│  │   8K context/doc    │  │  Clarifai Primary VLM           │   │
│  └─────────────────────┘  └─────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## 📁 Project Structure

```
hackday-rapid-prototyping/
├── src/
│   ├── web/
│   │   ├── app.py                  # FastAPI application (main entry)
│   │   ├── static/
│   │   │   └── index.html          # Single-page web application
│   │   ├── industry_questions.py   # Industry question management
│   │   ├── pricing_data.py         # GPU/CPU pricing database
│   │   └── huggingface_models.py   # Model discovery & recommendations
│   ├── agents/
│   │   ├── proposal_agent.py       # Proposal generation agent
│   │   ├── discovery_agent.py      # Discovery questions agent
│   │   └── solution_agent.py       # Solution architecture agent
│   ├── clients/
│   │   └── clarifai_client.py      # Clarifai API wrapper
│   ├── processors/
│   │   ├── document_processor.py   # PDF, DOCX, MD, TXT processing
│   │   └── image_processor.py      # Image analysis
│   └── config.py                   # Configuration management
├── config/
│   ├── models.yaml                 # Model configuration
│   ├── pricing.json                # GPU/CPU pricing data (editable)
│   └── prompts/                    # System prompts
│       ├── proposal.md
│       ├── discovery.md
│       └── solution.md
├── projects/                       # Generated project outputs
├── uploads/                        # Uploaded customer files
├── examples/
│   └── sample_input.md
├── Dockerfile
├── docker-compose.yaml
├── requirements.txt
└── README.md
```

## 🔌 API Reference

### Project Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/projects` | Create new project |
| `GET` | `/api/projects` | List all projects |
| `GET` | `/api/projects/{id}` | Get project details |
| `DELETE` | `/api/projects/{id}` | Delete project |
| `POST` | `/api/projects/{id}/upload` | Upload files to project |
| `GET` | `/api/projects/{id}/files` | List project files |

### Document Generation

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/generate/discovery` | Generate discovery questions |
| `POST` | `/api/generate/proposal` | Generate project proposal |
| `POST` | `/api/generate/compute-analysis` | Generate compute analysis & ROI |
| `POST` | `/api/generate/se-guide` | Generate SE implementation guide |

### Outputs

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/outputs/{project_id}/{filename}` | Download generated document |
| `DELETE` | `/api/outputs/{project_id}/{filename}` | Delete a generated document and update metadata |
| `GET` | `/api/projects/{project_id}/outputs/zip?format=pdf&include_md=false` | Stream a ZIP containing all project documents converted to PDF or DOCX |

### Uploaded Files

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/projects/{project_id}/files` | List uploaded project files |
| `GET` | `/api/projects/{project_id}/uploads/{filename}` | Download/serve an uploaded file |
| `DELETE` | `/api/projects/{project_id}/uploads/{filename}` | Delete an uploaded file and update metadata |

## 🔧 Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `CLARIFAI_API_KEY` | Your Clarifai Personal Access Token | Yes | - |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARN, ERROR) | No | INFO |
| `PORT` | Server port | No | 8080 |

## 📊 Document Processing

### Supported File Types
| Type | Extensions | Max Size |
|------|------------|----------|
| Text | `.txt`, `.md` | 8,000 chars |
| PDF | `.pdf` | 8,000 chars |
| Word | `.docx` | 8,000 chars |
| Images | `.png`, `.jpg`, `.jpeg` | 10MB |

### Processing Pipeline
1. Files uploaded to project directory
2. Text extracted from documents (PDF/DOCX support)
3. Content concatenated with 8K char limit per file
4. Sent to GPT-OSS-120B for analysis/generation

## 🎨 UI Components

### Help Overlay
Press `?` to access:
- Quick start guide
- Feature descriptions
- Model recommendations table
- Example use cases
- Resource links

### Sticky Footer
- Clarifai branding
- Links to main site and documentation
- Copyright information

### Document Viewer
- Full-screen markdown preview
- Download functionality
- Syntax highlighting for code blocks

## 🔐 Security Notes

- API key stored in environment variable only
- No credentials persisted to disk
- CORS enabled for development (configure for production)
- File uploads validated by extension

## 🚢 Deployment

### Docker Compose (Development)
```yaml
version: '3.8'
services:
  web:
    build: .
    ports:
      - "8080:8080"
    environment:
      - CLARIFAI_API_KEY=${CLARIFAI_API_KEY}
    volumes:
      - ./projects:/app/projects
      - ./uploads:/app/uploads
```

### Production Considerations
- Set specific CORS origins
- Use secrets management for API key
- Add rate limiting
- Enable HTTPS
- Configure persistent storage

## 📄 License

MIT License - See LICENSE file for details
