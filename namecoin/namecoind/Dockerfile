# Namecoin Core daemon for Umbrel
# Build and push as: ghcr.io/mstrofnone/namecoin-core-umbrel:30.2

# Stage 1: Build from source
FROM debian:bookworm-slim AS builder

ARG NAMECOIN_VERSION=nc30.2

RUN apt-get update && apt-get install -y \
    build-essential \
    ca-certificates \
    cmake \
    curl \
    git \
    libevent-dev \
    libboost-dev \
    libdb5.3++-dev \
    libsqlite3-dev \
    libzmq3-dev \
    pkg-config \
    pkgconf \
    python3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
RUN git clone --depth 1 --branch ${NAMECOIN_VERSION} https://github.com/namecoin/namecoin-core.git

WORKDIR /build/namecoin-core
RUN cmake -B build \
    -DBUILD_GUI=OFF \
    -DBUILD_TESTS=OFF \
    -DBUILD_BENCH=OFF \
    -DENABLE_IPC=OFF \
    -DWITH_ZMQ=ON \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX=/usr/local
RUN cmake --build build -j$(nproc)
RUN cmake --install build --prefix /output/usr/local

# Stage 2: Runtime
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y \
    bash \
    ca-certificates \
    curl \
    libevent-2.1-7 \
    libdb5.3++ \
    libsqlite3-0 \
    libzmq5 \
    tini \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /output/usr/local/bin/namecoind /usr/local/bin/
COPY --from=builder /output/usr/local/bin/namecoin-cli /usr/local/bin/
COPY --from=builder /output/usr/local/bin/namecoin-tx /usr/local/bin/

COPY entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/entrypoint.sh

RUN mkdir -p /data/.namecoin && chown -R 1000:1000 /data

EXPOSE 8334 8336

ENTRYPOINT ["tini", "--", "entrypoint.sh"]
