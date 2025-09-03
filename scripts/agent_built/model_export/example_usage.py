#!/usr/bin/env python3
"""
Example usage of the Clarifai model export script.

This script demonstrates different ways to use the model export functionality.
"""

import os
import subprocess
import sys
from pathlib import Path

def run_command(cmd, description):
    """Run a command and print the result."""
    print(f"\n🔧 {description}")
    print(f"Command: {' '.join(cmd)}")
    print("-" * 50)
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Command failed: {e}")
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
        return False

def main():
    """Demonstrate model export usage."""
    script_dir = Path(__file__).parent
    export_script = script_dir / "export_model.py"
    
    if not export_script.exists():
        print(f"❌ Export script not found: {export_script}")
        return False
    
    print("🚀 Clarifai Model Export Examples")
    print("=" * 50)
    
    # Example 1: Show help
    if not run_command(
        [sys.executable, str(export_script), "--help"],
        "Show help message"
    ):
        return False
    
    # Example 2: Test with invalid URL (should fail gracefully)
    print("\n" + "=" * 50)
    print("Testing error handling with invalid URL...")
    cmd = [sys.executable, str(export_script), "invalid-url"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("✅ Script correctly handles invalid URLs")
        print("Error output:", result.stderr.split('\n')[0])
    else:
        print("⚠️  Script should have failed with invalid URL")
    
    # Example 3: Test with valid URL but no auth (should fail gracefully)
    print("\n" + "=" * 50)
    print("Testing with valid URL but no authentication...")
    cmd = [
        sys.executable, str(export_script),
        "https://clarifai.com/clarifai/main/models/general-image-recognition",
        "--output", "/tmp/test_no_auth"
    ]
    # Remove any existing auth env vars for this test
    env = os.environ.copy()
    env.pop('CLARIFAI_PAT', None)
    env.pop('CLARIFAI_USER_ID', None)
    
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if result.returncode != 0:
        print("✅ Script correctly requires authentication")
        print("Error output:", result.stderr.split('\n')[0])
    else:
        print("⚠️  Script should have failed without authentication")
    
    print("\n" + "=" * 50)
    print("Example Usage Summary:")
    print("=" * 50)
    
    examples = [
        {
            "name": "Basic Export",
            "cmd": "python export_model.py https://clarifai.com/user/app/models/model",
            "description": "Export model to ./exported_model directory"
        },
        {
            "name": "Docker Export",
            "cmd": "python export_model.py MODEL_URL --docker",
            "description": "Export model and create Docker image"
        },
        {
            "name": "Custom Output",
            "cmd": "python export_model.py MODEL_URL --output ./my_model",
            "description": "Export to custom directory"
        },
        {
            "name": "Export Docker Image",
            "cmd": "python export_model.py MODEL_URL --docker --export-image model.tar",
            "description": "Create and export Docker image to file"
        },
        {
            "name": "With Authentication",
            "cmd": "python export_model.py MODEL_URL --pat YOUR_PAT --user-id YOUR_ID",
            "description": "Provide authentication via command line"
        }
    ]
    
    for i, example in enumerate(examples, 1):
        print(f"\n{i}. {example['name']}")
        print(f"   Command: {example['cmd']}")
        print(f"   Description: {example['description']}")
    
    print("\n📋 Environment Setup:")
    print("   export CLARIFAI_PAT='your_personal_access_token'")
    print("   export CLARIFAI_USER_ID='your_user_id'")
    
    print("\n📚 For more examples, see the README.md file")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)