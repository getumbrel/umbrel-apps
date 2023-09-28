#!/bin/bash

# Usage: ./docker-compose-checks.sh <docker-compose-file>
# Example: ./docker-compose-checks.sh docker-compose.yml

DOCKER_COMPOSE_FILE=$1

# Check if all images are multi-architecture
grep 'image:' $DOCKER_COMPOSE_FILE | while read -r line ; do
    IMAGE=$(echo $line | cut -d' ' -f2)
    ARCHITECTURES=$(docker run --rm mplatform/mquery:v0.5.0@sha256:d0989420b6f0d2b929fd9355f15c767f62d0e9a72cdf999d1eb16e6073782c71 $IMAGE | grep -E 'linux/amd64|linux/arm64')
    if [[ ! $ARCHITECTURES =~ "linux/amd64" ]] || [[ ! $ARCHITECTURES =~ "linux/arm" ]]; then
        echo "Image $IMAGE does not support both linux/amd64 and linux/arm architectures"
        exit 1
    fi
done

# Check if no image uses the latest tag
if grep -q ':latest' $DOCKER_COMPOSE_FILE ; then
    echo "Some images use the latest tag"
    exit 1
fi

# Check if PROXY_AUTH_ADD is set to true
if grep -q 'PROXY_AUTH_ADD: "true"' $DOCKER_COMPOSE_FILE ; then
    echo "PROXY_AUTH_ADD is set to true"
    exit 1
fi

echo "$DOCKER_COMPOSE_FILE -> All Checks passed"
