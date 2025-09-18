# syntax=docker/dockerfile:1.13-labs
FROM --platform=$TARGETPLATFORM nvcr.io/nvidia/cuda:12.9.1-cudnn-runtime-ubuntu24.04 AS base
RUN apt-get update
RUN apt-get install -y curl python3
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && cp /root/.local/bin/uv /usr/bin/uv
RUN uv venv /venv

COPY --link requirements.txt /home/nonroot/requirements.txt
COPY --link dist/ /home/nonroot/dist/

ENV VIRTUAL_ENV=/venv
ENV PATH="/home/nonroot/.local/bin:$VIRTUAL_ENV/bin:$PATH"

# Update clarifai package so we always have latest protocol to the API. Everything should land in /venv
RUN ["uv", "pip", "install", "--no-cache-dir", "-r", "/home/nonroot/requirements.txt"]
RUN ["uv", "pip", "show", "--no-cache-dir", "clarifai"]

# Set the NUMBA cache dir to /tmp
# Set the TORCHINDUCTOR cache dir to /tmp
# The CLARIFAI* will be set by the templaing system.
ENV NUMBA_CACHE_DIR=/tmp/numba_cache \
    TORCHINDUCTOR_CACHE_DIR=/tmp/torchinductor_cache \
    HOME=/tmp \
    DEBIAN_FRONTEND=noninteractive

# Copy linefinder source files
COPY --link=true setup.py /home/nonroot/main/setup.py
COPY --link=true hough.cpp /home/nonroot/main/hough.cpp
COPY --link=true lines.py /home/nonroot/main/lines.py

COPY --link=true config.yaml /home/nonroot/main/

# Install system dependencies for building OpenCV and C++ extensions
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    wget \
    unzip \
    pkg-config \
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev \
    libv4l-dev \
    libxvidcore-dev \
    libx264-dev \
    libgtk-3-dev \
    libatlas-base-dev \
    gfortran \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

FROM base AS builder

# Set working directory
WORKDIR /home/nonroot/main

# Install Python build dependencies
RUN uv pip install --no-cache-dir \
    numpy \
    pybind11 \
    setuptools \
    wheel

# Download and extract OpenCV 4.11.0 source code
RUN wget -O opencv-4.11.0.zip https://github.com/opencv/opencv/archive/refs/tags/4.11.0.zip && \
    unzip opencv-4.11.0.zip && \
    rm opencv-4.11.0.zip

# Build OpenCV from source
RUN cd opencv-4.11.0 && \
    mkdir -p build && cd build && \
    cmake -DCMAKE_INSTALL_PREFIX=../../opencv \
          .. && \
    make -j$(nproc) && \
    make install

COPY pybind11_opencv/ pybind11_opencv/
# Build the Python extension
RUN python3 setup.py build

# # Move the built library to the current directory
# RUN mv build/lib.*-cpython-*/hough.cpython-*.so .

FROM base as final

WORKDIR /home/nonroot/main

COPY --from=builder --chown=user:group /home/nonroot/main/opencv/ /home/nonroot/main/opencv/
COPY --from=builder --chown=user:group /home/nonroot/main/build/lib.*-cpython-*/hough.cpython-*.so /home/nonroot/main/
# Copy in the actual files like config.yaml, requirements.txt, and most importantly 1/model.py
# for the actual model.
# If checkpoints aren't downloaded since a checkpoints: block is not provided, then they will
# be in the build context and copied here as well.
COPY --link=true 1 /home/nonroot/main/1
# At this point we only need these for validation in the SDK.
COPY --link=true requirements.txt config.yaml /home/nonroot/main/

#RUN ["python", "-m", "clarifai.cli", "model", "download-checkpoints", "/home/nonroot/main", "--out_path", "/home/nonroot/main/1/checkpoints", "--stage", "build"]

RUN apt-get update && apt-get install -y libxext6 libsm6 && \
    rm -rf /var/lib/apt/lists/*

# Add the model directory to the python path.
ENV PYTHONPATH=${PYTHONPATH}:/home/nonroot/main \
    CLARIFAI_PAT=${CLARIFAI_PAT} \
    CLARIFAI_USER_ID=${CLARIFAI_USER_ID} \
    CLARIFAI_RUNNER_ID=${CLARIFAI_RUNNER_ID} \
    CLARIFAI_NODEPOOL_ID=${CLARIFAI_NODEPOOL_ID} \
    CLARIFAI_COMPUTE_CLUSTER_ID=${CLARIFAI_COMPUTE_CLUSTER_ID} \
    CLARIFAI_API_BASE=${CLARIFAI_API_BASE:-https://api.clarifai.com}

# Finally run the clarifai entrypoint to start the runner loop and local runner server.
# Note(zeiler): we may want to make this a clarifai CLI call.
ENTRYPOINT ["python", "-m", "clarifai.runners.server"]
CMD ["--model_path", "/home/nonroot/main"]
#############################
