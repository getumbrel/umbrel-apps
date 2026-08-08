# Self-contained image for umbrel-google-drive.
# Defaults to arm64 (Umbrel Home / Pi); pass --build-arg RCLONE_ARCH=amd64
# (and RCLONE_VERSION) for other architectures.
FROM python:3.12-alpine

ARG RCLONE_VERSION=1.75.0
ARG RCLONE_ARCH=arm64

RUN apk add --no-cache ca-certificates curl unzip \
 && curl -fsSLo /tmp/rclone.zip \
      "https://downloads.rclone.org/v${RCLONE_VERSION}/rclone-v${RCLONE_VERSION}-linux-${RCLONE_ARCH}.zip" \
 && unzip -o /tmp/rclone.zip -d /tmp/rclone \
 && cp "/tmp/rclone/rclone-v${RCLONE_VERSION}-linux-${RCLONE_ARCH}/rclone" /usr/local/bin/rclone \
 && chmod +x /usr/local/bin/rclone \
 && rm -rf /tmp/rclone /tmp/rclone.zip

COPY app /app
RUN rm -f /app/icon.svg

USER 1000:1000
ENV GDC_CONFIG=/data/config.json \
    GDC_PORT=8478 \
    GDC_RCLONE=/usr/local/bin/rclone \
    PYTHONDONTWRITEBYTECODE=1
EXPOSE 8478
ENTRYPOINT ["python3", "/app/server.py"]
