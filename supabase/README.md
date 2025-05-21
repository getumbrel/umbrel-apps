
# Supabase Self-Hosting Guide

## Introduction

This guide provides instructions for setting up and configuring a self-hosted Supabase installation on Umbrel.

## Initial Setup After Installation

After installing Supabase from the Umbrel app store, you need to configure the server's host information:

1. Open the Files app from the Umbrel dashboard
2. Navigate to `apps` → `supabase`
3. Locate and download the `exports.sh` file to your computer
4. Open the file in a text editor and update the following line with your Umbrel's IP address:

```bash
# Replace with your Umbrel's IP or host name
export UMBREL_HOST="172.17.0.3" # your's might be different
```

5. Save the file and upload it back to the same location
6. Restart the Supabase app from the Umbrel dashboard

This configuration is essential for proper function of Supabase.