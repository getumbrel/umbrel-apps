#!/bin/sh

# Bcrypt hash the password before giving it to the gateway
export FM_GATEWAY_BCRYPT_PASSWORD_HASH=$(gateway-cli create-password-hash $APP_PASSWORD \
  | sed 's/^"//; s/"$//' \
  | sed 's/\$/$$/g'
)

gatewayd lnd
