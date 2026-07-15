local_ips=$(hostname --all-ip-addresses 2> /dev/null | tr ' ' ',') || local_ips=""
export APP_PAPERCLIP_LOCAL_IPS="${local_ips}"
