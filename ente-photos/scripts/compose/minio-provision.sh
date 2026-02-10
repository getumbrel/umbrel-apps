#!/bin/sh

# Script used to prepare the minio instance
while ! mc config host add h0 http://minio:3200 $MINIO_ROOT_USER $MINIO_ROOT_PASSWORD 2>/dev/null
do
   echo "Waiting for minio..."
   sleep 0.5
done

cd /data

mc mb -p b2-eu-cen
mc mb -p wasabi-eu-central-2-v3
mc mb -p scw-eu-fr-v3