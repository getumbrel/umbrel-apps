# ── Stage 1: dependency check (no npm install needed — zero deps) ──────────
FROM node:20-alpine AS base

LABEL org.opencontainers.image.title="SINGULARITY Pool"
LABEL org.opencontainers.image.description="Zero-dependency solo Bitcoin mining pool for Umbrel"
LABEL org.opencontainers.image.source="https://github.com/BlackHole-Axe/singularity-pool"

# Security: run as non-root user
RUN addgroup -S pool && adduser -S pool -G pool

WORKDIR /app

# Copy source — no npm install required (zero dependencies, Node.js builtins only)
COPY package.json ./
COPY src/ ./src/
COPY static/ ./static/

# Create data directory with correct ownership
RUN mkdir -p /data && chown pool:pool /data /app

USER pool

# Stratum port + Dashboard port
EXPOSE 2038 3337

# Health check: dashboard responds within 5s
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD wget -qO- http://127.0.0.1:3337/api/state > /dev/null || exit 1

CMD ["node", "src/main.js"]
