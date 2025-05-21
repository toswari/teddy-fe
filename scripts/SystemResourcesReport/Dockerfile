FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies for reportlab and other packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    wget \
    build-essential \
    python3-dev \
    libfreetype6-dev \
    libjpeg-dev \
    zlib1g-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# IMPORTANT: Before building this Docker image, replace the logo file at:
# /app/static/img/clarifai_logo.png with the official Clarifai logo
# Download from: https://www.clarifai.com/brand-resources

# Create directory for logo if it doesn't exist
RUN mkdir -p /app/static/img

# Expose port
EXPOSE 5000

# Run the application
CMD ["python", "app.py"]