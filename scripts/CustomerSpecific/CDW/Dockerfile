FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create upload directory if it doesn't exist
RUN mkdir -p static/uploads

# Create directories for CSS and JS
RUN mkdir -p static/css static/js

# Set permissions for the uploads directory
RUN chmod -R 777 static/uploads

# Expose port
EXPOSE 5000

# Command to run the application
CMD ["python", "app.py"] 