# HyperConnect Image Content Moderation

A comprehensive image classification system for content moderation using Clarifai's AI workflow. This tool processes images to identify potentially harmful content across 8 categories using multiple AI models for thorough analysis.

## 🎯 Purpose

This project provides **defensive security** capabilities for content moderation, helping identify and prevent harmful content including:
- Severe Violence
- Felony Crime
- Sexual Violence  
- Terrorism
- Suicide/Self-harm
- Child Sexual Abuse Material (CSAM)
- Prohibited Item Sales
- Innocent Content

## 🚀 Features

- **Multi-Model Analysis**: Leverages 3 different AI models for comprehensive content assessment
- **Batch Processing**: Process entire directories of images or individual URLs
- **Structured Output**: Detailed CSV reports with classification, confidence scores, and reasoning
- **Flexible Input**: Supports both local files and web URLs
- **Error Handling**: Robust error handling with detailed status reporting

## 📁 Project Structure

```
hyperconnect/
├── README.md                    # This file
├── CLAUDE.md                   # Development guidance for Claude Code
├── multi_model_classifier.py   # Main production script (recommended)
├── image_classifier.py         # Basic classification script
├── Initial_Prompt.txt          # Detailed classification guidelines
├── images/                     # Sample test images
│   ├── actor.jpeg
│   ├── breastfeeding1.jpeg
│   ├── drug4.jpeg
│   ├── protest1.jpeg
│   └── victoria_secret.jpeg
└── results/                    # Output directory for CSV results
```

## 🛠 Installation & Setup

### Prerequisites
- Python 3.7+
- Clarifai Python SDK

### Install Dependencies
```bash
pip install clarifai
```

### Authentication
You'll need a Clarifai PAT (Personal Access Token). The scripts include a default token, but you should replace it with your own:

```bash
# Option 1: Command line argument
python multi_model_classifier.py -p "your_pat_token_here" -d images/

# Option 2: Set environment variable
export CLARIFAI_PAT="your_pat_token_here"
```

## 🚀 Quick Start

### Process Local Images
```bash
# Process all images in a directory (recommended)
python multi_model_classifier.py -d images/ -o results/my_analysis.csv
```

### Process URLs
```bash
# Process image URLs
python multi_model_classifier.py -u "https://example.com/image1.jpg" "https://example.com/image2.jpg" -o results/url_analysis.csv
```

### Combined Processing
```bash
# Process both local images and URLs
python multi_model_classifier.py -d images/ -u "https://example.com/image.jpg" -o results/combined_analysis.csv
```

## 📊 Understanding the Results

### Multi-Model Analysis (Recommended)

The `multi_model_classifier.py` captures results from all 3 AI models:

#### 1. **Main Classification Model** (MiniCPM-o-2_6-language)
- **Purpose**: Primary content moderation with structured reasoning
- **Output**: Category classification (e.g., "8.0.0" for Innocent)
- **Fields**: `main_predicted_category`, `main_category_name`, `main_confidence_score`, `main_reasoning`

#### 2. **Basic Moderation Model** (Clarifai moderation-recognition)  
- **Purpose**: Quick safety assessment
- **Output**: Scores for 5 core safety concepts
- **Fields**: `basic_moderation_suggestive`, `basic_moderation_explicit`, `basic_moderation_safe`, `basic_moderation_drug`, `basic_moderation_gore`

#### 3. **Detailed Moderation Model** (moderation-all-resnext-2)
- **Purpose**: Granular content detection  
- **Output**: 20+ specific content concepts (weapons, nudity, drugs, etc.)
- **Fields**: `detailed_moderation_top_concept`, `detailed_moderation_top_score`, `detailed_moderation_concepts`

### Sample CSV Output

| source | main_predicted_category | main_category_name | main_confidence_score | basic_moderation_suggestive | detailed_moderation_top_concept |
|--------|------------------------|--------------------|----------------------|----------------------------|--------------------------------|
| actor.jpeg | 8.0.0 | INNOCENT - All Others | 100 | 0.9962 | nipples |
| protest1.jpeg | 8.0.0 | INNOCENT - All Others | 100 | 0.0000 | none |

## 📋 Classification Categories

### Main Categories (Two-Step Process):

1. **SEVERE VIOLENCE** (1.x.x) - Extreme physical harm, life-threatening attacks
2. **FELONY CRIME** (2.x.x) - Murder, kidnapping, serious criminal acts  
3. **SEXUAL VIOLENCE** (3.x.x) - Non-consensual sexual acts with clear force/distress
4. **TERRORISM** (4.x.x) - Terrorist attacks, threats, damage sites
5. **SUICIDE** (5.x.x) - Self-harm attempts, suicide preparations
6. **CSAM** (6.x.x) - Content involving minors (under 18) in harmful contexts
7. **PROHIBITED ITEM SALES** (7.x.x) - Illegal weapons, drugs, counterfeit goods
8. **INNOCENT** (8.0.0) - All other content, including legal adult content

### Evaluation Process:
1. **Step 1**: Evaluate against all 8 parent categories
2. **Step 2**: Refine to specific subcategory when confident (85%+ accuracy)

## 🔧 Command Line Options

### multi_model_classifier.py (Recommended)

```bash
python multi_model_classifier.py [OPTIONS]

Options:
  -d, --directory DIRECTORY     Directory containing images to process
  -u, --urls URL [URL ...]      List of image URLs to process  
  -o, --output OUTPUT          Output CSV file (default: multi_model_results.csv)
  -p, --pat-token TOKEN        Clarifai PAT token
  -h, --help                   Show help message
```

### image_classifier.py (Basic)

```bash  
python image_classifier.py [OPTIONS]

# Same options as above, outputs only main classification results
```

## 🔒 Security & Ethics

**⚠️ IMPORTANT**: This tool is designed for **defensive security purposes only**:

- ✅ **Allowed**: Content moderation, harmful content detection, safety analysis
- ❌ **Prohibited**: Creating, modifying, or improving malicious content
- 🛡️ **Purpose**: Identifying and preventing harmful material

### Data Privacy
- All processing is done via Clarifai's secure API endpoints
- No data is stored locally beyond the CSV results you generate
- Replace the default PAT token with your own for production use

## 📈 Performance & Limits

- **Supported Formats**: JPG, JPEG, PNG, GIF, BMP, TIFF, WEBP
- **Processing**: Sequential processing (not parallel)
- **Rate Limits**: Subject to Clarifai API rate limits
- **File Size**: Limited by Clarifai's file size restrictions

## 🐛 Troubleshooting

### Common Issues

1. **"Directory does not exist"**
   ```bash
   # Check path exists
   ls -la /path/to/images
   ```

2. **API Authentication Errors**  
   ```bash
   # Verify PAT token
   python multi_model_classifier.py -p "your_token" -u "test_url"
   ```

3. **URL Download Errors**
   - Some URLs may restrict downloads
   - Try uploading the image to a public hosting service
   - Use local files instead of URLs when possible

4. **Empty Results**
   - Check that images are valid formats
   - Verify network connectivity for API calls
   - Ensure PAT token has proper permissions

## 📊 Example Analysis Workflow

```bash
# 1. Process your image collection
python multi_model_classifier.py -d /path/to/images -o results/analysis_$(date +%Y%m%d).csv

# 2. Review results in spreadsheet software
# - Sort by main_confidence_score (low confidence = review needed)  
# - Filter by basic_moderation_suggestive > 0.5 (potentially suggestive)
# - Check detailed_moderation_top_concept for specific concerns

# 3. Process any flagged URLs for verification
python multi_model_classifier.py -u "flagged_url1" "flagged_url2" -o results/verification.csv
```

## 🤝 Contributing

This project is designed for content safety and moderation. When contributing:

1. Maintain focus on defensive security applications
2. Follow the ethical guidelines outlined above
3. Test changes with the provided sample images
4. Update documentation for any new features

## 📞 Support

For issues with:
- **Clarifai API**: Check [Clarifai Documentation](https://docs.clarifai.com/)
- **Classification Guidelines**: See `Initial_Prompt.txt` for detailed criteria
- **Development**: See `CLAUDE.md` for technical guidance

## 📄 License

This project is intended for content moderation and safety applications. Use responsibly and in accordance with applicable laws and regulations.

---

**Last Updated**: 2025-01-07  
**Version**: 1.0.0
