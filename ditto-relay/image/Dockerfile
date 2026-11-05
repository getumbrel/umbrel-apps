# syntax=docker/dockerfile:1

# Build context is the upstream ditto-relay source at the commit pinned in
# .github/workflows/ditto-relay-image.yml, with docker-entrypoint.sh copied in.

FROM oven/bun:1.3-slim@sha256:d56a2534ffd262e92c12fd3249d3924d296d97086da773f821d7d0477435ea04 AS deps

WORKDIR /app

COPY package.json bun.lock ./
RUN bun install --frozen-lockfile --production

FROM oven/bun:1.3-slim@sha256:d56a2534ffd262e92c12fd3249d3924d296d97086da773f821d7d0477435ea04

WORKDIR /app

ENV NODE_ENV=production \
    PORT=13131

COPY --from=deps /app/node_modules ./node_modules
COPY package.json bun.lock tsconfig.json ./
COPY src ./src
COPY scripts ./scripts
COPY public ./public
COPY docker-entrypoint.sh /usr/local/bin/ditto-relay-entrypoint
RUN chmod 0755 /usr/local/bin/ditto-relay-entrypoint

USER bun

EXPOSE 13131

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 CMD \
  bun -e 'fetch(`http://127.0.0.1:${process.env.PORT ?? 13131}/`).then((r) => process.exit(r.ok ? 0 : 1)).catch(() => process.exit(1))'

ENTRYPOINT ["/usr/local/bin/ditto-relay-entrypoint"]
CMD ["bun", "src/server.ts"]
