FROM debian:bookworm-slim

ARG TARGETARCH=amd64

# Install minimal runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    iproute2 \
    kmod \
    curl \
    python3 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean \
    && apt-get autoremove -y \
    && rm -rf /var/cache/apt/archives/*

# Download and install nvpn CLI - supports both amd64 and arm64
RUN case "${TARGETARCH}" in \
        amd64) ARCH="x86_64-unknown-linux-musl" ;; \
        arm64) ARCH="aarch64-unknown-linux-musl" ;; \
        *) echo "unsupported architecture: ${TARGETARCH}"; exit 1 ;; \
    esac && \
    curl -fsSL "https://github.com/mmalmi/nostr-vpn/releases/download/v0.3.4/nvpn-${ARCH}.tar.gz" | tar -xz -C /tmp && \
    mv /tmp/nvpn/nvpn /usr/local/bin/ && \
    chmod +x /usr/local/bin/nvpn && \
    rm -rf /tmp/nvpn

# Copy application files
COPY nvpn-web.py /usr/local/bin/nvpn-web
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/nvpn-web /usr/local/bin/entrypoint.sh

# Create data directory structure
# Note: The /data volume is mounted by Umbrel with uid:1000 permissions.
# This directory structure is created at build time; runtime permissions
# depend on Umbrel's volume creation behavior.
RUN mkdir -p /data/.config/nvpn

# Remove curl after use - not needed at runtime (healthcheck uses docker's curl)
RUN apt-get remove -y --purge curl && rm -rf /var/lib/apt/lists/*

# Run as non-root user
USER 1000:1000

# Set environment variables
ENV PATH="/usr/local/bin:${PATH}"
ENV NVPN_DATA_DIR=/data
ENV HOME=/data
ENV PYTHONUNBUFFERED=1

# Explicitly disable Python bytecode caching for security
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/')" 2>/dev/null || exit 1

CMD ["/usr/local/bin/entrypoint.sh"]