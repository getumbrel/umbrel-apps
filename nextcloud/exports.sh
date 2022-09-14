export APP_NEXTCLOUD_PORT="8081"
export APP_NEXTCLOUD_IP="10.21.21.32"
export APP_NEXTCLOUD_DB_IP="10.21.21.33"
export APP_NEXTCLOUD_REDIS_IP="10.21.21.34"
export APP_NEXTCLOUD_CRON_IP="10.21.21.35"

local_ips=$(hostname --all-ip-addresses 2> /dev/null) || local_ips=""
export APP_NEXTCLOUD_LOCAL_IPS="${local_ips}"