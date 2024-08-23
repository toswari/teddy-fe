import os
import subprocess
import shutil

REPO_URL = "https://github.com/Clarifai/runners-python.git"
CLONE_DIR = "runners-python"
EXAMPLES_DIR = os.path.join(CLONE_DIR, "examples")
ENV_TEMPLATE = os.path.join(EXAMPLES_DIR, ".env.template")
DEV_ENV_FILE = ".dev.env.template"

def run_command(command, cwd=None):
    try:
        subprocess.run(command, shell=True, check=True, cwd=cwd)
    except subprocess.CalledProcessError as e:
        print(f"Command failed: {e}")
        exit(1)

def clone_repo():
    if not os.path.exists(CLONE_DIR):
        print("Cloning the repository...")
        run_command(f"git clone {REPO_URL}")
    else:
        print("Repository already cloned.")

def install_dependencies():
    print("Installing dependencies...")
    run_command("pip install -r requirements.txt", cwd=CLONE_DIR)
    run_command("python setup.py develop", cwd=CLONE_DIR)

def setup_dev_env():
    print("Setting up the development environment...")
    os.environ['CLARIFAI_API_BASE'] = "https://api-dev.clarifai.com"
    os.environ['CLARIFAI_PAT'] = " PAT HERE"
    os.environ['CLARIFAI_USER_ID'] = "mulder"
    os.environ['CLARIFAI_APP_ID'] = "testapp"
    print("CLARIFAI_PAT environment variable set.")

def copy_example_folder():
    example_folders = [f for f in os.listdir(EXAMPLES_DIR) if os.path.isdir(os.path.join(EXAMPLES_DIR, f))]
    if not example_folders:
        print("No example folders found.")
        return None
    selected_folder = "python_string_cat"  # Chose this one for now
    new_folder = os.path.join(EXAMPLES_DIR, f"custom_{selected_folder}")
    shutil.copytree(os.path.join(EXAMPLES_DIR, selected_folder), new_folder)
    return new_folder

def customize_model(folder_path):
    config_path = os.path.join(folder_path, "config.yaml")
    model_py_path = os.path.join(folder_path, "model.py")
    print(f"Customizing {config_path} and {model_py_path} as needed...")
    with open(config_path, "r") as file:
        config_content = file.read()
    config_content = config_content.replace("id: \"python_string_cat\"", "id: \"testapp\"")
    config_content = config_content.replace("user_id: \"user_id\"", "user_id: \"mulder\"")
    config_content = config_content.replace("app_id: \"app_id\"", "app_id: \"testapp\"")
    with open(config_path, "w") as file:
        file.write(config_content)
    checkpoints_script = os.path.join(folder_path, "download_checkpoints.py")
    if os.path.exists(checkpoints_script):
        print(f"Running {checkpoints_script}...")
        run_command(f"python {checkpoints_script}", cwd=folder_path)

def upload_model(folder_path):
    print("Uploading the model...")
    upload_script = os.path.join(CLONE_DIR, "examples", "upload_folder.py")
    if not os.path.exists(upload_script):
        print(f"upload_folder.py not found at {upload_script}.")
        exit(1)
    run_command(f"python {upload_script} --folder {folder_path}")

if __name__ == "__main__":
    clone_repo()
    install_dependencies()
    setup_dev_env()
    custom_folder = copy_example_folder()
    if custom_folder:
        customize_model(custom_folder)
        upload_model(custom_folder)
    else:
        print("No example folder copied, exiting.")
