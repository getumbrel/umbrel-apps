#!/bin/bash
# ==============================================================================
# Garbageman Nodes Manager - Umbrel Environment Exports
# ==============================================================================
# This script is executed by Umbrel before starting the app's docker-compose.yml
# It exports environment variables that can be used in docker-compose.yml via
# variable substitution (e.g., $APP_GARBAGEMAN_NM_IP)
#
# These variables are also made available to other Umbrel apps for inter-app
# communication (e.g., if another app needs to know our API endpoint)

# ==============================================================================
# IP Address Assignment
# ==============================================================================
# Umbrel assigns apps static IPs in the 10.21.21.x range on its internal network
# This IP must be unique across all installed apps
# 
# We use 10.21.21.201 which is above the range used by official Umbrel apps
# as of November 2024 (they typically use 10.21.21.1 through 10.21.21.100)
#
# IMPORTANT: If you fork this app, check current IP assignments to avoid conflicts:
# ssh umbrel@umbrel.local 'docker network inspect umbrel_main_network'
export APP_GARBAGEMAN_NM_IP="10.21.21.201"

# ==============================================================================
# Service Ports (for reference/inter-app communication)
# ==============================================================================
# These define the ports our services listen on INSIDE the container
# External access is handled by Umbrel's app_proxy (configured in umbrel-app.yml)
#
# Port 5173: Web UI (Next.js frontend) - primary user interface
# Port 8080: REST API (Fastify backend) - programmatic access
# Port 9000: Supervisor API - manages Bitcoin daemon instances
export APP_GARBAGEMAN_NM_UI_PORT="5173"
export APP_GARBAGEMAN_NM_API_PORT="8080"
export APP_GARBAGEMAN_NM_SUPERVISOR_PORT="9000"

# ==============================================================================
# Data Directory (for inter-app access)
# ==============================================================================
# EXPORTS_APP_DIR is provided by Umbrel and points to our app's data directory
# (typically: /home/umbrel/umbrel/app-data/garbageman-nm)
#
# This export allows other apps to reference our data directory if needed
# For example, a backup app might want to know where our Bitcoin data lives
export APP_GARBAGEMAN_NM_DATA_DIR="${EXPORTS_APP_DIR}/data"
