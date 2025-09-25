# Clarifai Batch Image Upload Tool

A robust Python tool for batch uploading images from CSV files to Clarifai with automatic concept annotation. Features intelligent batch processing, concept ID sanitization, and comprehensive error handling.

## 🚀 Features

- **Batch Processing**: Configurable batch sizes for optimal performance
- **CSV Input**: Simple CSV format with image URLs and concept labels
- **Concept Sanitization**: Automatically converts concept names to valid Clarifai IDs
- **Error Handling**: Robust error recovery and detailed logging
- **Environment Configuration**: Secure credential management via `.env` file
- **Progress Tracking**: Real-time batch progress and upload status
- **Modern API**: Uses latest Clarifai Python SDK and gRPC APIs

## 📋 Requirements

- Python 3.12+
- Conda environment (recommended)
- Clarifai account with API access

## 🔧 Installation

1. **Clone or download the project files**

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables:**
   ```bash
   cp .env-template .env
   # Edit .env with your Clarifai credentials
   ```

## ⚙️ Configuration

### Environment Variables (`.env` file)

```bash
# Clarifai Configuration
CLARIFAI_USER_ID=your-user-id
CLARIFAI_APP_ID=your-app-id
CLARIFAI_PAT=your-personal-access-token

# Batch processing configuration
BATCH_SIZE=32  # Recommended: 8-32
```

### Batch Size Guidelines

| Batch Size | Use Case | Trade-offs |
|------------|----------|------------|
| 8-16 | Testing, debugging | More API calls, better error recovery |
| 16-32 | Production (recommended) | Balanced performance and reliability |
| 32+ | High-volume processing | Fewer API calls, longer processing times |

### 🔑 How to Get Your Clarifai Personal Access Token (PAT)

A Personal Access Token (PAT) is required to authenticate with the Clarifai API. Follow these steps to create one:

#### Step 1: Log in to Clarifai
1. Go to [Clarifai Login](https://clarifai.com/login)
2. Sign in with your account credentials

#### Step 2: Navigate to Security Settings
1. In the left sidebar, click on **Settings**
2. Select **Security** from the dropdown menu

#### Step 3: Create a New PAT
1. On the Security page, click the **"Create Personal Access Token"** button
2. In the popup form:
   - **Description**: Enter a descriptive name (e.g., "Batch Upload Tool")
   - **Scopes**: Select the permissions you need (recommended: full access for upload operations)
3. Click **"Create Personal Access Token"**

#### Step 4: Copy Your Token
1. Your new PAT will appear in the Personal Access Token section
2. **Important**: Copy the token immediately as you won't be able to see it again
3. Store it securely in your `.env` file

#### 📋 Example PAT Configuration
```bash
# Your Personal Access Token from Clarifai Security settings
CLARIFAI_PAT=1234567890abcdef1234567890abcdef12345678
```

> **🔒 Security Notes:**
> - PATs do not expire but should be kept secure
> - Never share your PAT or commit it to version control
> - If compromised, delete the old PAT and create a new one
> - Use environment variables (`.env` file) to store your PAT securely

#### Getting User ID and App ID
- **User ID**: Found in your Clarifai profile URL (`https://clarifai.com/users/YOUR-USER-ID`)
- **App ID**: Found in your application settings or URL (`https://clarifai.com/users/YOUR-USER-ID/apps/YOUR-APP-ID`)

For more detailed information, visit the [official Clarifai documentation](https://docs.clarifai.com/control/authentication/pat).

## 📊 CSV Format

Your CSV file should have the following structure:

```csv
ID,URL,description
1,https://example.com/image1.jpg,King Bed
2,https://example.com/image2.jpg,Queen Size
3,https://example.com/image3.jpg,Twin Bed
```

**Column Mapping:**
- Column 1: ID (any unique identifier)
- Column 2: Image URL (must be publicly accessible)
- Column 3: Concept/Label (will be sanitized for Clarifai)

## 🎯 Usage

### Basic Usage
```bash
python upload-csv inputs.csv
```

### Specify Custom CSV File
```bash
python upload-csv my-custom-file.csv
```

### Using Conda Environment
```bash
conda run -n your-env-name python upload-csv inputs.csv
```

## 🔄 Concept ID Sanitization

The tool automatically sanitizes concept names to meet Clarifai requirements:

| Original | Sanitized | Rules Applied |
|----------|-----------|---------------|
| `Twin Bed` | `twin-bed` | Lowercase, spaces → hyphens |
| `KING SIZE` | `king-size` | Lowercase, spaces → hyphens |
| `Queen_Bed_XL` | `queen-bed-xl` | Lowercase, underscores → hyphens |

**Sanitization Rules:**
- Convert to lowercase
- Replace spaces with hyphens
- Replace underscores with hyphens  
- Remove special characters
- Clean up multiple consecutive hyphens
- Remove leading/trailing hyphens

## 📈 Example Output

```
=== DEBUG: Environment Variables ===
USER_ID: roomplanner-org
APP_ID: furniture-bed
CLARIFAI_PAT: ******************************** (masked)
CSV_FILE_PATH: inputs.csv
BATCH_SIZE: 32

Starting upload to application: furniture-bed
Reading data from 'inputs.csv'...
Row 1: Transformed concept 'Twin Bed' → 'twin-bed'
Found 1000 valid entries in CSV file.
Processing in 32 batch(es) of 32 items each.

--- Processing Batch 1/32 (32 items) ---
Batch 1: Downloading image from: https://example.com/image1.jpg
Batch 1: Successfully downloaded 32 images.
Batch 1: Uploaded image 1/32: bed_image_1758820775_0_0
Batch 1: Successfully uploaded 32 images.
Batch 1: Successfully created annotations for 32 inputs.
Batch 1: Upload complete: 32 inputs with annotations.

All uploads completed successfully!
```

## 📁 Project Structure

```
clarifai-roomplanner/
├── upload-csv              # Main upload script
├── requirements.txt        # Python dependencies
├── .env-template          # Environment template
├── .env                   # Your configuration (keep private)
├── inputs.csv             # Sample input file
├── inputs-complete.csv    # Large dataset example
└── README.md              # This file
```

## 🛠️ Dependencies

```
clarifai>=10.0.0           # Modern Clarifai Python client
clarifai-grpc>=10.0.0      # gRPC API for annotations
python-dotenv>=0.19.0      # Environment variable management
requests>=2.25.0           # HTTP client for image downloads
```

## 🔍 Troubleshooting

### Common Issues

**1. Authentication Error**
```
Error: CLARIFAI_PAT environment variable not set.
```
**Solution:** Check your `.env` file and ensure `CLARIFAI_PAT` is set correctly.

**2. App Not Found**
```
Exception: code: CONN_DOES_NOT_EXIST
```
**Solution:** Verify `CLARIFAI_USER_ID` and `CLARIFAI_APP_ID` in your `.env` file.

**3. Invalid Concept IDs**
```
CONCEPTS_INVALID_REQUEST: 'id' must consist of alphanumeric strings...
```
**Solution:** This is automatically handled by concept sanitization (should not occur).

**4. Image Download Failures**
```
Warning: Could not download image from URL. Error: 404. Skipping row X.
```
**Solution:** Check that image URLs are publicly accessible and valid.

### Debug Mode

The script includes comprehensive debug output showing:
- Environment variable status
- CSV parsing progress
- Concept transformations
- Batch processing status
- Upload confirmations

## 🔒 Security

- **Never commit `.env` files** to version control
- Use the `.env-template` for sharing configuration structure
- Keep your `CLARIFAI_PAT` secure and rotate periodically
- Ensure image URLs are from trusted sources

## 📊 Performance Tips

1. **Optimal Batch Size**: Use 16-32 for most cases
2. **Network Considerations**: Larger batches work better with stable connections
3. **Memory Usage**: Script downloads images in batches to manage memory
4. **Error Recovery**: Smaller batches provide better error isolation

## 🤝 Contributing

Feel free to submit issues and enhancement requests!

## 📄 License

This project is provided as-is for educational and development purposes.

---

## 🆘 Support

If you encounter issues:

1. Check the debug output for specific error messages
2. Verify your `.env` configuration
3. Ensure your CSV format matches the expected structure
4. Test with a small batch first (`BATCH_SIZE=5`)

**Happy uploading!** 🎉