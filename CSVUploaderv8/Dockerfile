# Use the official Python image as a base image
FROM python:3.11

# Set environment variables for Flask
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0

# Set the working directory in the container
WORKDIR /app

# Create a directory for uploads
RUN mkdir -p /app/uploads

# Set permissions for the uploads directory
RUN chmod -R 777 /app/uploads
# Copy the requirements.txt file into the container at /app
COPY requirements.txt .

# Install any dependencies specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container at /app
COPY . .

# Expose port 5000 to the outside world
EXPOSE 5000

# Run the Flask application
CMD ["flask", "run"]
