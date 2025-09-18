# AI Brand Compliance Specialist

A sophisticated Streamlit web application that functions as an automated Brand Compliance Specialist for Kia Corporation, powered by Clarifai's advanced AI models.

## 🎯 Overview

This application analyzes visual assets (images and PDFs) to ensure adherence to Kia's corporate branding guidelines using state-of-the-art multimodal Large Language Models (LLMs) via the Clarifai API.

## ✨ Features

### Phase 1: Core Functionality ✅
- **Multi-Model AI Analysis**: Support for Gemini 1.5 Pro, GPT-4o, and Claude 3.5 Sonnet
- **Multi-Format Support**: Upload images (PNG, JPG, JPEG) and multi-page PDFs
- **Real-time Analysis**: Live brand guideline compliance checking
- **Comprehensive Reporting**: Downloadable PDF reports with detailed findings
- **Historical Dashboard**: Statistics and trends with interactive charts
- **Database Persistence**: SQLite database for all analysis activities

### Brand Guidelines Checked
1. **Logo Placement**: Proper positioning and visibility
2. **Logo Size**: Adequate size for clear recognition
3. **Logo Rotation**: Correct orientation (not tilted/rotated)
4. **Color Usage**: Official Kia brand colors (black, red, white)
5. **Logo Count**: Single primary logo per asset
6. **Background Contrast**: Sufficient contrast for visibility
7. **Logo Integrity**: No distortion, stretching, or modification

## 🚀 Quick Start

### Prerequisites
- Python 3.11 or 3.12
- Conda environment
- Clarifai API key (Personal Access Token)

### Installation

1. **Clone and setup**:
   ```bash
   cd /path/to/kia-guidance2
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
   python test_setup.py
   ```

4. **Start the application**:
   ```bash
   ./start.sh
   # or
   streamlit run app.py
   ```

## 📁 Project Structure

```
kia-guidance2/
├── app.py                  # Main Streamlit application
├── config.toml            # Model configurations and prompts
├── config_loader.py       # Configuration management
├── clarifai_utils.py      # Clarifai API integration
├── database.py            # SQLite database operations
├── utils.py               # PDF processing and reporting
├── test_setup.py          # Comprehensive testing script
├── start.sh               # Application startup script
├── requirements.txt       # Python dependencies
├── .streamlit/
│   └── secrets.toml       # API keys and configuration
├── DetailDesign.md        # Detailed technical specification
├── SoftwareSpec.md        # Software requirements
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

Modify the `prompt_text` in `config.toml` to adjust brand guidelines or analysis criteria.

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

The application uses the Clarifai Python SDK to interact with various AI models:

```python
from clarifai.client import Model

# Initialize model with URL and PAT
model = Model(url=model_url, pat=clarifai_pat)

# Make prediction with image and prompt
response = model.predict(inputs=[{
    "data": {
        "image": {"base64": image_base64},
        "text": {"raw": prompt_text}
    }
}])
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

The application expects AI models to return JSON in this format:

```json
{
  "compliance_status": "Compliant|Non-Compliant|No Logo Found",
  "summary": "Brief analysis summary",
  "violations": [
    {
      "rule_violated": "Specific guideline name",
      "description": "Detailed violation description"
    }
  ],
  "recommendations": ["Actionable suggestions"],
  "confidence_score": 0.95
}
```

## 🤝 Contributing

1. Follow the existing code structure
2. Add tests for new functionality
3. Update documentation
4. Ensure all tests pass before committing

## 📄 License

This project is proprietary to Kia Corporation.

## 🔗 Links

- [Clarifai Documentation](https://docs.clarifai.com/)
- [Streamlit Documentation](https://docs.streamlit.io/)
- [Detailed Design Specification](DetailDesign.md)

---

*Built with ❤️ using Streamlit and Clarifai AI*
