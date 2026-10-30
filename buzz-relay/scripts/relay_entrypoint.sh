#!/bin/bash
# Umbrel relay wrapper: re-read secrets and re-exec buzz-relay when the setup
# UI requests a restart. A plain `docker restart` would NOT reload env_file
# contents (RELAY_OWNER_PUBKEY); Umbrel's full app restart works but cannot be
# triggered from inside this container. This flag-file path is the safe middle.
#
# The ghcr.io/block/buzz image runs as uid/gid 1000 (user `buzz`). Secrets must
# be owned by that user (pre-start + setup-api chown them). Never `source` a
# root-only relay.env under `set -e` — that crash-looped 0.2.10/0.2.11.
set -euo pipefail

SECRETS="${BUZZ_SECRETS_DIR:-/secrets}"
FLAG="${SECRETS}/restart-relay.requested"
CHILD_PID=""

load_env() {
  if [[ -f "${SECRETS}/relay.env" ]]; then
    if [[ -r "${SECRETS}/relay.env" ]]; then
      set -a
      # shellcheck disable=SC1090
      source "${SECRETS}/relay.env"
      set +a
    else
      echo "App: buzz-relay - ${SECRETS}/relay.env not readable by uid $(id -u); using container env (run Umbrel Restart after upgrade so pre-start can chown secrets)" >&2
    fi
  fi
  if [[ -f "${SECRETS}/owner-pubkey.override" ]]; then
    if [[ -r "${SECRETS}/owner-pubkey.override" ]]; then
      export RELAY_OWNER_PUBKEY
      RELAY_OWNER_PUBKEY="$(tr -d '[:space:]' < "${SECRETS}/owner-pubkey.override")"
    else
      echo "App: buzz-relay - owner-pubkey.override not readable by uid $(id -u)" >&2
    fi
  fi
}

stop_child() {
  if [[ -n "${CHILD_PID}" ]] && kill -0 "${CHILD_PID}" 2>/dev/null; then
    kill -TERM "${CHILD_PID}" 2>/dev/null || true
    # Give the relay its stop_grace window, then force.
    for _ in $(seq 1 50); do
      if ! kill -0 "${CHILD_PID}" 2>/dev/null; then
        break
      fi
      sleep 0.2
    done
    if kill -0 "${CHILD_PID}" 2>/dev/null; then
      kill -KILL "${CHILD_PID}" 2>/dev/null || true
    fi
    wait "${CHILD_PID}" 2>/dev/null || true
  fi
  CHILD_PID=""
}

on_signal() {
  echo "App: buzz-relay - received stop signal" >&2
  stop_child
  exit 0
}
trap on_signal SIGTERM SIGINT

# Directory may already be mounted; ignore failures (we are not root).
mkdir -p "${SECRETS}" 2>/dev/null || true

if [[ ! -x /usr/local/bin/buzz-relay && ! -f /usr/local/bin/buzz-relay ]]; then
  echo "App: buzz-relay - missing /usr/local/bin/buzz-relay" >&2
  exit 1
fi

# If the bind-mount target became a directory (Docker missing-file trap), fail
# loudly instead of looping forever.
if [[ -d /relay_entrypoint.sh ]]; then
  echo "App: buzz-relay - /relay_entrypoint.sh is a directory (Docker bind-mount trap). Stop the app, delete data/setup/relay_entrypoint.sh, and start again so pre-start can install the script." >&2
  exit 1
fi

while true; do
  load_env
  rm -f "${FLAG}" 2>/dev/null || true

  /usr/local/bin/buzz-relay &
  CHILD_PID=$!
  echo "App: buzz-relay - started pid=${CHILD_PID} uid=$(id -u) RELAY_OWNER_PUBKEY=${RELAY_OWNER_PUBKEY:-unset}"

  while kill -0 "${CHILD_PID}" 2>/dev/null; do
    if [[ -f "${FLAG}" ]]; then
      echo "App: buzz-relay - restart requested via /umbrel-setup/"
      stop_child
      rm -f "${FLAG}" 2>/dev/null || true
      break
    fi
    sleep 1
  done

  if [[ -n "${CHILD_PID}" ]]; then
    set +e
    wait "${CHILD_PID}"
    status=$?
    set -e
    CHILD_PID=""
    echo "App: buzz-relay - process exited status=${status}; restarting in 2s" >&2
    sleep 2
  fi
done
