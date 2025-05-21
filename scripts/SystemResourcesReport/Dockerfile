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

# Create directory for logo if it doesn't exist
RUN mkdir -p /app/static/img

# Download Clarifai logo
RUN wget -O /app/static/img/clarifai_logo.png https://www.clarifai.com/hubfs/logo-main.svg || \
    echo "Clarifai logo could not be downloaded" > /app/static/img/clarifai_logo.png

# Expose port
EXPOSE 5000

# Run the application
CMD ["python", "app.py"]