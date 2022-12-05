export APP_NEXTCLOUD_PORT="8081"

local_ips=$(hostname --all-ip-addresses 2> /dev/null) || local_ips=""
export APP_NEXTCLOUD_LOCAL_IPS="${local_ips}"