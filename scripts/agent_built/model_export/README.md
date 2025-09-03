# Container-based Model Export from Clarifai.com

This directory contains tools to export container-based models from Clarifai.com. The platform has moved from Triton-based models to container-based models, requiring new export approaches that handle Docker containers and model artifacts properly.

## 🚀 Quick Start

```bash
# Basic model export
python export_model.py https://clarifai.com/user/app/models/model

# Export with Docker image creation
python export_model.py https://clarifai.com/user/app/models/model --docker

# Export to custom directory with Docker image file
python export_model.py https://clarifai.com/user/app/models/model \
  --output ./my_exported_model \
  --docker \
  --export-image my_model.tar
```

## 📋 Requirements

- Python 3.8+
- Clarifai SDK (`pip install clarifai`)
- Docker (for image export functionality)
- Valid Clarifai Personal Access Token (PAT)

## 🔧 Installation

```bash
# Install Clarifai SDK
pip install clarifai

# Set up authentication (required)
export CLARIFAI_PAT="your_personal_access_token"
export CLARIFAI_USER_ID="your_user_id"
```

## 🎯 Usage

### Basic Export

Export a model to a local directory structure:

```bash
python export_model.py https://clarifai.com/clarifai/main/models/general-image-recognition
```

This creates an `exported_model/` directory with:
- `1/model.py` - Model implementation code
- `config.yaml` - Model configuration
- `requirements.txt` - Python dependencies
- `Dockerfile` - Container configuration
- `docker-compose.yml` - Local orchestration
- `start_runner.sh` - Startup script

### Docker Image Export

Create and export a Docker image:

```bash
python export_model.py https://clarifai.com/clarifai/main/models/general-image-recognition \
  --docker \
  --export-image my_model.tar
```

### Advanced Options

```bash
python export_model.py MODEL_URL [OPTIONS]

Options:
  --output, -o PATH          Output directory (default: ./exported_model)
  --docker, -d              Create Docker image
  --export-image, -x PATH    Export Docker image to file
  --compress-export          Compress exported image with gzip
  --pat TOKEN               Clarifai Personal Access Token
  --user-id ID              Clarifai User ID
  --help                    Show help message
```

## 📁 Output Structure

The exported model follows the standard Clarifai container model structure:

```
exported_model/
├── 1/
│   ├── model.py              # Main model implementation
│   └── checkpoints/          # Downloaded model weights (if available)
├── config.yaml               # Model configuration
├── requirements.txt          # Python dependencies
├── Dockerfile                # Container image recipe
├── docker-compose.yml        # Local development setup
└── start_runner.sh           # Runner startup script
```

## 🔐 Authentication

### Environment Variables (Recommended)

```bash
export CLARIFAI_PAT="your_personal_access_token"
export CLARIFAI_USER_ID="your_user_id"
```

### Command Line Options

```bash
python export_model.py MODEL_URL --pat your_token --user-id your_id
```

### Getting Your Credentials

1. **Personal Access Token (PAT)**: 
   - Go to [Clarifai Settings](https://clarifai.com/settings/security)
   - Create a new Personal Access Token

2. **User ID**: 
   - Found in your Clarifai profile URL: `https://clarifai.com/YOUR_USER_ID`

## 🐳 Working with Exported Models

### Local Development

```bash
cd exported_model/

# Test the model directly
python 1/model.py

# Or use Docker Compose
docker-compose up --build
```

### Docker Commands

```bash
# Build the image
docker build -t my-model .

# Run the container
docker run -p 8080:8080 -e CLARIFAI_PAT="$CLARIFAI_PAT" my-model

# Load exported image
docker load -i my_model.tar
```

### Using with Clarifai SDK

```python
from clarifai.client import Model

# Connect to your locally running model
model = Model(
    "https://clarifai.com/your-user/your-app/models/your-model",
    deployment_id="local-runner-deployment"
)

# Make predictions
result = model.predict(prompt="Hello world")
print(result)
```

## 🛠️ Customization

### Updating Model Code

1. Edit `1/model.py` to implement your model logic
2. Update `requirements.txt` with any additional dependencies
3. Modify `config.yaml` for model metadata
4. Rebuild Docker image: `docker-compose build`

### Example Model Implementation

```python
from clarifai.runners.models.model_runner import ModelRunner

class ModelClass(ModelRunner):
    def __init__(self):
        super().__init__()
        # Initialize your model here
        self.model = self.load_model()
    
    def load_model(self):
        # Load your trained model
        pass
    
    def predict(self, request):
        # Implement your prediction logic
        return {"prediction": "result"}
```

## 🔄 Container-based vs Triton Models

### Key Differences

| Aspect | Triton Models (Legacy) | Container Models (New) |
|--------|----------------------|------------------------|
| **Runtime** | NVIDIA Triton | Docker Containers |
| **Model Format** | TensorRT, ONNX, TorchScript | Python + Dependencies |
| **Deployment** | Triton Model Repository | Container Registry |
| **Scaling** | Triton Auto-scaling | Container Orchestration |
| **Customization** | Limited | Full Python Environment |

### Migration Benefits

- **Flexibility**: Full Python environment with custom dependencies
- **Portability**: Standard Docker containers work anywhere
- **Development**: Easier local development and testing
- **Integration**: Better integration with existing container workflows
- **Debugging**: Easier to debug and modify model behavior

## 🔍 Troubleshooting

### Common Issues

1. **Authentication Failed**
   ```
   ❌ Clarifai PAT not provided
   ```
   **Solution**: Set `CLARIFAI_PAT` environment variable or use `--pat` option

2. **Model Not Found**
   ```
   ❌ Failed to connect to model
   ```
   **Solution**: Verify model URL and ensure you have access to the model

3. **Docker Build Failed**
   ```
   ❌ Docker build failed
   ```
   **Solution**: Check Docker is installed and running, verify Dockerfile syntax

4. **Permission Denied**
   ```
   ❌ Permission denied accessing model
   ```
   **Solution**: Ensure your PAT has the required scopes and model access

### Debug Mode

For debugging, you can examine the exported files before Docker build:

```bash
python export_model.py MODEL_URL --output ./debug_export
# Examine files in ./debug_export/ before building
```

## 📚 Examples

### Export Public Model

```bash
python export_model.py https://clarifai.com/clarifai/main/models/general-image-recognition
```

### Export Private Model

```bash
export CLARIFAI_PAT="your_token"
export CLARIFAI_USER_ID="your_user_id"
python export_model.py https://clarifai.com/your-user/your-app/models/your-model
```

### Export with Custom Configuration

```bash
python export_model.py https://clarifai.com/user/app/models/model \
  --output ./custom_model \
  --docker \
  --export-image custom_model.tar.gz \
  --compress-export
```

## 🤝 Contributing

This script is part of the Clarifai Field Engineering repository. For issues or improvements:

1. Create an issue describing the problem or enhancement
2. Follow the existing code style and patterns
3. Test your changes with different model types
4. Update documentation as needed

## 📄 License

This project follows the repository's license terms.
