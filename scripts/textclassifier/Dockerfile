FROM python:3.11-slim

# Install minimal system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Make the startup script executable
RUN chmod +x start_runner.sh

# Expose port for the runner
EXPOSE 8080

# Set environment variables
ENV PYTHONPATH=/app

# Command to run the Clarifai local runner
CMD ["./start_runner.sh"]