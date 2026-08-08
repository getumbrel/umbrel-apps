FROM node:22-bookworm-slim

ARG CODEX_VERSION
WORKDIR /app

# Pin the Codex CLI release used by the gateway. No credentials enter this layer.
RUN npm install --global --omit=dev "@openai/codex@${CODEX_VERSION}" \
    && npm cache clean --force

COPY --chown=node:node server.mjs healthcheck.mjs configure-remnic.mjs entrypoint.sh /app/
COPY --chown=node:node public/ /app/public/
RUN chmod 0555 /app/entrypoint.sh \
    && chmod -R a+rX /app

USER node
EXPOSE 8080
ENTRYPOINT ["/app/entrypoint.sh"]
