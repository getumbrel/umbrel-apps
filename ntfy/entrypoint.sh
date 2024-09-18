#!/bin/sh
ntfy serve &
sleep 2
NTFY_PASSWORD=${NTFY_PASSWORD} ntfy user add --role=admin umbrel || true
wait