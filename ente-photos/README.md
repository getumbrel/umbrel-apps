# Ente Photos 📸
Safe Home for Your Photos

## Steps to Set Up Ente Photos

### 1. Install Ente Photos 🛠️
First, install the Ente Photos application on your Umbrel device. Navigate to the Umbrel App Store and select Ente Photos to complete the installation.

*Note: After installation, open the following URL to ensure the service is running and responding correctly. You should receive a "pong" response. Which shows all services are up and running.*

**URL**: `http://172.17.0.2:8080/ping`

**Expected Response**:
```json
{
  "id": "b0674cd5f37cebda0f446db7ce1e87a3e6d8b9fc", # id can be anything
  "message": "pong"
}
```

### 2. Update Configuration 🖥️
Next, update the IP/Host and other configurations in the `/home/umbrel/umbrel/app-data/ente-photos/exports.sh` file. Make sure the details are accurate for your setup.

Example configuration in `/home/umbrel/umbrel/app-data/ente-photos/exports.sh`:
```bash
# Replace with your Umbrel's IP or host name
export APP_HOST="umbrel.local"

# Default DB Configs
export DB_HOST="postgres"
export DB_PORT="5432"
export DB_NAME="ente_db"
export DB_USER="pguser"
export DB_PASSWORD="pgpass"

# Default MinIO Configs
export MINIO_API_PORT="3200"
export MINIO_CONSOLE_PORT="3201"
export MINIO_ROOT_USER="test"
export MINIO_ROOT_PASSWORD="testtest"
export MINIO_REGION="eu-central-2"

# SMTP Configs to send OTP emails
export SMTP_HOST="smtp.gmail.com"
export SMTP_PORT="465"
export SMTP_USERNAME="example@gmail.com"
export SMTP_PASSWORD="changeme"
# The email address from which to send the email.
export SMTP_EMAIL="example@gmail.com"

# Uncomment and set these to your email ID or domain to avoid checking server logs for OTPs.
# export INTERNAL_HARDCODED_OTT_EMAILS="example@example.org,123456"

# Hardcode the verification code to 123456 for email addresses ending with @example.org
export INTERNAL_HARDCODED_OTT_LOCAL_DOMAIN_SUFFIX="@example.com"
export INTERNAL_HARDCODED_OTT_LOCAL_DOMAIN_VALUE="123456"

# List of user IDs that can use the admin API endpoints.
# e.g. export INTERNAL_ADMINS="1580559962386439,1580559962386440"
export INTERNAL_ADMINS=""
```

### 3. Create the First Account and Obtain the User ID 🔑

Download and install the Ente Desktop or Mobile [App](https://ente.io). To configure the connection endpoint, tap the onboarding screen 7 times to reveal a configuration page. Detailed instructions can be found in the Ente documentation [here](https://help.ente.io/self-hosting/guides/custom-server/).

Once configured, create your first account in the app. This will generate a user ID for the newly created account. Next, open the UmbrelOS [Terminal](http://umbrel.local/settings/terminal/umbrelos) and run the CLI, providing the required information as prompted. 

**Command**:
```shell
# Follow the prompts to log into the account created by the Ente Photos Desktop or Mobile app.
sudo docker exec -it ente-photos_cli_1 ./ente-cli account add
```

**Output**:
```shell
[sudo] password for umbrel: 
Enter app type (default: photos): 
Use default app type: photos
Enter export directory: /var/tmp
Enter email address: example@example.com
Enter password: 
Please wait authenticating...
Account added successfully
run `ente export` to initiate export of your account data
```

Retrieve the user ID of the newly created account:

**Command**:
```shell
sudo docker exec -it ente-photos_cli_1 ./ente-cli account list
```

**Output**:
```shell
Configured accounts: 1
====================================
Email:     example@example.com
ID:        1580559962386438
App:       photos
ExportDir: /var/tmp
====================================
```

### 4. Make the User an Admin 👨‍💼
Make the user an admin by updating the `INTERNAL_ADMINS` variable in the `/home/umbrel/umbrel/app-data/ente-photos/exports.sh` file.

Example:
```bash
...
# List of user IDs that can use the admin API endpoints.
# e.g. export INTERNAL_ADMINS="1580559962386439,1580559962386440"
export INTERNAL_ADMINS="1580559962386438"
...
```

Run `/home/umbrel/umbrel/app-data/ente-photos/update_admins.sh` to create a `museum.yaml` with all admin IDs.

### 5. Restart Ente Photos 🔄
Restart the Ente Photos application from the UmbrelOS dashboard.

### 6. Update Storage Provision 💾
Update the storage provision to ensure you have allocated sufficient storage for your Ente Photos application.

Example:
```bash
sudo docker exec -it ente-photos_cli_1 ./ente-cli admin update-subscription -a example@example.com -u example@example.com --no-limit true
```

### Final Steps 🎉    
By following these steps, you should have successfully set up Ente Photos on your Umbrel device. If you encounter any issues, refer to the [official self-hosting documentation](https://help.ente.io/self-hosting) or reach out to support.