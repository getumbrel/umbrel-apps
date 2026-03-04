# Namecoin Core daemon for Umbrel
# Build and push to Docker Hub as: namecoin/namecoin-core-umbrel:30.2

# Stage 1: Build from source
FROM debian:bookworm-slim AS builder

ARG NAMECOIN_VERSION=nc30.2

RUN apt-get update && apt-get install -y \
    autoconf \
    automake \
    autotools-dev \
    bsdmainutils \
    build-essential \
    ca-certificates \
    cmake \
    curl \
    git \
    libevent-dev \
    libboost-dev \
    libboost-filesystem-dev \
    libboost-system-dev \
    libboost-thread-dev \
    libdb5.3++-dev \
    libminiupnpc-dev \
    libnatpmp-dev \
    libsqlite3-dev \
    libssl-dev \
    libtool \
    libzmq3-dev \
    pkg-config \
    python3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
RUN git clone --depth 1 --branch ${NAMECOIN_VERSION} https://github.com/namecoin/namecoin-core.git

WORKDIR /build/namecoin-core
RUN ./autogen.sh
RUN ./configure \
    --disable-tests \
    --disable-bench \
    --disable-gui \
    --with-daemon \
    --with-utils \
    --without-miniupnpc \
    --prefix=/usr/local \
    CXXFLAGS="-O2"
RUN make -j$(nproc)
RUN make install DESTDIR=/output

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
    libminiupnpc17 \
    libnatpmp1 \
    tini \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /output/usr/local/bin/namecoind /usr/local/bin/
COPY --from=builder /output/usr/local/bin/namecoin-cli /usr/local/bin/
COPY --from=builder /output/usr/local/bin/namecoin-tx /usr/local/bin/

COPY entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/entrypoint.sh

RUN mkdir -p /data/.namecoin

EXPOSE 8334 8336

ENTRYPOINT ["tini", "--", "entrypoint.sh"]
