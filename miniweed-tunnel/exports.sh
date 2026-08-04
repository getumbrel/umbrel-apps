#!/usr/bin/env bash
export TUNNEL_WG_TOKEN=$(printf 'tunnel-wg-api-v1:%s' "${APP_SEED}" | sha256sum | cut -d' ' -f1)
