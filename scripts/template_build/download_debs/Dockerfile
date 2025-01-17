
FROM ubuntu:20.04

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    apt-utils \
    wget \
    apt-transport-https \
    curl \
    gnupg \
    dos2unix \
    ca-certificates \
    software-properties-common \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.29/deb/Release.key | gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring-v1.29.gpg && \
    echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring-v1.29.gpg] https://pkgs.k8s.io/core:/stable:/v1.29/deb/ /' \
    | tee /etc/apt/sources.list.d/kubernetes-v1.29.list
RUN mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg && \
    echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu focal stable" \
    | tee /etc/apt/sources.list.d/docker.list > /dev/null
RUN mkdir -p /deb_files && chmod -R a+w /deb_files /var/cache/apt/archives
COPY requirements.txt /app/requirements.txt
COPY download_debs.sh /app/download_debs.sh
RUN chmod +x /app/download_debs.sh
ENTRYPOINT ["/bin/bash", "/app/download_debs.sh"]
