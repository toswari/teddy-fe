#!/bin/bash
# Local test script to simulate the GitHub Actions workflow
# This allows you to test the load tests locally before running them on GitHub

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Function to show usage
usage() {
    echo "Usage: $0 --environment <env> --pat <token> --model-url <url> [OPTIONS]"
    echo ""
    echo "Required arguments:"
    echo "  --environment <env>      Environment: prod, dev, or test"
    echo ""
    echo "Required for prod/dev (not for test):"
    echo "  --pat <token>           Clarifai Personal Access Token"
    echo "  --model-url <url>       Full Clarifai model URL"
    echo ""
    echo "Optional arguments:"
    echo "  --duration <seconds>    Test duration in seconds (default: 60)"
    echo "  --users <number>        Number of concurrent users (default: 10)"
    echo "  --spawn-rate <rate>     Users to spawn per second (default: 1)"
    echo "  --deployment-user-id <id>  Deployment user ID (optional)"
    echo "  --help                  Show this help message"
    echo ""
    echo "Examples:"
    echo "  # Test mode (no credentials needed):"
    echo "  $0 --environment test --duration 30 --users 5"
    echo ""
    echo "  # Dev environment:"
    echo "  $0 --environment dev --pat YOUR_PAT --model-url https://web-dev.clarifai.com/user/app/models/model"
    echo ""
    echo "  # Prod environment:"
    echo "  $0 --environment prod --pat YOUR_PAT --model-url https://clarifai.com/user/app/models/model"
    exit 1
}

# Default values
ENVIRONMENT=""
PAT=""
MODEL_URL=""
DURATION=60
USERS=10
SPAWN_RATE=1
DEPLOYMENT_USER_ID=""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --pat)
            PAT="$2"
            shift 2
            ;;
        --model-url)
            MODEL_URL="$2"
            shift 2
            ;;
        --duration)
            DURATION="$2"
            shift 2
            ;;
        --users)
            USERS="$2"
            shift 2
            ;;
        --spawn-rate)
            SPAWN_RATE="$2"
            shift 2
            ;;
        --deployment-user-id)
            DEPLOYMENT_USER_ID="$2"
            shift 2
            ;;
        --help)
            usage
            ;;
        *)
            print_error "Unknown option: $1"
            usage
            ;;
    esac
done

# Validate required arguments
if [ -z "$ENVIRONMENT" ]; then
    print_error "Environment is required"
    usage
fi

if [ "$ENVIRONMENT" != "test" ] && [ "$ENVIRONMENT" != "dev" ] && [ "$ENVIRONMENT" != "prod" ]; then
    print_error "Environment must be one of: prod, dev, test"
    exit 1
fi

if [ "$ENVIRONMENT" != "test" ]; then
    if [ -z "$PAT" ]; then
        print_error "PAT is required for $ENVIRONMENT environment"
        usage
    fi
    if [ -z "$MODEL_URL" ]; then
        print_error "Model URL is required for $ENVIRONMENT environment"
        usage
    fi
fi

# Print configuration
print_info "=========================================="
print_info "Local Load Test Configuration"
print_info "=========================================="
print_info "Environment: $ENVIRONMENT"
if [ "$ENVIRONMENT" != "test" ]; then
    print_info "Model URL: $MODEL_URL"
fi
print_info "Duration: ${DURATION}s"
print_info "Users: $USERS"
print_info "Spawn Rate: $SPAWN_RATE/s"
print_info "=========================================="
echo ""

# Set environment variables
export CLARIFAI_PAT="$PAT"
export CLARIFAI_MODEL_URL="$MODEL_URL"
export CLARIFAI_DEPLOYMENT_USER_ID="$DEPLOYMENT_USER_ID"

# Set API base based on environment
if [ "$ENVIRONMENT" == "test" ]; then
    print_info "Using TEST mode (mock test - no real API calls)"
    TEST_FILE="locust_v2/tests/mock_test.py"
elif [ "$ENVIRONMENT" == "dev" ]; then
    export CLARIFAI_API_BASE="https://api-dev.clarifai.com"
    print_info "Using DEV environment (api-dev.clarifai.com)"
    TEST_FILE="locust_v2/tests/new_inference.py"

    # Validate dev URL format
    if [[ ! "$MODEL_URL" =~ ^https://web-dev\.clarifai\.com/.+/.+/models/.+ ]]; then
        print_error "Invalid dev model URL format"
        print_error "Expected: https://web-dev.clarifai.com/user_id/app_id/models/model_id"
        print_error "Got: $MODEL_URL"
        exit 1
    fi
else
    print_info "Using PROD environment (api.clarifai.com - default)"
    TEST_FILE="locust_v2/tests/new_inference.py"

    # Validate prod URL format
    if [[ ! "$MODEL_URL" =~ ^https://clarifai\.com/.+/.+/models/.+ ]]; then
        print_error "Invalid prod model URL format"
        print_error "Expected: https://clarifai.com/user_id/app_id/models/model_id"
        print_error "Got: $MODEL_URL"
        exit 1
    fi
fi

print_success "✓ Model URL validated"
echo ""

# Check if dependencies are installed
print_info "Checking dependencies..."
if ! command -v python3 &> /dev/null; then
    print_error "python3 is not installed"
    exit 1
fi

if ! python3 -c "import locust" 2>/dev/null; then
    print_warning "Locust not found. Installing dependencies..."
    pip install -r locust_v2/requirements.txt
fi

print_success "✓ Dependencies installed"
echo ""

# Run warmup check for prod/dev
if [ "$ENVIRONMENT" != "test" ]; then
    print_info "=========================================="
    print_info "Running Model Warmup Check"
    print_info "=========================================="
    python3 locust_v2/tests/warmup_check.py
    if [ $? -eq 0 ]; then
        print_success "✓ Warmup check passed"
    else
        print_error "✗ Warmup check failed"
        exit 1
    fi
    echo ""
fi

# Calculate total runtime with buffer
TOTAL_DURATION=$((DURATION + 5))

# Run Locust test
print_info "=========================================="
print_info "Starting Locust Load Test"
print_info "=========================================="
print_info "Test file: $TEST_FILE"
print_info "Total runtime (with 5s buffer): ${TOTAL_DURATION}s"
echo ""

locust \
    -f "$TEST_FILE" \
    --headless \
    --users "$USERS" \
    --spawn-rate "$SPAWN_RATE" \
    --run-time "${TOTAL_DURATION}s" \
    --html locust_report.html \
    --csv locust_results \
    --host=http://localhost

if [ $? -eq 0 ]; then
    print_success "✓ Test completed successfully"
else
    print_error "✗ Test failed"
    exit 1
fi

echo ""

# Verify HTML report was created
if [ -f locust_report.html ]; then
    print_success "✓ HTML report generated: locust_report.html"
    ls -lh locust_report.html
else
    print_warning "✗ HTML report not found"
fi

echo ""

# Display test results
if [ -f locust_results_stats.csv ]; then
    print_info "=========================================="
    print_info "Test Results Summary"
    print_info "=========================================="
    cat locust_results_stats.csv
    echo ""
fi

if [ -f locust_results_failures.csv ]; then
    print_warning "Failures detected:"
    cat locust_results_failures.csv
    echo ""
fi

print_success "=========================================="
print_success "Test completed! Check these files:"
print_success "  - locust_report.html (interactive report)"
print_success "  - locust_results_stats.csv (statistics)"
print_success "  - locust_results_failures.csv (failures)"
print_success "  - locust_*.log (debug logs)"
print_success "=========================================="
