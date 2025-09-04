#!/usr/bin/env python3
"""
Module Builder Script for Clarifai Streamlit Apps

This script builds a Docker image for a Streamlit module based on the same process
used by the Clarifai Module Manager, but for local development without GitHub.

Usage:
    python build_module.py /path/to/your/streamlit/app [options]

Requirements:
    - Docker installed and running
    - app.py file in the target directory
    - requirements.txt file in the target directory
"""

import argparse
import gzip
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


class ModuleBuilder:
    def __init__(self, app_path, image_name=None, port=8501, no_build=False, no_run=False, debug=False, env_vars=None, secrets=None, export_path=None, compress_export=False):
        self.app_path = Path(app_path).resolve()
        self.image_name = image_name or f"clarifai-module-{self.app_path.name.lower()}"
        self.port = port
        self.no_build = no_build
        self.no_run = no_run
        self.debug = debug
        self.env_vars = env_vars or {}
        self.secrets = secrets or {}
        self.export_path = export_path
        self.compress_export = compress_export
        
    def validate_app_directory(self):
        """Validate that the app directory contains required files."""
        print(f"🔍 Validating app directory: {self.app_path}")
        
        if not self.app_path.exists():
            raise FileNotFoundError(f"App directory does not exist: {self.app_path}")
        
        if not self.app_path.is_dir():
            raise NotADirectoryError(f"Path is not a directory: {self.app_path}")
        
        # Check for required files
        app_py = self.app_path / "app.py"
        requirements_txt = self.app_path / "requirements.txt"
        
        if not app_py.exists():
            raise FileNotFoundError(
                f"app.py not found in {self.app_path}. "
                "Streamlit modules must have an app.py entrypoint."
            )
        
        if not requirements_txt.exists():
            raise FileNotFoundError(
                f"requirements.txt not found in {self.app_path}. "
                "Please create a requirements.txt file with your Python dependencies."
            )
        
        print("✅ Required files found: app.py, requirements.txt")
        
        # Check for optional files
        optional_files = [".streamlit/secrets.toml", "README.md"]
        found_optional = []
        for file_path in optional_files:
            if (self.app_path / file_path).exists():
                found_optional.append(file_path)
        
        if found_optional:
            print(f"📄 Optional files found: {', '.join(found_optional)}")
    
    def generate_secrets_toml(self):
        """Generate Streamlit secrets.toml content from provided secrets."""
        if not self.secrets:
            return ""
        
        toml_content = []
        for key, value in self.secrets.items():
            toml_content.append(f'{key} = "{value}"')
        
        return '\n'.join(toml_content)
    
    def generate_dockerfile(self):
        """Generate the Dockerfile content based on Clarifai's template."""
        dockerfile_content = """FROM public.ecr.aws/docker/library/python:3.12-slim

USER root
RUN groupadd -g 999 python && \\
  useradd -r -u 999 -g python python

RUN mkdir -p /streamlit/app && chown python:python /streamlit/app
# Make sure we have a normal /home/python in case libraries need it.
RUN mkdir -p /home/python && chown python:python /home/python

# Install system dependencies including build tools for Python packages like Pillow
RUN apt update && apt install -y \\
    git \\
    curl \\
    libgl1 \\
    libgl1-mesa-dev \\
    libglib2.0-0 \\
    zlib1g-dev \\
    libjpeg-dev \\
    libpng-dev \\
    libfreetype6-dev \\
    liblcms2-dev \\
    libopenjp2-7-dev \\
    libtiff5-dev \\
    libwebp-dev \\
    libffi-dev \\
    gcc \\
    g++ \\
    && rm -rf /var/lib/apt/lists/*

USER python
ENV HOME=/home/python
# uv gets installed to $HOME/.local/bin and the virtualenv to $HOME/.venv
ENV PATH="$HOME/.local/bin:$HOME/.venv/bin:$PATH"
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Copy the app directory
COPY --chown=999:999 . /streamlit/app/

WORKDIR /streamlit/app

# Setup venv in the app directory and install dependencies
RUN uv venv .venv && uv pip install --no-cache-dir -r requirements.txt

# Set Streamlit configuration
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
ENV STREAMLIT_BROWSER_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_PORT=8501

EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \\
  CMD curl -f http://localhost:8501/healthz || exit 1

# Use the virtual environment's Python to run streamlit (venv is in current working directory)
ENTRYPOINT ["/streamlit/app/.venv/bin/python", "-m", "streamlit", "run", "app.py", "--browser.gatherUsageStats=False", "--server.address=0.0.0.0"]
"""
        return dockerfile_content
    
    def create_dockerignore(self, temp_dir):
        """Create a .dockerignore file to exclude unnecessary files."""
        dockerignore_content = """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
.venv/
.env

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Git
.git/
.gitignore

# Docker
Dockerfile*
.dockerignore

# Logs
*.log

# Temporary files
*.tmp
*.temp
"""
        dockerignore_path = temp_dir / ".dockerignore"
        dockerignore_path.write_text(dockerignore_content)
        print(f"📝 Created .dockerignore")
    
    def build_image(self):
        """Build the Docker image."""
        print(f"🏗️  Building Docker image: {self.image_name}")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Copy app directory to temp location
            print("📂 Copying app files to build context...")
            shutil.copytree(self.app_path, temp_path / "app")
            
            # Generate and write secrets.toml if secrets are provided
            secrets_content = self.generate_secrets_toml()
            if secrets_content:
                streamlit_dir = temp_path / "app" / ".streamlit"
                streamlit_dir.mkdir(exist_ok=True)
                secrets_path = streamlit_dir / "secrets.toml"
                secrets_path.write_text(secrets_content)
                print("🔐 Generated .streamlit/secrets.toml")
            
            # Generate Dockerfile
            dockerfile_content = self.generate_dockerfile()
            dockerfile_path = temp_path / "app" / "Dockerfile"
            dockerfile_path.write_text(dockerfile_content)
            print("📝 Generated Dockerfile")
            
            # Create .dockerignore
            self.create_dockerignore(temp_path / "app")
            
            if self.no_build:
                print(f"📁 Build files prepared in temporary directory")
                print(f"   Dockerfile: {dockerfile_path}")
                print("   Run with --no-build=false to build the image")
                return
            
            # Build Docker image
            build_cmd = [
                "docker", "build",
                "-t", self.image_name,
                "-f", str(dockerfile_path),
                str(temp_path / "app")
            ]
            
            print(f"🔧 Running: {' '.join(build_cmd)}")
            try:
                result = subprocess.run(build_cmd, check=True, capture_output=True, text=True)
                print("✅ Docker image built successfully!")
                return True
            except subprocess.CalledProcessError as e:
                print(f"❌ Docker build failed!")
                print(f"Error: {e.stderr}")
                return False
    
    def run_container(self):
        """Run the built Docker image."""
        if self.no_run:
            print("🚀 Skipping container run (--no-run specified)")
            return
        
        print(f"🚀 Running container from image: {self.image_name}")
        
        # Check if image exists
        check_cmd = ["docker", "images", "-q", self.image_name]
        result = subprocess.run(check_cmd, capture_output=True, text=True)
        
        if not result.stdout.strip():
            print(f"❌ Image {self.image_name} not found. Build it first.")
            return False
        
        # Check if port is already in use
        port_check = ["docker", "ps", "--filter", f"publish={self.port}", "--format", "table {{.Names}}"]
        port_result = subprocess.run(port_check, capture_output=True, text=True)
        if len(port_result.stdout.strip().split('\n')) > 1:  # More than just header
            print(f"⚠️  Port {self.port} is already in use by another container")
            print("   Try using a different port with --port option")
            return False
        
        # Check if container name already exists
        name_check = ["docker", "ps", "-a", "--filter", f"name={self.image_name}-container", "--format", "table {{.Names}}"]
        name_result = subprocess.run(name_check, capture_output=True, text=True)
        if len(name_result.stdout.strip().split('\n')) > 1:  # More than just header
            print(f"🧹 Removing existing container: {self.image_name}-container")
            remove_cmd = ["docker", "rm", "-f", f"{self.image_name}-container"]
            subprocess.run(remove_cmd, capture_output=True)
        
        run_cmd = [
            "docker", "run",
            "--rm",
            "-p", f"{self.port}:8501",
            "--name", f"{self.image_name}-container"
        ]
        
        # Add environment variables
        for key, value in self.env_vars.items():
            run_cmd.extend(["-e", f"{key}={value}"])
        
        # Add debug options if debug mode is enabled
        if self.debug:
            run_cmd.extend(["-it", "--entrypoint", "/bin/bash"])
            print("🐛 Debug mode: Starting container with bash shell")
        
        run_cmd.append(self.image_name)
        
        print(f"🔧 Running: {' '.join(run_cmd)}")
        print(f"🌐 Access your app at: http://localhost:{self.port}")
        print("🛑 Press Ctrl+C to stop the container")
        
        try:
            if self.debug:
                # In debug mode, run interactively
                subprocess.run(run_cmd, check=True)
            else:
                # In normal mode, capture output for better error handling
                process = subprocess.run(run_cmd, check=True, capture_output=True, text=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to run container!")
            print(f"Exit code: {e.returncode}")
            if e.stdout:
                print(f"STDOUT:\n{e.stdout}")
            if e.stderr:
                print(f"STDERR:\n{e.stderr}")
            
            # Try to get container logs if container was created
            try:
                logs_cmd = ["docker", "logs", f"{self.image_name}-container"]
                logs_result = subprocess.run(logs_cmd, capture_output=True, text=True)
                if logs_result.stdout or logs_result.stderr:
                    print(f"\n📋 Container logs:")
                    if logs_result.stdout:
                        print(f"STDOUT:\n{logs_result.stdout}")
                    if logs_result.stderr:
                        print(f"STDERR:\n{logs_result.stderr}")
            except:
                pass
            
            return False
        except KeyboardInterrupt:
            print("\n🛑 Container stopped by user")
            return True
    
    def export_image(self):
        """Export the Docker image to a file."""
        if not self.export_path:
            return True
        
        print(f"📦 Exporting Docker image to: {self.export_path}")
        
        # Check if image exists
        check_cmd = ["docker", "images", "-q", self.image_name]
        result = subprocess.run(check_cmd, capture_output=True, text=True)
        
        if not result.stdout.strip():
            print(f"❌ Image {self.image_name} not found. Build it first.")
            return False
        
        try:
            if self.compress_export:
                # Export with compression using Python's gzip
                print("🗜️  Compressing during export...")
                
                # First export to temporary uncompressed file
                temp_file = str(self.export_path) + ".tmp"
                export_cmd = ["docker", "save", "-o", temp_file, self.image_name]
                subprocess.run(export_cmd, check=True, capture_output=True, text=True)
                
                # Then compress it with Python's gzip
                with open(temp_file, 'rb') as f_in:
                    with gzip.open(self.export_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                
                # Clean up temporary file
                os.remove(temp_file)
            else:
                # Export uncompressed
                export_cmd = ["docker", "save", "-o", str(self.export_path), self.image_name]
                subprocess.run(export_cmd, check=True, capture_output=True, text=True)
            
            # Check file size
            file_size = Path(self.export_path).stat().st_size / (1024 * 1024)  # MB
            print(f"✅ Image exported successfully! File size: {file_size:.1f}MB")
            
            # Print load instructions
            print(f"\n📋 To load this image on another machine:")
            if self.compress_export:
                print(f"   gunzip -c {self.export_path} | docker load")
            else:
                print(f"   docker load -i {self.export_path}")
            
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to export image!")
            print(f"Error: {e.stderr if e.stderr else str(e)}")
            return False
    
    def build_and_run(self):
        """Main method to validate, build, and run the module."""
        try:
            # Validate app directory
            self.validate_app_directory()
            
            # Build Docker image
            if self.build_image() and not self.no_build:
                print(f"✅ Successfully built image: {self.image_name}")
                
                # Export image if requested
                if not self.export_image():
                    return
                
                # Run container
                self.run_container()
            
        except Exception as e:
            print(f"❌ Error: {e}")
            sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Build and run Clarifai Streamlit modules locally",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Build and run a module
  python build_module.py /path/to/my/streamlit/app
  
  # Build with Clarifai credentials
  python build_module.py /path/to/app --clarifai-user-id your_user_id --clarifai-pat your_token
  
  # Build with custom secrets and environment variables
  python build_module.py /path/to/app -s API_KEY=secret123 -e DEBUG=true
  
  # Build with custom image name and port
  python build_module.py /path/to/app --image my-module --port 8502
  
  # Build and export image
  python build_module.py /path/to/app --export my-module.tar
  
  # Build and export compressed image
  python build_module.py /path/to/app --export my-module.tar.gz --compress-export
  
  # Only generate Dockerfile (don't build)
  python build_module.py /path/to/app --no-build
  
  # Debug mode - start container with bash shell
  python build_module.py /path/to/app --debug

Required files in app directory:
  - app.py (Streamlit entrypoint)
  - requirements.txt (Python dependencies)

Optional files:
  - .streamlit/secrets.toml (Streamlit secrets - will be merged with --secret options)
  - README.md (Documentation)
  - assets/ (Static files)

Environment Variables vs Secrets:
  - Environment variables (-e/--env): Available to the container process
  - Streamlit secrets (-s/--secret): Available via st.secrets in your Streamlit app
        """
    )
    
    parser.add_argument(
        "app_path",
        help="Path to the Streamlit app directory"
    )
    
    parser.add_argument(
        "--image", "-i",
        help="Docker image name (default: clarifai-module-{dirname})"
    )
    
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=8501,
        help="Port to run the container on (default: 8501)"
    )
    
    parser.add_argument(
        "--no-build",
        action="store_true",
        help="Only generate Dockerfile, don't build image"
    )
    
    parser.add_argument(
        "--no-run",
        action="store_true",
        help="Build image but don't run container"
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Start container in debug mode with bash shell"
    )
    
    parser.add_argument(
        "--env", "-e",
        action="append",
        default=[],
        help="Environment variables in KEY=VALUE format (can be used multiple times)"
    )
    
    parser.add_argument(
        "--secret", "-s",
        action="append", 
        default=[],
        help="Streamlit secrets in KEY=VALUE format (can be used multiple times)"
    )
    
    parser.add_argument(
        "--clarifai-user-id",
        help="Clarifai User ID (convenience for --secret CLARIFAI_USER_ID=value)"
    )
    
    parser.add_argument(
        "--clarifai-pat",
        help="Clarifai Personal Access Token (convenience for --secret CLARIFAI_PAT=value)"
    )
    
    parser.add_argument(
        "--clarifai-app-id",
        help="Clarifai App ID (convenience for --env CLARIFAI_APP_ID=value)"
    )
    
    parser.add_argument(
        "--export", "-x",
        help="Export the built image to a file (e.g., --export my-image.tar)"
    )
    
    parser.add_argument(
        "--compress-export",
        action="store_true",
        help="Compress the exported image with gzip (creates .tar.gz file)"
    )
    
    args = parser.parse_args()
    
    # Check if Docker is available
    try:
        subprocess.run(["docker", "--version"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ Docker is not installed or not running. Please install Docker first.")
        sys.exit(1)
    
    # Parse environment variables
    env_vars = {}
    for env_var in args.env:
        if "=" not in env_var:
            print(f"❌ Invalid environment variable format: {env_var}. Use KEY=VALUE")
            sys.exit(1)
        key, value = env_var.split("=", 1)
        env_vars[key] = value
    
    # Parse secrets
    secrets = {}
    for secret in args.secret:
        if "=" not in secret:
            print(f"❌ Invalid secret format: {secret}. Use KEY=VALUE")
            sys.exit(1)
        key, value = secret.split("=", 1)
        secrets[key] = value
    
    # Add convenience Clarifai arguments to both secrets and environment variables
    # Many Clarifai apps expect these as environment variables
    if args.clarifai_user_id:
        secrets["CLARIFAI_USER_ID"] = args.clarifai_user_id
        env_vars["CLARIFAI_USER_ID"] = args.clarifai_user_id
    if args.clarifai_pat:
        secrets["CLARIFAI_PAT"] = args.clarifai_pat
        env_vars["CLARIFAI_PAT"] = args.clarifai_pat
    if args.clarifai_app_id:
        secrets["CLARIFAI_APP_ID"] = args.clarifai_app_id
        env_vars["CLARIFAI_APP_ID"] = args.clarifai_app_id
    
    # Display configuration
    if env_vars:
        print(f"🌍 Environment variables: {', '.join(env_vars.keys())}")
    if secrets:
        secret_keys = [k if k != "CLARIFAI_PAT" else "CLARIFAI_PAT=***" for k in secrets.keys()]
        print(f"🔐 Streamlit secrets: {', '.join(secret_keys)}")
    
    builder = ModuleBuilder(
        app_path=args.app_path,
        image_name=args.image,
        port=args.port,
        no_build=args.no_build,
        no_run=args.no_run,
        debug=args.debug,
        env_vars=env_vars,
        secrets=secrets,
        export_path=args.export,
        compress_export=args.compress_export
    )
    
    builder.build_and_run()


if __name__ == "__main__":
    main()
