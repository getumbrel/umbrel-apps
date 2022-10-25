#!/usr/bin/env bash

# Delay booting Core Lightning until the REST Tor Hidden Service is ready

HIDDEN_SERVICE_FILE="${TOR_DATA_DIR}/app-${APP_ID}-rest/hostname"

if [[ -f "${HIDDEN_SERVICE_FILE}" ]]; then
	exit
fi

"${UMBREL_ROOT}/scripts/app" compose "${APP_ID}" up --detach c-lightning-rest
"${UMBREL_ROOT}/scripts/app" compose "${APP_ID}" up --detach tor

echo "App: ${APP_ID} - Generating Tor Hidden Service..."

for attempt in $(seq 1 100); do
	if [[ -f "${HIDDEN_SERVICE_FILE}" ]]; then
		echo "App: ${APP_ID} - Hidden service file created successfully!"
		break
	fi
	sleep 0.1
done

if [[ ! -f "${HIDDEN_SERVICE_FILE}" ]]; then
	echo "App: ${APP_ID} - Hidden service file wasn't created"
fi