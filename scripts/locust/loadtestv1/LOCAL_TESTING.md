# Local Testing Guide

This guide explains how to run the load tests locally before running them on GitHub Actions.

## Prerequisites

- Python 3.10+
- Bash shell (Git Bash on Windows, native on Linux/Mac)
- Clarifai PAT (for prod/dev tests)

## Installation

1. Install Python dependencies:
```bash
pip install -r locust_v2/requirements.txt
```

2. Make the test script executable (Linux/Mac):
```bash
chmod +x test_local.sh
```

## Usage

### Test Mode (No Credentials Required)

Perfect for verifying the workflow works:

```bash
./test_local.sh --environment test --duration 30 --users 5
```

This runs a mock test with simulated API calls. Great for:
- Testing the script itself
- Verifying Locust setup
- Checking report generation
- No API costs!

### Dev Environment

Test against the Clarifai dev environment:

```bash
./test_local.sh \
  --environment dev \
  --pat "YOUR_DEV_PAT" \
  --model-url "https://web-dev.clarifai.com/user/app/models/model" \
  --duration 60 \
  --users 10 \
  --spawn-rate 1
```

### Prod Environment

Test against the Clarifai production environment:

```bash
./test_local.sh \
  --environment prod \
  --pat "YOUR_PROD_PAT" \
  --model-url "https://clarifai.com/user/app/models/model" \
  --duration 120 \
  --users 50 \
  --spawn-rate 5
```

## Command Line Options

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `--environment` | Yes | - | Environment: `prod`, `dev`, or `test` |
| `--pat` | For prod/dev | - | Clarifai Personal Access Token |
| `--model-url` | For prod/dev | - | Full Clarifai model URL |
| `--duration` | No | 60 | Test duration in seconds |
| `--users` | No | 10 | Number of concurrent users |
| `--spawn-rate` | No | 1 | Users to spawn per second |
| `--deployment-user-id` | No | - | Deployment user ID (optional) |
| `--help` | No | - | Show help message |

## What the Script Does

1. **Validates inputs**
   - Checks environment is valid
   - Validates model URL format
   - Ensures required parameters are provided

2. **Sets up environment**
   - Exports environment variables
   - Sets correct API base URL for dev/prod
   - Configures test parameters

3. **Installs dependencies**
   - Checks if Locust is installed
   - Installs requirements if needed

4. **Runs warmup check** (prod/dev only)
   - Makes single test call to model
   - Verifies model is responding
   - Fails fast if model not accessible

5. **Executes load test**
   - Runs Locust in headless mode
   - Generates HTML report with graphs
   - Creates CSV files with statistics
   - Saves debug logs

6. **Displays results**
   - Shows summary statistics
   - Lists any failures
   - Points to generated files

## Output Files

After running, you'll get:

- `locust_report.html` - Interactive HTML report with graphs
- `locust_results_stats.csv` - Detailed statistics
- `locust_results_failures.csv` - Failure details (if any)
- `locust_*.log` - Debug logs

## Example Workflows

### Quick Test Run (30 seconds)
```bash
./test_local.sh --environment test --duration 30 --users 3 --spawn-rate 1
```

### Light Load Test (1 minute, 10 users)
```bash
./test_local.sh \
  --environment dev \
  --pat "$CLARIFAI_PAT" \
  --model-url "$MODEL_URL" \
  --duration 60 \
  --users 10
```

### Heavy Load Test (5 minutes, 100 users)
```bash
./test_local.sh \
  --environment prod \
  --pat "$CLARIFAI_PAT" \
  --model-url "$MODEL_URL" \
  --duration 300 \
  --users 100 \
  --spawn-rate 10
```

## Troubleshooting

### "python3: command not found"
Install Python 3.10+ from python.org

### "Permission denied"
Make the script executable:
```bash
chmod +x test_local.sh
```

On Windows with Git Bash, try:
```bash
bash test_local.sh --environment test
```

### "Warmup check failed"
- Verify your PAT is correct
- Check the model URL format
- Ensure you have permissions to access the model
- Try running in test mode first to verify the script works

### "Module 'locust' not found"
Install dependencies:
```bash
pip install -r locust_v2/requirements.txt
```

## Comparing Local vs GitHub Actions

The local script simulates the GitHub Actions workflow as closely as possible:

| Step | Local Script | GitHub Actions |
|------|--------------|----------------|
| Environment setup | ✓ | ✓ |
| URL validation | ✓ | ✓ |
| Dependency install | ✓ | ✓ |
| Warmup check | ✓ | ✓ |
| Load test execution | ✓ | ✓ |
| Report generation | ✓ | ✓ |
| Results display | ✓ | ✓ |
| Artifact upload | ✗ | ✓ |

The only difference is that GitHub Actions uploads the results as artifacts, while local tests save them to your current directory.

## Tips

1. **Start with test mode** to verify everything works
2. **Use shorter durations** for initial testing
3. **Check the HTML report** for visual graphs
4. **Monitor the CSV files** for detailed metrics
5. **Review logs** if something goes wrong

## Environment Variables

Instead of passing flags, you can set environment variables:

```bash
export CLARIFAI_PAT="your_pat"
export CLARIFAI_MODEL_URL="your_model_url"

./test_local.sh --environment dev --duration 60
```

This is useful for CI/CD pipelines or repeated testing.
