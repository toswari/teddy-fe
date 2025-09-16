#!/bin/bash
# Helper script to run commands with the brand-logo-312 conda environment

CONDA_ENV="brand-logo-312"
CONDA_PATH="/home/toswari/anaconda3/bin/conda"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if conda is available
if [ ! -f "$CONDA_PATH" ]; then
    print_error "Conda not found at $CONDA_PATH"
    print_error "Please update CONDA_PATH in this script"
    exit 1
fi

# Check if environment exists
if ! $CONDA_PATH env list | grep -q "$CONDA_ENV"; then
    print_warning "Environment '$CONDA_ENV' not found"
    print_status "Creating environment..."
    $CONDA_PATH create -n $CONDA_ENV python=3.12 -y
    
    if [ $? -eq 0 ]; then
        print_status "Environment created successfully"
    else
        print_error "Failed to create environment"
        exit 1
    fi
fi

# Function to run command in conda environment
run_with_conda() {
    print_status "Running in conda environment '$CONDA_ENV': $*"
    $CONDA_PATH run -n $CONDA_ENV "$@"
}

# Function to activate environment and run command
activate_and_run() {
    print_status "Activating environment '$CONDA_ENV' and running: $*"
    # For interactive shells
    echo "conda activate $CONDA_ENV && $*"
}

# Main script logic
case "$1" in
    "test")
        print_status "Running test setup..."
        run_with_conda python test_setup.py
        ;;
    "install")
        print_status "Installing requirements..."
        run_with_conda pip install -r requirements.txt
        ;;
    "app")
        print_status "Starting Streamlit application..."
        run_with_conda streamlit run app.py
        ;;
    "python")
        shift
        run_with_conda python "$@"
        ;;
    "pip")
        shift
        run_with_conda pip "$@"
        ;;
    "shell")
        print_status "To activate the environment in your current shell, run:"
        echo "conda activate $CONDA_ENV"
        ;;
    "check")
        print_status "Checking environment status..."
        if $CONDA_PATH env list | grep -q "$CONDA_ENV"; then
            print_status "Environment '$CONDA_ENV' exists ✅"
            print_status "Installed packages:"
            run_with_conda pip list | head -20
        else
            print_warning "Environment '$CONDA_ENV' not found ❌"
        fi
        ;;
    *)
        echo "Usage: $0 {test|install|app|python|pip|shell|check}"
        echo ""
        echo "Commands:"
        echo "  test     - Run test_setup.py"
        echo "  install  - Install requirements.txt"
        echo "  app      - Start Streamlit app"
        echo "  python   - Run python with args"
        echo "  pip      - Run pip with args"
        echo "  shell    - Show activation command"
        echo "  check    - Check environment status"
        echo ""
        echo "Examples:"
        echo "  $0 test"
        echo "  $0 install"
        echo "  $0 app"
        echo "  $0 python script.py"
        echo "  $0 pip install package"
        exit 1
        ;;
esac
