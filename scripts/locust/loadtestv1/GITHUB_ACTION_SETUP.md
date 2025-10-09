# GitHub Action Setup for Clarifai Load Tests

This repository includes a GitHub Action workflow for running Locust load tests on Clarifai models.

## Prerequisites

### Get Your Clarifai Credentials

Before running the workflow against real Clarifai APIs (prod/dev), you need:

1. **Personal Access Token (PAT)**: Get your Clarifai PAT from the [Clarifai platform](https://clarifai.com/settings/security)
2. **Model URL**: Should be in the format:
   ```
   https://clarifai.com/user_id/app_id/models/model_id
   ```
   You can find this URL in the Clarifai platform when viewing your model.

**Note**: For testing the workflow setup without hitting real APIs, use the `test` environment (no credentials required).

## Running the Load Test

### Using GitHub UI

1. Go to the **Actions** tab in your repository
2. Select **Clarifai Model Load Test** from the left sidebar
3. Click **Run workflow** button
4. Fill in the parameters:
   - **Environment** (required): Choose `prod`, `dev`, or `test` (default: prod)
     - `test`: Mock test mode - no real API calls, no credentials required
     - `prod`: Production Clarifai API
     - `dev`: Development Clarifai API
   - **PAT** (optional): Your Clarifai Personal Access Token (not required for `test` mode)
   - **Model URL** (optional): Full Clarifai model URL (not required for `test` mode)
   - **Duration** (required): Test duration in seconds (default: 60)
   - **Users** (optional): Number of concurrent users (default: 10)
   - **Spawn Rate** (optional): Users to spawn per second (default: 1)
   - **Deployment User ID** (optional): If using a specific deployment
5. Click **Run workflow**

### Using GitHub CLI

You can also trigger the workflow using the GitHub CLI:

**Production/Dev Test:**
```bash
gh workflow run clarifai-load-test.yml \
  -f environment=prod \
  -f pat="your_clarifai_pat_token" \
  -f model_url="https://clarifai.com/user_id/app_id/models/model_id" \
  -f duration=120 \
  -f users=20 \
  -f spawn_rate=2
```

**Mock Test (no credentials needed):**
```bash
gh workflow run clarifai-load-test.yml \
  -f environment=test \
  -f duration=30 \
  -f users=5 \
  -f spawn_rate=1
```

## Workflow Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `environment` | Yes | prod | Environment to test (`prod`, `dev`, or `test`) |
| `pat` | No | - | Clarifai Personal Access Token (not needed for `test`) |
| `model_url` | No | test URL | Full Clarifai model URL (not needed for `test`) |
| `duration` | Yes | 60 | Test duration in seconds |
| `users` | No | 10 | Number of concurrent users |
| `spawn_rate` | No | 1 | Users to spawn per second |
| `deployment_user_id` | No | '' | Deployment user ID (if applicable) |

## Viewing Results

After the workflow completes:

1. **Summary**: View the test summary in the workflow run's summary page
2. **Artifacts**: Download the full HTML report and CSV files from the artifacts section
   - `locust_report.html`: Interactive HTML report with graphs
   - `locust_results_stats.csv`: Detailed statistics
   - `locust_results_failures.csv`: Failure details (if any)
   - `locust_*.log`: Debug logs

## Example Workflow Run

### Test Mode (Mock - No Real API Calls)
```yaml
Environment: test
Duration: 30 seconds
Users: 5
Spawn Rate: 1/s
```
Perfect for verifying the workflow setup works correctly without consuming API resources.

### Production Environment Test
```yaml
Environment: prod
Model URL: https://clarifai.com/openai/chat-completion/models/gpt-4
Duration: 120 seconds
Users: 50
Spawn Rate: 5/s
```

### Development Environment Test
```yaml
Environment: dev
Model URL: https://clarifai.com/your_user/your_app/models/your_model
Duration: 60 seconds
Users: 10
Spawn Rate: 1/s
```

Each test will:
- Run load test for the specified duration
- Spawn the specified number of users
- Add users at the specified spawn rate
- Generate detailed performance metrics and HTML reports
- Target the selected environment (test/prod/dev)

## Troubleshooting

### Testing the Workflow First
Before running tests against real APIs, try the `test` environment:
- Select `test` as the environment
- No PAT or model URL required
- Verifies the workflow, Locust, and report generation work correctly
- Simulates realistic API response times and metrics

### Invalid Model URL
Make sure your model URL follows the exact format:
```
https://clarifai.com/user_id/app_id/models/model_id
```
(Not required for `test` environment)

### Authentication Errors
Verify that:
- Your PAT is entered correctly (no extra spaces)
- The PAT has permissions to access the model
- The PAT hasn't expired
- You're using the correct environment (dev vs prod)
- Try `test` mode first to verify workflow setup

### Test Failures
- Check the workflow logs for detailed error messages
- Download the CSV and log files from artifacts for debugging
- Ensure the model is accessible and responding

## Customizing the Test

To modify the test behavior, edit `locust_v2/tests/new_inference.py` to:
- Change the prompt or input data
- Adjust task weights
- Add custom metrics
- Modify request parameters

After making changes, commit and push to your repository. The workflow will use the updated test file.
