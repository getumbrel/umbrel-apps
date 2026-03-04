# Stage 1: Build ElectrumX and dependencies
FROM python:3.11-slim-bookworm AS builder

ARG ELECTRUMX_BRANCH=protocol-1.4.3-v1

RUN apt-get update && apt-get install -y \
    build-essential \
    ca-certificates \
    git \
    libleveldb-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

RUN git clone --depth 1 --branch ${ELECTRUMX_BRANCH} https://github.com/namecoin/electrumx.git

WORKDIR /build/electrumx

RUN pip install --no-cache-dir --prefix=/install \
    aiorpcx>=0.18.1,<0.23 \
    aiohttp>=3.3 \
    attrs \
    plyvel \
    pylru \
    uvloop

RUN pip install --no-cache-dir --prefix=/install .

# Stage 2: Runtime image
FROM python:3.11-slim-bookworm

RUN apt-get update && apt-get install -y \
    bash \
    ca-certificates \
    libleveldb1d \
    libssl3 \
    openssl \
    tini \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local
COPY --from=builder /build/electrumx /opt/electrumx

COPY entrypoint.sh /usr/local/bin/
COPY banner.txt /opt/electrumx/
RUN chmod +x /usr/local/bin/entrypoint.sh

RUN mkdir -p /data/electrumx-db /data/ssl && chown -R 1000:1000 /data

EXPOSE 50011 50012 8010

ENTRYPOINT ["tini", "--", "entrypoint.sh"]
