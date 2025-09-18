# KIA AI Brand Compliance Specialist 🚗✨

A sophisticated Streamlit web application that functions as an automated Brand Compliance Specialist for KIA Motors, powered by Clarifai's advanced AI models with enhanced batch processing and professional-grade PDF reporting.

## 🎯 Overview

This application analyzes visual assets (images and PDFs) to ensure adherence to KIA's corporate branding guidelines using state-of-the-art multimodal Large Language Models (LLMs) via the Clarifai API. The system now features advanced batch processing capabilities and WeasyPrint-powered PDF generation with full emoji and styling support.

## ✨ Features

### Phase 1: Core Functionality ✅
- **Multi-Model AI Analysis**: Support for Claude 3.5 Sonnet, Gemini 1.5 Pro, GPT-4o, and more
- **Advanced Batch Processing**: Process 1-10 images simultaneously with intelligent rate limiting
- **Multi-Format Support**: Upload images (PNG, JPG, JPEG) and multi-page PDFs
- **Real-time Analysis**: Live brand guideline compliance checking with progress tracking
- **Enhanced PDF Reports**: Professional-grade reports with WeasyPrint (emoji and styling support)
- **KIA-Branded Reports**: Official KIA styling with corporate colors and branding
- **Historical Dashboard**: Statistics and trends with interactive Plotly charts
- **Database Persistence**: SQLite database for all analysis activities and analytics

### Phase 2: Enhanced Features ✅
- **WeasyPrint Integration**: Modern PDF generation with full Unicode and emoji support
- **Batch Processing System**: Configurable batch sizes with progress indicators
- **Token Usage Analytics**: Detailed tracking of AI model token consumption
- **Advanced Error Handling**: Robust retry logic and graceful failure handling
- **Responsive UI**: Enhanced user interface with real-time feedback

### Brand Guidelines Checked
1. **Logo Placement**: Proper positioning and visibility assessment
2. **Logo Size**: Adequate size for clear recognition and brand impact
3. **Logo Rotation**: Correct orientation (not tilted/rotated)
4. **Color Usage**: Official KIA brand colors (black, red, white, silver)
5. **Logo Count**: Single primary logo per asset (avoid redundancy)
6. **Background Contrast**: Sufficient contrast for optimal visibility
7. **Logo Integrity**: No distortion, stretching, or unauthorized modification
8. **Brand Consistency**: Adherence to KIA corporate identity standards

## 🚀 Quick Start

### Prerequisites
- Python 3.11 or 3.12
- Conda environment (recommended) or virtual environment
- Clarifai API key (Personal Access Token)
- WeasyPrint dependencies (automatically installed)

### Installation

1. **Clone and setup**:
   ```bash
   cd /path/to/kia-guidance
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

3. **Start the application**:
   ```bash
   ./start.sh
   # or manually:
   streamlit run app.py
   ```

### Batch Processing Configuration

Configure batch processing in the application:
- **Batch Size**: 1-10 images (adjustable in sidebar)
- **Rate Limiting**: Automatic delays between batches
- **Progress Tracking**: Real-time progress indicators
- **Error Handling**: Automatic retry with exponential backoff

## 📁 Project Structure

```
kia-guidance/
├── app.py                            # Main Streamlit application
├── config.toml                       # Model configurations and prompts
├── config_loader.py                  # Configuration management
├── clarifai_utils.py                 # Clarifai API integration & batch processing
├── database.py                       # SQLite database operations
├── utils.py                          # PDF processing and utilities
├── pdf_report_generator.py           # Legacy PDF generation (fpdf2)
├── weasyprint_report_generator.py    # Modern PDF generation (WeasyPrint)
├── kia_branded_report_generator.py   # KIA-specific branded reports
├── start.sh                          # Application startup script
├── requirements.txt                  # Python dependencies
├── models.yaml                       # AI model configurations
├── .streamlit/
│   ├── secrets.toml                  # API keys and configuration
│   └── config.toml                   # Streamlit settings
├── .gitignore                        # Git ignore patterns
├── sample-codes/                     # Sample code snippets
├── documentation/
│   ├── BATCH_PROCESSING.md           # Batch processing documentation
│   ├── WEASYPRINT_UPGRADE_SUMMARY.md # PDF generation upgrade notes
│   ├── DetailDesign.md               # Detailed technical specification
│   ├── SoftwareSpec.md               # Software requirements
│   └── PhasesTaksList.md             # Implementation checklist
└── README.md                         # This file
```

## 🔧 Configuration

### Batch Processing Settings

Configure batch processing in `clarifai_utils.py`:

```python
# Batch size validation (1-10 images)
def validate_batch_size(batch_size):
    return max(1, min(batch_size, 10))

# Rate limiting between batches
BATCH_DELAY = 2.0  # seconds between batches
API_DELAY = 1.0    # seconds between individual API calls
```

### Adding New AI Models

Edit `config.toml` to add new AI models:

```toml
[prompts."new-model-id"]
model_name = "Model Display Name"
model_url = "https://clarifai.com/owner/app/models/model-name"
prompt_text = """
Your detailed prompt for KIA brand compliance analysis...
"""
```

### PDF Report Configuration

Choose between PDF generation methods:
- **WeasyPrint** (recommended): Modern styling with emoji support
- **fpdf2** (legacy): Basic PDF generation
- **KIA Branded**: Official KIA corporate styling

### Customizing Brand Guidelines

Modify the `prompt_text` in `config.toml` to adjust brand guidelines or analysis criteria specific to KIA's requirements.

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

## 🔍 API Integration & Batch Processing

The application uses the Clarifai Python SDK with enhanced batch processing capabilities:

```python
from clarifai.client import Model
from clarifai_utils import analyze_images_batch

# Initialize model with URL and PAT
model = Model(url=model_url, pat=clarifai_pat)

# Batch processing with progress tracking
results = analyze_images_batch(
    images=image_list,
    model_config=selected_model,
    batch_size=batch_size,
    progress_callback=update_progress
)
```

### Batch Processing Features:
- **Configurable Batch Sizes**: 1-10 images per batch
- **Progress Tracking**: Real-time progress bars and status updates
- **Error Handling**: Automatic retry logic with exponential backoff
- **Rate Limiting**: Intelligent delays to respect API limits
- **Token Tracking**: Detailed monitoring of input/output tokens

## 📈 Analytics Dashboard

The enhanced dashboard provides comprehensive analytics:

- **Key Metrics**: Total requests, compliance rate, average response times
- **Token Usage Analytics**: Breakdown by model with detailed visualizations
- **Compliance Trends**: 30-day trend analysis with predictive insights
- **Common Violations**: Most frequent guideline violations with recommendations
- **Recent Activity**: Searchable and filterable table of recent analyses
- **Batch Processing Stats**: Performance metrics for batch operations
- **Model Performance**: Comparative analysis across different AI models

### New Features:
- **Interactive Charts**: Plotly-powered visualizations with drill-down capabilities
- **Export Functionality**: Download analytics data as CSV/Excel
- **Real-time Updates**: Live dashboard updates during batch processing
- **Performance Monitoring**: API response times and token efficiency tracking

## 🧪 Testing & Quality Assurance

Comprehensive testing suite for all components:

```bash
# Run all tests
python -m pytest tests/

# Test individual components
python -m pytest tests/test_batch_processing.py
python -m pytest tests/test_weasyprint.py
python -m pytest tests/test_database.py
```

### Test Coverage:
- ✅ **Import verification**: All modules load correctly
- ✅ **Configuration loading**: TOML and YAML parsing
- ✅ **Database operations**: SQLite CRUD operations
- ✅ **PDF generation**: Both WeasyPrint and fpdf2
- ✅ **Clarifai API connectivity**: Model availability and authentication
- ✅ **Batch processing**: Various batch sizes and error scenarios
- ✅ **UI components**: Streamlit interface functionality

## 🔒 Security

- API keys stored in Streamlit secrets
- Local SQLite database (no cloud data storage)
- Configurable model endpoints
- Error handling for API failures

## 🎨 User Interface & Experience

### Compliance Analysis Page
- **Multi-file upload**: Drag-and-drop interface supporting multiple file formats
- **Batch configuration**: Adjustable batch size (1-10 images) with real-time validation
- **Progress tracking**: Multi-level progress bars (overall, batch, individual)
- **Live results**: Real-time display of analysis results as they complete
- **Visual status indicators**: Intuitive icons (✅ ❌ 🔍) with color coding
- **Summary metrics**: Instant compliance statistics and recommendations
- **Enhanced PDF reports**: Professional reports with WeasyPrint styling
- **KIA branding**: Official corporate styling and color schemes

### Analytics Dashboard
- **Interactive visualizations**: Plotly charts with zoom, filter, and export
- **Real-time updates**: Live data refresh during batch processing
- **Filtering capabilities**: Advanced search and filter options
- **AI-generated insights**: Automated recommendations based on analysis patterns
- **Historical trend analysis**: Long-term compliance tracking
- **Token usage monitoring**: Cost analysis and optimization recommendations

### Enhanced Features
- **Responsive design**: Optimized for desktop and tablet viewing
- **Error handling**: User-friendly error messages with recovery suggestions
- **Performance indicators**: Real-time API response time monitoring
- **Accessibility**: WCAG-compliant interface elements

## 🚧 Recent Updates & Enhancements

### ✅ Phase 2 Completed Features:
- **WeasyPrint Integration**: Complete migration from fpdf2 to WeasyPrint
- **Emoji Support**: Full Unicode support in PDF reports with proper emoji rendering
- **Batch Processing**: Intelligent batch processing system with configurable sizes
- **KIA Branding**: Official KIA corporate styling in reports and interface
- **Enhanced Analytics**: Advanced token usage tracking and performance metrics
- **Error Resilience**: Robust retry logic and graceful error handling
- **Progress Tracking**: Multi-level progress indicators for batch operations

### 🔄 Future Enhancements (Phase 3):
- **Visual Feedback**: Bounding box annotations on detected logos
- **Advanced AI Models**: Integration with latest Clarifai model releases
- **Custom Brand Guidelines**: Configurable compliance rules per brand
- **API Rate Optimization**: Smart caching and request optimization
- **Enhanced UX**: Improved mobile responsiveness and accessibility
- **Integration Options**: REST API endpoints for external system integration

## 🔧 Technical Requirements

### System Dependencies:
```bash
# Core Python packages
streamlit>=1.38.0
clarifai>=11.6.0
weasyprint>=62.3

# Data processing
pandas>=2.3.0
plotly>=6.3.0
PyMuPDF>=1.24.0

# Configuration
pyyaml>=6.0.1
toml>=0.10.0
python-dotenv>=1.0.1

# Testing
pytest>=8.2.0
```

### WeasyPrint System Dependencies:
- **Linux**: `apt-get install python3-cffi python3-brotli libpango-1.0-0 libharfbuzz0b libpangoft2-1.0-0`
- **macOS**: `brew install python-cffi pango`
- **Windows**: Most dependencies included with weasyprint package

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

## 📄 License

This project is proprietary software developed for KIA Motors Corporation. All rights reserved.

## 🔗 Resources & Documentation

- [Clarifai Documentation](https://docs.clarifai.com/) - API reference and guides
- [Streamlit Documentation](https://docs.streamlit.io/) - Web framework documentation
- [WeasyPrint Documentation](https://doc.courtbouillon.org/weasyprint/) - PDF generation library
- [KIA Brand Guidelines](internal-link) - Official KIA branding standards
- [Project Documentation](./documentation/) - Detailed technical specifications:
  - [Batch Processing Guide](./BATCH_PROCESSING.md)
  - [WeasyPrint Migration](./WEASYPRINT_UPGRADE_SUMMARY.md)
  - [Detailed Design](./DetailDesign.md)
  - [Software Specification](./SoftwareSpec.md)

## 🤝 Contributing & Support

### Development Guidelines:
1. **Code Quality**: Follow existing code structure and naming conventions
2. **Testing**: Add comprehensive tests for new functionality
3. **Documentation**: Update relevant documentation files
4. **Performance**: Ensure all tests pass and performance benchmarks are met
5. **Security**: Follow secure coding practices, especially for API key handling

### Getting Help:
- Check the [troubleshooting section](./documentation/FIXES_SUMMARY.md)
- Review [batch processing documentation](./BATCH_PROCESSING.md)
- Contact the development team for KIA-specific customizations

---

*Built with ❤️ for KIA Motors using Streamlit, Clarifai AI, and WeasyPrint*

**Last Updated**: September 2025 | **Version**: 2.0 | **Status**: Production Ready ✅
