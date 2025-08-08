#!/bin/sh
set -e

# Configuration
LOG_DIR="/logs"
LOG_FILE="${LOG_DIR}/kaspad_buffer.log"
BUFFER_SIZE=10000

# Ensure log directory exists
mkdir -p "${LOG_DIR}"

# Start kaspad with all arguments and pipe output to rolling buffer
exec kaspad \
  --rpclisten=0.0.0.0:16110 \
  --rpclisten-borsh=0.0.0.0:17110 \
  --rpclisten-json=0.0.0.0:18110 \
  --loglevel=info \
  "$@" 2>&1 | {
    # Initialize the log file
    > "${LOG_FILE}"
    
    # Read lines and maintain rolling buffer
    while IFS= read -r line; do
        echo "$line" >> "${LOG_FILE}"
        
        # Check line count and trim if necessary
        LINE_COUNT=$(wc -l < "${LOG_FILE}" 2>/dev/null || echo 0)
        if [ "$LINE_COUNT" -gt "$BUFFER_SIZE" ]; then
            tail -n "$BUFFER_SIZE" "${LOG_FILE}" > "${LOG_FILE}.tmp"
            mv "${LOG_FILE}.tmp" "${LOG_FILE}"
        fi
        
        # Also output to stdout for Docker logging
        echo "$line"
    done
}