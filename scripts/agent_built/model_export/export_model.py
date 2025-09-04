#!/usr/bin/env python3
"""
Container-based Model Export Script for Clarifai

This script exports container-based models from Clarifai.com, supporting the new
architecture that replaced Triton-based models. It downloads all model components
and creates deployable packages.

Usage:
    python export_model.py [MODEL_URL] [options]

Requirements:
    - clarifai SDK installed
    - Docker (for image export functionality)
    - Valid Clarifai PAT and authentication
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import gzip
from pathlib import Path
from urllib.parse import urlparse

try:
    from clarifai.client.model import Model
    from clarifai.client.user import User
    import clarifai
except ImportError:
    print("❌ Clarifai SDK not found. Install with: pip install clarifai")
    sys.exit(1)


class ModelExporter:
    def __init__(self, model_url, output_dir=None, export_docker=False, 
                 export_image_path=None, compress_export=False, 
                 pat=None, user_id=None):
        self.model_url = model_url
        self.output_dir = Path(output_dir) if output_dir else Path("./exported_model")
        self.export_docker = export_docker
        self.export_image_path = export_image_path
        self.compress_export = compress_export
        self.pat = pat
        self.user_id = user_id
        
        # Parse model URL to extract components
        self._parse_model_url()
        
        # Set up authentication
        self._setup_auth()
        
        # Initialize Clarifai model client
        self.model = None
        
    def _parse_model_url(self):
        """Parse Clarifai model URL to extract user, app, and model IDs."""
        print(f"🔍 Parsing model URL: {self.model_url}")
        
        # Handle different URL formats
        if self.model_url.startswith("https://clarifai.com/"):
            # Format: https://clarifai.com/user/app/models/model
            parts = self.model_url.replace("https://clarifai.com/", "").split("/")
            if len(parts) >= 4 and parts[2] == "models":
                self.model_user_id = parts[0]
                self.model_app_id = parts[1]
                self.model_id = parts[3]
            else:
                raise ValueError(f"Invalid model URL format: {self.model_url}")
        else:
            # Assume it's just a model ID, require user to specify user/app
            raise ValueError("Please provide full Clarifai model URL: https://clarifai.com/user/app/models/model")
        
        print(f"✅ Parsed - User: {self.model_user_id}, App: {self.model_app_id}, Model: {self.model_id}")
    
    def _setup_auth(self):
        """Set up Clarifai authentication."""
        # Check environment variables first
        if not self.pat:
            self.pat = os.getenv('CLARIFAI_PAT')
        if not self.user_id:
            self.user_id = os.getenv('CLARIFAI_USER_ID')
        
        if not self.pat:
            raise ValueError("Clarifai PAT not provided. Set CLARIFAI_PAT environment variable or use --pat option")
        
        print(f"🔐 Authentication configured for user: {self.user_id or 'from PAT'}")
    
    def _init_model_client(self):
        """Initialize the Clarifai model client."""
        try:
            print(f"🤖 Connecting to model: {self.model_url}")
            self.model = Model(
                url=self.model_url,
                pat=self.pat,
                user_id=self.user_id
            )
            
            # Test connection by getting model info
            model_info = self.model.get_info()
            print(f"✅ Connected to model: {model_info.id}")
            print(f"   Description: {model_info.description or 'No description'}")
            print(f"   Model Type: {model_info.model_type_id}")
            
            return True
        except Exception as e:
            print(f"❌ Failed to connect to model: {str(e)}")
            return False
    
    def _download_model_artifacts(self):
        """Download model artifacts using Clarifai CLI."""
        print("📥 Downloading model artifacts...")
        
        # Create temporary directory for download
        temp_dir = Path(tempfile.mkdtemp(prefix="clarifai_export_"))
        
        try:
            # Create a basic config.yaml to use with download-checkpoints
            config_content = f"""
model:
  id: "{self.model_id}"
  user_id: "{self.model_user_id}"
  app_id: "{self.model_app_id}"
"""
            config_path = temp_dir / "config.yaml"
            config_path.write_text(config_content)
            
            # Use CLI to download checkpoints and model files
            download_cmd = [
                sys.executable, "-m", "clarifai.cli", "model", "download-checkpoints",
                str(temp_dir), "--out_path", str(temp_dir / "1" / "checkpoints")
            ]
            
            print(f"🔧 Running: {' '.join(download_cmd)}")
            
            # Set environment for authentication
            env = os.environ.copy()
            env['CLARIFAI_PAT'] = self.pat
            if self.user_id:
                env['CLARIFAI_USER_ID'] = self.user_id
            
            result = subprocess.run(download_cmd, capture_output=True, text=True, env=env)
            
            if result.returncode != 0:
                print(f"⚠️  Download command failed, but continuing: {result.stderr}")
                # Don't fail here as some models might not have downloadable checkpoints
            
            return temp_dir
            
        except Exception as e:
            print(f"❌ Failed to download artifacts: {str(e)}")
            shutil.rmtree(temp_dir, ignore_errors=True)
            return None
    
    def _create_model_structure(self, temp_dir):
        """Create the standard model directory structure."""
        print("📁 Creating model directory structure...")
        
        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create standard structure
        model_dir = self.output_dir / "1"
        model_dir.mkdir(exist_ok=True)
        
        # Create a basic model.py if not exists
        model_py_path = model_dir / "model.py"
        if not model_py_path.exists():
            model_py_content = f'''"""
Exported model from Clarifai: {self.model_url}

This is a container-based model exported from Clarifai.com.
Original model: {self.model_user_id}/{self.model_app_id}/{self.model_id}
"""

from clarifai.runners.models.model_runner import ModelRunner


class ModelClass(ModelRunner):
    """Exported model class from Clarifai."""
    
    def __init__(self):
        super().__init__()
        # TODO: Initialize your model here
        # This is a template - you may need to add actual model loading code
        print(f"Loading model: {self.model_id}")
    
    def load_model(self):
        """Load the model."""
        # TODO: Implement model loading logic
        pass
    
    def predict(self, request):
        """Make predictions."""
        # TODO: Implement prediction logic
        return {{"error": "Model implementation needed"}}
'''
            model_py_path.write_text(model_py_content)
            print(f"📝 Created template model.py")
        
        # Copy any downloaded artifacts
        if temp_dir and (temp_dir / "1").exists():
            print("📋 Copying downloaded artifacts...")
            for item in (temp_dir / "1").iterdir():
                if item.is_file():
                    shutil.copy2(item, model_dir)
                elif item.is_dir():
                    shutil.copytree(item, model_dir / item.name, dirs_exist_ok=True)
        
        # Create config.yaml
        config_path = self.output_dir / "config.yaml"
        config_content = f"""
model:
  id: "{self.model_id}"
  user_id: "{self.model_user_id}"
  app_id: "{self.model_app_id}"
  model_type_id: "text-to-text"  # Update as needed
  
  # Model metadata exported from Clarifai
  source_url: "{self.model_url}"
  export_timestamp: "{Path(__file__).stat().st_mtime if Path(__file__).exists() else 'unknown'}"
"""
        config_path.write_text(config_content)
        print(f"📝 Created config.yaml")
        
        # Create requirements.txt
        requirements_path = self.output_dir / "requirements.txt"
        if not requirements_path.exists():
            requirements_content = """clarifai>=11.0.0
numpy>=1.20.0
pydantic>=2.0.0
"""
            requirements_path.write_text(requirements_content)
            print(f"📝 Created requirements.txt")
        
        # Copy template files from existing examples if available
        self._copy_template_files()
        
        print(f"✅ Model structure created in: {self.output_dir}")
    
    def _copy_template_files(self):
        """Copy template files from existing Dockerized runner example."""
        # Look for the Dockerized_Runner example
        repo_root = Path(__file__).parent.parent.parent
        dockerized_runner = repo_root / "CustomRunners" / "Dockerized_Runner"
        
        if dockerized_runner.exists():
            print("📋 Copying template files from Dockerized_Runner...")
            
            # Copy useful template files
            template_files = ["Dockerfile", "docker-compose.yml", "start_runner.sh"]
            for template_file in template_files:
                src = dockerized_runner / template_file
                if src.exists():
                    dst = self.output_dir / template_file
                    shutil.copy2(src, dst)
                    print(f"   Copied {template_file}")
    
    def _create_docker_image(self):
        """Create Docker image from the exported model."""
        if not self.export_docker:
            return True
        
        print("🐳 Creating Docker image...")
        
        # Check if Docker is available
        try:
            subprocess.run(["docker", "--version"], check=True, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("❌ Docker not found. Install Docker to use --docker option")
            return False
        
        # Generate Dockerfile if not exists
        dockerfile_path = self.output_dir / "Dockerfile"
        if not dockerfile_path.exists():
            dockerfile_content = f'''FROM public.ecr.aws/clarifai-models/torch:2.4.1-py3.12-cu124-42938da8e33b0f37ee7db16b83631da94c2348b9

USER root
RUN groupadd -g 999 python && useradd -r -u 999 -g python python
RUN mkdir -p /home/nonroot/main && chown python:python /home/nonroot/main

USER python

# Copy model files
COPY --chown=999:999 . /home/nonroot/main/

WORKDIR /home/nonroot/main

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Set environment
ENV PYTHONPATH=${{PYTHONPATH}}:/home/nonroot/main:/home/nonroot/main/1
ENV CLARIFAI_PAT=${{CLARIFAI_PAT}}
ENV CLARIFAI_USER_ID=${{CLARIFAI_USER_ID}}

# Run the model
ENTRYPOINT ["python", "-m", "clarifai.runners.server"]
CMD ["--model_path", "/home/nonroot/main"]
'''
            dockerfile_path.write_text(dockerfile_content)
            print("📝 Generated Dockerfile")
        
        # Build Docker image
        image_name = f"clarifai-model-{self.model_id.lower()}"
        build_cmd = [
            "docker", "build", "-t", image_name, str(self.output_dir)
        ]
        
        print(f"🔧 Building Docker image: {image_name}")
        try:
            result = subprocess.run(build_cmd, check=True, capture_output=True, text=True)
            print("✅ Docker image built successfully!")
            
            # Export image if requested
            if self.export_image_path:
                return self._export_docker_image(image_name)
            
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Docker build failed: {e.stderr}")
            return False
    
    def _export_docker_image(self, image_name):
        """Export Docker image to file."""
        print(f"📦 Exporting Docker image to: {self.export_image_path}")
        
        try:
            if self.compress_export:
                # Export with compression using gzip
                import gzip
                temp_file = str(self.export_image_path) + ".tmp"
                export_cmd = ["docker", "save", "-o", temp_file, image_name]
                subprocess.run(export_cmd, check=True, capture_output=True, text=True)
                
                # Compress the file
                with open(temp_file, 'rb') as f_in:
                    with gzip.open(self.export_image_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                
                # Clean up temporary file
                os.remove(temp_file)
            else:
                # Export uncompressed
                export_cmd = ["docker", "save", "-o", str(self.export_image_path), image_name]
                subprocess.run(export_cmd, check=True, capture_output=True, text=True)
            
            # Check file size
            file_size = Path(self.export_image_path).stat().st_size / (1024 * 1024)  # MB
            print(f"✅ Image exported successfully! File size: {file_size:.1f}MB")
            
            # Print load instructions
            print(f"\n📋 To load this image on another machine:")
            if self.compress_export:
                print(f"   gunzip -c {self.export_image_path} | docker load")
            else:
                print(f"   docker load -i {self.export_image_path}")
            
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to export image: {e.stderr}")
            return False
    
    def export_model(self):
        """Main method to export the model."""
        try:
            print(f"🚀 Starting model export for: {self.model_url}")
            print(f"📁 Output directory: {self.output_dir}")
            
            # Initialize model client
            if not self._init_model_client():
                return False
            
            # Download model artifacts
            temp_dir = self._download_model_artifacts()
            
            # Create model structure
            self._create_model_structure(temp_dir)
            
            # Create Docker image if requested
            if not self._create_docker_image():
                return False
            
            # Cleanup temp directory
            if temp_dir:
                shutil.rmtree(temp_dir, ignore_errors=True)
            
            print(f"\n✅ Model export completed successfully!")
            print(f"📁 Model files: {self.output_dir}")
            
            # Print next steps
            print(f"\n📋 Next steps:")
            print(f"   1. Review and update the model.py file with your actual model logic")
            print(f"   2. Update requirements.txt with your model's dependencies")
            print(f"   3. Test the model locally: cd {self.output_dir} && python 1/model.py")
            if self.export_docker:
                print(f"   4. Run with Docker: docker run -p 8080:8080 clarifai-model-{self.model_id.lower()}")
            
            return True
            
        except Exception as e:
            print(f"❌ Export failed: {str(e)}")
            return False


def main():
    parser = argparse.ArgumentParser(
        description="Export container-based models from Clarifai.com",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic export
  python export_model.py https://clarifai.com/user/app/models/model

  # Export with Docker image
  python export_model.py https://clarifai.com/user/app/models/model --docker

  # Export with custom output directory and Docker image file
  python export_model.py https://clarifai.com/user/app/models/model \\
    --output ./my_model \\
    --docker \\
    --export-image my_model.tar

  # Export with authentication
  python export_model.py https://clarifai.com/user/app/models/model \\
    --pat your_pat_token \\
    --user-id your_user_id

Environment Variables:
  CLARIFAI_PAT      - Personal Access Token for authentication
  CLARIFAI_USER_ID  - Your Clarifai user ID

The exported model will include:
  - Model code (1/model.py)
  - Configuration (config.yaml)
  - Dependencies (requirements.txt)
  - Dockerfile for containerization
  - Docker Compose setup for local testing
  - Startup scripts
        """
    )
    
    parser.add_argument(
        "model_url",
        help="Clarifai model URL (https://clarifai.com/user/app/models/model)"
    )
    
    parser.add_argument(
        "--output", "-o",
        help="Output directory for exported model (default: ./exported_model)"
    )
    
    parser.add_argument(
        "--docker", "-d",
        action="store_true",
        help="Create Docker image for the exported model"
    )
    
    parser.add_argument(
        "--export-image", "-x",
        help="Export Docker image to file (e.g., model.tar)"
    )
    
    parser.add_argument(
        "--compress-export",
        action="store_true",
        help="Compress exported Docker image with gzip"
    )
    
    parser.add_argument(
        "--pat",
        help="Clarifai Personal Access Token (or set CLARIFAI_PAT env var)"
    )
    
    parser.add_argument(
        "--user-id",
        help="Clarifai User ID (or set CLARIFAI_USER_ID env var)"
    )
    
    args = parser.parse_args()
    
    # Validate Docker requirements
    if args.docker or args.export_image:
        try:
            subprocess.run(["docker", "--version"], check=True, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("❌ Docker is required for --docker and --export-image options")
            print("   Install Docker: https://docs.docker.com/get-docker/")
            sys.exit(1)
    
    # Create exporter and run
    exporter = ModelExporter(
        model_url=args.model_url,
        output_dir=args.output,
        export_docker=args.docker,
        export_image_path=args.export_image,
        compress_export=args.compress_export,
        pat=args.pat,
        user_id=args.user_id
    )
    
    success = exporter.export_model()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()