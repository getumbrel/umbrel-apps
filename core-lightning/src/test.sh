#!/usr/bin/env bash

# function cleanup() {
#     docker-compose down
#     echo "Nuking data dirs..."
#     rm -rf data
# }
# trap cleanup EXIT

# docker-compose up &

while true
do
    sleep 10
    echo "Generating a block..."
    docker-compose exec bitcoind bitcoin-cli -regtest generatetoaddress 1 "bcrt1qs758ursh4q9z627kt3pp5yysm78ddny6txaqgw"
done