#!/usr/bin/bash

# Author: https://github.com/starfreck
# This script runs automatically on each restart. It reads admin IDs from the environment
# and writes them into "museum.yaml" at "/home/umbrel/umbrel/app-data/ente-photos".
# To run manually, execute it from the "/home/umbrel/umbrel/app-data/ente-photos" directory.

# Function to delete the existing file or directory
delete_existing_file() {
  local file_path=$1
  if [ -e "$file_path" ]; then
    if [ -d "$file_path" ]; then
      rmdir "$file_path"
    else
      rm "$file_path"
    fi
    echo "Deleted existing $file_path"
  fi
}

# Function to read admin IDs from the environment variable
read_admin_ids_from_env() {
  local ids_env
  ids_env=$(printenv INTERNAL_ADMINS)
  if [ -z "$ids_env" ]; then
    echo ""
  else
    echo "$ids_env" | tr ',' '\n'
  fi
}

# Function to write admin IDs to the YAML file
write_admin_ids_to_yaml() {
  local file_path=$1
  shift
  local admin_ids=("$@")

  echo "internal:" > "$file_path"
  echo "  admins:" >> "$file_path"
  for admin_id in "${admin_ids[@]}"; do
    echo "    - $admin_id" >> "$file_path"
  done
  echo "Created new $file_path with Admin IDs: ${admin_ids[*]}"
}

# Main function to create the admin config file
create_admin_config_file() {
  local config_file="/home/umbrel/umbrel/app-data/ente-photos/museum.yaml"
  
  delete_existing_file "$config_file"
  
  local admin_ids
  IFS=$'\n' read -d '' -r -a admin_ids < <(read_admin_ids_from_env && printf '\0')
  
  write_admin_ids_to_yaml "$config_file" "${admin_ids[@]}"
}

source /home/umbrel/umbrel/app-data/ente-photos/exports.sh
echo "Running create_admin_config_file..."
create_admin_config_file