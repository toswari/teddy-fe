# Clarifai Multimodal Chatbot 🤖

An interactive web-based chatbot for IKEA Digital Asset Management (DAM) that allows users to upload images or use URLs, ask questions, and get instant AI-powered analysis using Clarifai's multimodal models.

## 🚀 What's New (September 2025)

- **Image Upload & URL Input:** Both methods now fully supported and robust
- **IKEA Collection Classification:** 21 collections with detailed discriminators
- **MergeFrom Error Fixed:** Multiple fallback methods (SDK & protobuf) for input creation
- **Advanced Error Handling:** Clear messages for API/auth issues, image format, and more
- **Port 8502 Configuration:** Default for chatbot deployment
- **Debug Mode:** Toggle for troubleshooting and API key masking
- **Professional UI:** IKEA-themed, responsive, and user-friendly

## Features

- 📷 **Image Upload & URL Input**: Analyze images from your device or the web
🧠 **Multiple AI Models**: Choose from top multimodal models (MM-Poly-8B (default), MiniCPM, GPT-4o, Claude, etc.)
- 🏷️ **IKEA Collection & Taxonomy Detection**: Classifies images into IKEA collections, room types, design styles, and activities
- 💬 **Interactive Chat**: Real-time Q&A with AI
- 📊 **Conversation History**: Track your analysis
- 🎨 **User-Friendly Interface**: Clean, IKEA-inspired design

## Quick Start

1. **Setup**
   - Run `./setup.sh` or use conda/pip as described below
2. **Configure API Key**
   - Add your Clarifai PAT to `.streamlit/secrets.toml`
3. **Run the Chatbot**
   - `./run_chatbot.sh` (opens at <http://localhost:8502>)

## How to Use

1. **Select a Model** in the sidebar
2. **Add an Image** (upload or URL)
3. **Ask Questions** about the image
4. **Get AI Responses** (IKEA taxonomy, collection, and more)

## Example Questions

- "What IKEA collection does this product belong to?"
- "Describe the room type and design style."
- "Suggest DAM tags for this image."
- "What activities are visible in this photo?"

## Available Models

**MM-Poly-8B** (Default): Good for visual reasoning
**MiniCPM-o-2.6**: Best for general vision tasks
**GPT-5**: Latest OpenAI model with advanced capabilities
**GPT-4o**: Excellent for detailed analysis
**GPT-4o Mini**: Faster, cost-effective option
**Claude-3.5 Sonnet**: Great for creative descriptions

## Technical Highlights

- **Fallback Input Creation:** Tries SDK and protobuf methods to avoid MergeFrom errors
- **Authentication Validation:** Checks and masks API key in debug mode
- **Comprehensive Prompts:** 4,784-character IKEA collection prompt, taxonomy, and activities
- **Sample Images:** Quick-start with pre-configured rooms
- **Test Files:** Integration and prompt tests included

## IKEA Collection Classification

The chatbot can identify and classify images into 21 IKEA collections:

**Modern Collections:**
- BRÄNNBOLL, STOCKHOLM, SKOGSDUVA

**Seasonal Collections:**
- HÖSTAGILLE, VINTERFINT, AFTONSPARV

**Designer Collections:**
- Design by Ilse Crawford, MÄVINN, BLÅVINGAD

**And many more including:** SÖTRÖNN, Nytillverkad, TESAMMANS, BRÖGGAN, DAKSJUS, HÄSTHAGE, FRÖJDA, TJÄRLEK, OMMJÄNGE, KÖSSEBÄR, KUSTFYR, Tyg collection

## Setup Instructions

### 1. Environment Setup

**Option A: Automated Setup (Recommended)**
```bash
./setup.sh
```

**Option B: Manual Setup with Conda**
```bash
conda env create -f environment.yml
conda activate clarifai-chatbot
```

**Option C: Manual Setup with Pip**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. API Key Configuration

1. Get your Clarifai API key from: <https://clarifai.com/settings/security>
2. Create `.streamlit/secrets.toml`:
```toml
[clarifai]
PAT = "your_actual_api_key_here"
```

### 3. Run the Application

```bash
./run_chatbot.sh
```

The chatbot will open at <http://localhost:8502>

## Troubleshooting

### Common Issues

1. **403 Errors (Authentication)**
   - Verify API key is correct in `.streamlit/secrets.toml`
   - Check API key permissions at Clarifai dashboard
   - Ensure no extra spaces or quotes in the key

2. **MergeFrom Errors (Input Format)**
   - Handled automatically with multiple fallback methods
   - Try different image formats (PNG, JPG, JPEG, WebP)
   - Enable debug mode to see detailed error information

3. **Image Upload Issues**
   - Check file size (max 10MB by default)
   - Ensure image format is supported
   - Try using image URL instead of upload

4. **Model Timeout or Errors**
   - Try a different model (MiniCPM-o-2.6 is most reliable)
   - Check internet connection
   - Verify image is accessible (for URLs)

### Debug Mode

Enable debug mode in `app_config.toml`:
```toml
[debug]
debug_prompts = true
```

This will show:
- Detailed error messages
- API key masking for security
- Input type information
- Model URL verification

## File Structure

```
ikea-dam-chatbot/
├── .streamlit/
│   ├── secrets.toml          # API keys (create this)
│   └── secrets.toml.example  # Template for secrets
├── app_config.toml           # Main configuration and IKEA prompts
├── chatbot_app.py            # Main Streamlit application
├── run_chatbot.sh            # Launcher script (port 8502)
├── requirements.txt          # Python dependencies
├── environment.yml           # Conda environment
├── setup.sh                  # Automated setup script
├── test_setup.py             # API connection tester
├── validate_models.py        # Model validation script
├── validate_prompts.py       # Prompt testing script
├── COLLECTION_FEATURE_SUMMARY.md  # Feature documentation
├── MODEL_VALIDATION_REPORT.md     # Model testing results
└── README.md                 # This file
```

## Configuration

The application uses `app_config.toml` for comprehensive configuration:

- **App Settings**: Title, icon, layout preferences
- **Model Configuration**: Default model, conversation limits
- **IKEA Prompts**: Collection classification, taxonomy detection
- **UI Preferences**: Sample images, debug mode, file size limits
- **Sample Images**: Pre-configured test images for quick start

## Development & Customization

### Adding New Models

Edit the `MULTIMODAL_MODELS` dictionary in `chatbot_app.py`:
```python
MULTIMODAL_MODELS = {
    "Your Model Name": "https://clarifai.com/path/to/model",
    # ... existing models
}
```

### Customizing IKEA Collections

Edit the `ikea_collection_prompt` in `app_config.toml` to add or modify collection descriptions.

### UI Customization

Modify the CSS section in `chatbot_app.py` to change the IKEA-themed styling.

## Testing

Run the included test scripts:

```bash
# Test API connection
python test_setup.py

# Validate models
python validate_models.py

# Test prompts
python validate_prompts.py
```

## License

This project is based on Clarifai's sample code and follows their usage terms.

---

## Status: All Features Working ✅

- ✅ Image Upload (File)
- ✅ Image Input (URL)
- ✅ IKEA Collection Classification (21 collections)
- ✅ Taxonomy Detection (Room types, Design styles, Activities)
- ✅ MergeFrom Error Handling
- ✅ Authentication Validation
- ✅ Debug Mode
- ✅ Professional UI

**Happy analyzing with AI! 🏠✨**
