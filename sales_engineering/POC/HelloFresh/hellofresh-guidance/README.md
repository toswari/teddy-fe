# HelloFresh AI Brand Compliance Specialist

A sophisticated Streamlit web application that functions as an automated Brand Compliance Specialist for HelloFresh, powered by Clarifai's advanced AI models with deterministic predictions and enhanced JSON processing.

## 🎯 Overview

This application analyzes visual assets (images and PDFs) to ensure adherence to HelloFresh's corporate branding guidelines using state-of-the-art multimodal Large Language Models (LLMs) via the Clarifai API. Features deterministic predictions with temperature=0, simplified JSON format, and comprehensive brand validation.

## ✨ Features

### Core Functionality ✅ PRODUCTION READY
- **Multi-Model AI Analysis**: Support for Gemini 2.5 Pro, Gemini 1.5 Pro, GPT-4o, and MM Poly 8B
- **Deterministic Predictions**: Temperature=0.0 for consistent, reproducible results
- **Enhanced JSON Processing**: Simplified format with separate description/recommendation fields
- **Multi-Format Support**: Upload images (PNG, JPG, JPEG) and multi-page PDFs
- **Real-time Analysis**: Live HelloFresh brand guideline compliance checking
- **Comprehensive Reporting**: Downloadable PDF reports with detailed findings
- **Historical Dashboard**: Statistics and trends with interactive charts
- **Database Persistence**: SQLite database for all analysis activities

### HelloFresh Brand Guidelines Checked
1. **Logo Integrity**: HelloFresh logo must not be stretched, rotated, recolored, or modified
2. **Brand Name Spelling**: Accepts both "HelloFresh" and "HELLO FRESH" formats
3. **Packaging Design**: Official HelloFresh branding with correct green color scheme
4. **Text Legibility**: Clear, legible text with sufficient size and contrast
5. **Food Presentation**: Aesthetically pleasing, well-lit, and appetizing food imagery
6. **Brand Prominence**: HelloFresh logo clearly visible and prominent
7. **Offer Disclaimer Pairing**: All offers paired with legally required disclaimer text

## 🚀 Quick Start

### Prerequisites
- Python 3.11 or 3.12
- Conda environment
- Clarifai API key (Personal Access Token)

### Installation

1. **Clone and setup**:
   ```bash
   cd /path/to/hellofresh-guidance
   conda create -n brand-logo-312 python=3.12
   conda activate brand-logo-312
   pip install -r requirements.txt
   ```

2. **Configure Clarifai API**:
   - Get your PAT from [Clarifai Security Settings](https://clarifai.com/settings/security)
   - Add it to `.streamlit/secrets.toml`:
     ```toml
     CLARIFAI_PAT = "your_personal_access_token_here"
     ```

3. **Test the setup**:
   ```bash
   conda activate brand-logo-312
   python test_setup.py
   ```

4. **Start the application**:
   ```bash
   ./start.sh
   # or using conda helper script
   ./conda_run.sh app
   # or manually
   conda activate brand-logo-312
   streamlit run app.py
   ```

## 🐍 Conda Environment Management

This project includes helper scripts to ensure consistent use of the `brand-logo-312` conda environment:

### Using conda_run.sh (Recommended)
```bash
# Install dependencies
./conda_run.sh install

# Run tests
./conda_run.sh test

# Start application
./conda_run.sh app

# Run any Python script
./conda_run.sh python script.py

# Install packages
./conda_run.sh pip install package_name

# Check environment status
./conda_run.sh check

# Get activation command for manual use
./conda_run.sh shell
```

## 📁 Project Structure

```
hellofresh-guidance/
├── app.py                  # Main Streamlit application
├── config.toml            # Model configurations and HelloFresh prompts
├── config_loader.py       # Configuration management (updated for unified TOML)
├── clarifai_utils.py      # Clarifai API integration with temperature=0
├── database.py            # SQLite database operations
├── utils.py               # PDF processing and reporting
├── start.sh               # Application startup script
├── requirements.txt       # Python dependencies
├── .streamlit/
│   └── secrets.toml       # API keys and configuration
├── DetailDesign.md        # Detailed technical specification
├── SoftwareSpec.md        # Software requirements (updated)
├── PhasesTaksList.md      # Implementation checklist
└── README.md              # This file
```

## 🔧 Configuration

### Adding New Models

Edit `config.toml` to add new AI models:

```toml
[prompts."new-model-id"]
model_name = "Model Display Name"
model_url = "https://clarifai.com/owner/app/models/model-name"
prompt_text = """
Your detailed prompt for brand compliance analysis...
"""
```

### Customizing Brand Guidelines

Modify the `prompt_text` in `config.toml` to adjust HelloFresh brand guidelines or analysis criteria. All models are configured with unified prompts for consistent analysis.

## 📊 Database Schema

### analysis_log
- `id` (Primary Key)
- `timestamp` (Analysis time)
- `filename` (Asset filename)
- `page_number` (PDF page number, if applicable)
- `model_id` (AI model used)
- `response_time_seconds` (API response time)
- `input_tokens` / `output_tokens` (Token usage)
- `compliance_status` (Compliant/Non-Compliant/No Logo Found)

### violations_log
- `id` (Primary Key)
- `analysis_id` (Foreign key to analysis_log)
- `rule_violated` (Specific guideline violated)
- `description` (Detailed violation description)

## 🔍 API Integration

The application uses the Clarifai Python SDK with enhanced configuration and deterministic predictions:

```python
from clarifai.client import Model

# Initialize model with URL and PAT
model = Model(url=model_url, pat=clarifai_pat)

# Make prediction with deterministic settings (temperature=0)
response = model.predict(inputs=[{
    "data": {
        "image": {"base64": image_base64},
        "text": {"raw": prompt_text}
    }
}], inference_params={"temperature": 0.0})
```

## 📈 Statistics Dashboard

The dashboard provides comprehensive analytics:

- **Key Metrics**: Total requests, compliance rate, response times
- **Token Usage**: Breakdown by model with visualizations
- **Compliance Trends**: 30-day trend analysis
- **Common Violations**: Most frequent guideline violations
- **Recent Activity**: Searchable table of recent analyses

## 🧪 Testing

Run the comprehensive test suite:

```bash
conda activate brand-logo-312
python test_setup.py
```

Tests cover:
- ✅ Import verification
- ✅ Configuration loading
- ✅ Database operations
- ✅ PDF generation
- ✅ Clarifai API connectivity

## 🔒 Security

- API keys stored in Streamlit secrets
- Local SQLite database (no cloud data storage)
- Configurable model endpoints
- Error handling for API failures

## 🎨 User Interface

### Compliance Analysis Page
- Multi-file upload with drag-and-drop
- Real-time progress tracking
- Detailed results with expandable sections
- Visual status indicators (✅ ❌ 🔍)
- Summary metrics and recommendations
- PDF report generation

### Statistics Dashboard
- Interactive charts with Plotly
- Filtering and search capabilities
- AI-generated insights
- Historical trend analysis
- Token usage monitoring

## 🚧 Future Enhancements (Phase 2)

- **Visual Feedback**: Bounding box annotations on images
- **Example Gallery**: Pre-loaded sample analyses
- **Enhanced UX**: Better progress indicators and error handling
- **Advanced Analytics**: More sophisticated insights and recommendations

## 📝 API Response Format

The application uses an enhanced JSON format with separate description and recommendation fields:

```json
{
  "compliance_status": "Compliant|Non-Compliant|No Logo Found",
  "logo_type": "HelloFresh Creative",
  "summary": "Brief analysis summary",
  "violations": [
    {
      "rule_violated": "Specific HelloFresh guideline name",
      "description": "Detailed violation description",
      "recommendation": "Specific corrective action needed"
    }
  ],
  "confidence_score": 0.95
}
```

## 🔧 Key Improvements

- **Deterministic Results**: Temperature=0.0 for consistent analysis
- **Enhanced JSON**: Simplified format with better parsing
- **Unified Configuration**: All prompts centralized in config.toml
- **Better Brand Rules**: Updated to accept multiple valid HelloFresh formats
- **Improved UI**: Better violation display with proper indentation

## 🤝 Contributing

1. Follow the existing code structure
2. Add tests for new functionality
3. Update documentation
4. Ensure all tests pass before committing

## 📄 License

This project is proprietary to HelloFresh.

## 🔗 Links

- [Clarifai Documentation](https://docs.clarifai.com/)
- [Streamlit Documentation](https://docs.streamlit.io/)
- [Detailed Design Specification](DetailDesign.md)

---

*Built with ❤️ for HelloFresh using Streamlit and Clarifai AI*
