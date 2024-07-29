#!/usr/bin/env bash

export DOCSERVER_PORT=5672
export APP_DOCSERVER_PORT=3014

export DEFAULT_INTERFACE_IP=$(ip addr show $(ip route | grep default | awk '{print $5}') | grep 'inet ' | awk '{print $2}' | cut -d/ -f1)
export DOCKER_INTERFACE_IP=$(ip addr show docker0 | grep 'inet ' | awk '{print $2}' | cut -d/ -f1)