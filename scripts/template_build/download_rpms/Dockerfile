
FROM almalinux

WORKDIR /app

RUN dnf install -y dnf-plugins-core dos2unix \
    && dnf clean all
COPY requirements.txt /app/requirements.txt
COPY download_rpms.sh /app/download_rpms.sh
RUN chmod +x /app/download_rpms.sh \
    && dos2unix /app/download_rpms.sh
ENTRYPOINT ["/bin/bash", "/app/download_rpms.sh"]
