#!/bin/bash

# Usage: ./umbrel-app-checks.sh <umbrel-app-file>
# Example: ./umbrel-app-checks.sh umbrel-app.yml

UMBREL_APP_FILE=$1

# Check if all required fields are present
REQUIRED_FIELDS=("manifestVersion" "id" "category" "name" "version" "tagline" "description" "developer" "website" "dependencies" "support" "port" "gallery")
for FIELD in "${REQUIRED_FIELDS[@]}"; do
    if ! grep -q "^$FIELD:" $UMBREL_APP_FILE ; then
        echo "Required field $FIELD is missing"
        exit 1
    fi
done

# Check if category value is lowercase
CATEGORY=$(grep 'category:' $UMBREL_APP_FILE | cut -d':' -f2 | tr -d '[:space:]')
if [[ $CATEGORY != $(echo "$CATEGORY" | tr '[:upper:]' '[:lower:]') ]]; then
    echo "Category value is not lowercase"
    exit 1
fi

# Check if optional fields are present
OPTIONAL_FIELDS=("submission" "submitter" "defaultPassword" "defaultUsername" "repo")
for FIELD in "${OPTIONAL_FIELDS[@]}"; do
    if ! grep -q "$FIELD:" $UMBREL_APP_FILE ; then
        echo "Warning: Optional field $FIELD is missing"
    fi
done

echo "$UMBREL_APP_FILE -> All Checks passed"
