FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directory for logo if it doesn't exist
RUN mkdir -p /app/static/img

# Download Clarifai logo
RUN apt-get update && \
    apt-get install -y wget && \
    wget -O /app/static/img/clarifai_logo.png https://www.clarifai.com/hubfs/logo-main.svg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Expose port
EXPOSE 5000

# Run the application
CMD ["python", "app.py"]