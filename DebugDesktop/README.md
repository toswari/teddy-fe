# Field Engineering Deployed Test Container

This Docker container provides a web-accessible Linux desktop environment using Apache Guacamole, VNC, and XFCE4. It includes Python 3.11, MinIO client, and Clarifai SDKs pre-installed.

## Features

- Web-based remote desktop access via Apache Guacamole
- XFCE4 desktop environment
- VNC server
- Python 3.11
- MinIO client
- Clarifai SDK
- Google Chrome browser

## Quick Start

1. Build the Docker image:
```bash
docker build -t guacamole .
```

2. Run the container:
```bash
docker run -p 8080:8080 -p 5901:5901 guacamole
```

3. Access the desktop:
   - Open your web browser and navigate to `http://localhost:8080/guacamole`
   - Login credentials:
     - Username: `admin`
     - Password: `admin`

## Port Configuration

- 8080: Guacamole web interface
- 5901: VNC server

## Default Credentials

### Guacamole Web Interface
- Username: `admin`
- Password: `admin`

### VNC User
- Username: `vnc_user`
- Password: `vncpass123`

## Container Components

- Ubuntu 20.04 base image
- Apache Guacamole 1.4.0
- XFCE4 desktop environment
- TigerVNC server
- Python 3.11
- MinIO client
- Clarifai and Clarifai-gRPC SDKs
- Google Chrome

## File Structure

- `Dockerfile`: Container build instructions
- `xstartup`: VNC startup script
- `guacamole.properties`: Guacamole server configuration
- `user-mapping.xml`: Guacamole user credentials
- `desktop.jpg`: Custom desktop background

## Building and Saving the Image

Build the image:
```bash
docker build -t guacamole .
```

Save the image to a tar file:
```bash
docker save guacamole -o guacamole.tar
```

Load the image on another machine:
```bash
docker load -i guacamole.tar
```



