# SAM2 Labeling Flask

This project is a Flask-based web application for labeling and tracking objects in video segments using SAM2.

## Prerequisites

- Docker and Docker Compose installed on your machine.
- Python 3.13 (if running locally).

## Setup

1. **Clone the repository:**

   ```bash
   git clone <repository-url>
   cd <repository-directory>
   ```

2. **Create a `.env` file:**

   Create a `.env` file in the root directory with the following content:

   ```
   PAT=123456Yourpathere2345
   ```

   This file is required for the application to run correctly.

3. **Build and run the Docker container:**

   ```bash
   docker-compose up --build
   ```

   This will build the Docker image and start the Flask application. The app will be available at `http://localhost:5000`.

   Alternatively, you can use traditional Docker commands:

   ```bash
   docker build -t sam2-labeling-flask .
   docker run -p 5000:5000 sam2-labeling-flask
   ```

   This will build the Docker image and run the container, making the app available at `http://localhost:5000`.

## Usage

- Open your web browser and navigate to `http://localhost:5000`.
- Follow the on-screen instructions to label and track objects in your video segments.

## Development

- The application uses Flask for the backend and a simple HTML/CSS/JS frontend.
- The `requirements.txt` file lists all the Python dependencies required for the project.

## Troubleshooting

- Ensure the `.env` file is present and contains the correct `PAT` value.
- Check Docker logs for any errors during startup.
