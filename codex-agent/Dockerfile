FROM node:22-bookworm-slim

ARG CODEX_VERSION
WORKDIR /app

# The Codex CLI uses the operating-system trust store for its device-code
# request. node:slim does not include that trust store by default, so retain
# ca-certificates even though Node itself can use its bundled roots.
# Pin the Codex CLI release used by the gateway. No credentials enter this layer.
RUN apt-get update \
    && apt-get install --yes --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && npm install --global --omit=dev "@openai/codex@${CODEX_VERSION}" \
    && npm cache clean --force

COPY --chown=node:node server.mjs healthcheck.mjs configure-remnic.mjs entrypoint.sh /app/
COPY --chown=node:node public/ /app/public/
RUN chmod 0555 /app/entrypoint.sh \
    && chmod -R a+rX /app

USER node
EXPOSE 8080
ENTRYPOINT ["/app/entrypoint.sh"]
