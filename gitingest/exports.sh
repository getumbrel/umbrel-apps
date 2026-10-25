# Get all local IP addresses and delimit with commas
local_ips=$(hostname --all-ip-addresses 2> /dev/null | tr ' ' ',') || local_ips=""
export APP_GITINGEST_LOCAL_IPS="${local_ips}"