# System Resources Report

A Dockerized Flask application that displays system resource information and allows downloading the data as a PDF report.

## Features

- Displays comprehensive system information:
  - Operating System details
  - CPU specifications
  - Memory usage
  - Storage information
  - GPU details (if available)
  - Network information
- Clean, responsive user interface
- PDF report generation
- Containerized for easy deployment

## Requirements

- Docker installed on the host machine
- Internet connection for initial Docker image pull (deployment is offline-capable)

## Deployment Instructions

### Option 1: Run from Docker Hub

```bash
# Pull the Docker image
docker pull clarifai/system-resources-report:latest

# Run the container
docker run -d --name system-report \
  --network host \
  clarifai/system-resources-report:latest
```

### Option 2: Build and Run Locally

1. Clone this repository or copy the SystemResourcesReport directory
2. Navigate to the directory:

```bash
cd SystemResourcesReport
```

3. Build the Docker image:

```bash
docker build -t system-resources-report .
```

4. Run the container:

```bash
docker run -d --name system-report \
  --network host \
  system-resources-report
```

## Accessing the Application

Once the container is running, you can access the web interface by opening a browser and navigating to:

```
http://localhost:5000
```

## Troubleshooting

### Port Conflicts

If port 5000 is already in use, you can map to a different port:

```bash
docker run -d --name system-report -p 8080:5000 system-resources-report
```

Then access the application at http://localhost:8080

### GPU Detection Issues

For GPU information to be displayed, you need to run the container with GPU access:

```bash
docker run -d --name system-report \
  --network host \
  --gpus all \
  system-resources-report
```

### Container Not Starting

Check container logs for errors:

```bash
docker logs system-report
```

### Network Issues

If you're behind a corporate firewall or proxy, you might need to configure Docker to use your proxy settings.

## Notes on System Access

- The application needs appropriate permissions to access system information
- Some resource information might be limited within containers
- For full system details, consider using the `--privileged` flag (use with caution)

## Customization

### Clarifai Logo

This application requires the official Clarifai logo for proper branding. Before deploying:

1. Download the official Clarifai brand kit from https://www.clarifai.com/brand-resources
2. Extract the ZIP file and locate an appropriate PNG logo file (preferably with transparency)
3. Rename the logo file to `clarifai_logo.png` and place it in the `static/img/` directory
4. Rebuild the Docker image if you're building locally

**Note:** The logo should be a PNG file that looks good at 40px height against a dark background (header).