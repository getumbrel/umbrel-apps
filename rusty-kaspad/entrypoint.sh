#!/bin/sh
set -e

# Configuration
LOG_DIR="/logs"
LOG_FILE="${LOG_DIR}/kaspad_buffer.log"
BUFFER_SIZE=10000

# Ensure log directory exists
mkdir -p "${LOG_DIR}"

# Call the original entrypoint with kaspad and our custom arguments
# The original entrypoint handles user switching and IP detection
exec /app/entrypoint.sh kaspad \
  --rpclisten=0.0.0.0:16110 \
  --rpclisten-borsh=0.0.0.0:17110 \
  --rpclisten-json=0.0.0.0:18110 \
  --loglevel=info \
  --yes \
  --nologfiles \
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
