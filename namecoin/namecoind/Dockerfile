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
RUN mkdir -p /output/usr/local/bin && \
    cp build/src/namecoind build/src/namecoin-cli build/src/namecoin-tx /output/usr/local/bin/ 2>/dev/null || \
    cp build/src/bitcoin build/src/bitcoin-cli build/src/bitcoin-tx /output/usr/local/bin/ 2>/dev/null

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

COPY --from=builder /output/usr/local/bin/ /usr/local/bin/
# Namecoin Core nc30.x builds binaries named 'bitcoin', 'bitcoin-cli', 'bitcoin-tx'
# Create symlinks for namecoin-prefixed names
RUN for bin in bitcoin bitcoin-cli bitcoin-tx; do \
      if [ -f /usr/local/bin/$bin ]; then \
        ln -sf $bin /usr/local/bin/namecoin${bin#bitcoin}; \
      fi; \
    done

COPY entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/entrypoint.sh

RUN mkdir -p /data/.namecoin && chown -R 1000:1000 /data

EXPOSE 8334 8336

ENTRYPOINT ["tini", "--", "entrypoint.sh"]
