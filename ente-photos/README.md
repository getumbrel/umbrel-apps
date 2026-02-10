# Ente Photos Self-Hosting Guide

## Table of Contents
1. [Introduction](#introduction)
2. [Initial Setup After Installation](#initial-setup-after-installation)
3. [How to Use Predefined OTPs](#how-to-use-predefined-otps)
4. [How to Find Verification Codes in Logs](#how-to-find-verification-codes-in-logs)
5. [How to Connect Desktop and Mobile Apps](#how-to-connect-desktop-and-mobile-apps)
6. [How to Update Subscription to Unlimited](#how-to-update-subscription-to-unlimited)
7. [How to Configure Custom Email Senders](#how-to-configure-custom-email-senders)
8. [Additional Resources](#additional-resources)

## Introduction

This guide provides instructions for setting up and configuring a self-hosted Ente Photos installation on Umbrel. The document covers various aspects including OTP configuration, connecting devices, subscription management, and email configuration.

## Initial Setup After Installation

After installing Ente Photos from the Umbrel app store, you need to configure the server's host information:

1. Open the Files app from the Umbrel dashboard
2. Navigate to `apps` → `ente-photos`
3. Locate and download the `export.sh` file to your computer
4. Open the file in a text editor and update the following line with your Umbrel's IP address:

```bash
# Replace with your Umbrel's IP or host name
export ENTE_HOST="172.17.0.3" # your's might be different
```

5. Save the file and upload it back to the same location
6. Restart the Ente Photos app from the Umbrel dashboard

This configuration is essential for proper communication between the Ente server and clients.

## How to Use Predefined OTPs

This section explains how to set up predefined One-Time Passwords (OTPs) for your Ente Photos installation, eliminating the need to check server logs for verification codes.

### 1. Access the Configuration File

1. After installing Ente Photos from the Umbrel app store, open the Files app from the Umbrel dashboard.
2. Navigate to `apps` → `ente-photos`.
3. Locate and download the `museum.yaml` file to your computer.

### 2. Configure Predefined OTPs

Open the `museum.yaml` file in a text editor. Find the `internal` section containing the `hardcoded-ott` configuration:

```yaml
# Various low-level configuration options
internal:
  # Hardcoded verification codes.
  # Uncomment this and set these to your email ID or domain so that you don't need to peek into the server logs for obtaining the OTP when trying to log into an instance you're developing on.
  hardcoded-ott:
    emails:
    - "example@example.org,123456" # TODO: Add your email and 6 digit OTP here
    # When running in a local environment, hardcode the verification code to
    # 123456 for email addresses ending with @example.org
    local-domain-suffix: "@example.org" # TODO: Add your email domain and 6 digit OTP here
    local-domain-value: 123456
```

You have two options for setting up predefined OTPs:

#### Option 1: Set OTP for Specific Email Addresses

Add your full email address with a comma followed by your desired 6-digit OTP:

```yaml
hardcoded-ott:
  emails:
  - "example@example.org,123456"
  - "your.email@gmail.com,111111"
```

#### Option 2: Set OTP for an Entire Domain

Define a domain suffix and a standard OTP that will work for all email addresses with that domain:

```yaml
local-domain-suffix: "@gmail.com"
local-domain-value: 111111
```

Example configuration:

```yaml
# Various low-level configuration options
internal:
  # Hardcoded verification codes.
  # Uncomment this and set these to your email ID or domain so that you don't need to peek into the server logs for obtaining the OTP when trying to log into an instance you're developing on.
  hardcoded-ott:
    emails:
    - "example@example.org,123456"
    - "example@gmail.com,111111"
    # When running in a local environment, hardcode the verification code to
    # 123456 for email addresses ending with @example.org
    local-domain-suffix: "@gmail.com"
    local-domain-value: 111111
```

### 3. Update the Configuration File

1. Delete the original `museum.yaml` file from the Files app.
2. Upload your updated `museum.yaml` file to the same directory.

### 4. Apply Changes

Restart the Ente Photos app from the Umbrel dashboard to apply your changes.

### 5. Usage

When signing in, you can now use your predefined OTP instead of checking server logs.

## How to Find Verification Codes in Logs

If you haven't set up predefined OTPs or custom email senders, you can find verification codes directly in the app logs. This is useful when you're setting up Ente for the first time or troubleshooting login issues.

### 1. Access the Logs via Troubleshoot Menu

1. From the Umbrel dashboard, find the Ente Photos app tile
2. Right-click on the Ente Photos app icon 
3. Select "Troubleshoot" from the context menu
4. A new window will open showing the live logs from the Ente Photos container

### 2. Look for Verification Codes

When you request a verification code during login, look for entries in the logs that contain the verification code. They will appear in this format:

```
ente-photos_museum_1 | INFO[0518]email.go:124 sendViaTransmail Skipping sending email to your.email@gmail.com: Verification code: 830783
```

The six-digit number at the end (in this example, `830783`) is your verification code.

### 3. Enter the Code in the Login Screen

Use this verification code in the Ente app or web interface to complete your login process.

Note: The logs will only show verification codes for the most recent requests. If you don't see your code, try requesting a new one.

## How to Connect Desktop and Mobile Apps

You can modify various Ente client apps and CLI to connect to a self-hosted custom server endpoint.

### Mobile Apps

The pre-built Ente apps from GitHub, App Store, Play Store, or F-Droid can be easily configured to use a custom server:

1. Tap 7 times on the onboarding screen to bring up the server configuration page.
2. Enter your custom server endpoint.

![Setting a custom server on the onboarding screen](https://help.ente.io/assets/custom-server.SovW5NKW.png)

### Desktop and Web Apps

Similar to mobile apps, you can configure custom server endpoints on desktop and web apps:

1. Tap 7 times on the onboarding screen to access the configuration page.
2. Enter your custom server endpoint.

![Setting a custom server on the onboarding screen on desktop or self-hosted web apps](https://help.ente.io/assets/web-dev-settings.CX9UEGb-.png)

To help identify when a custom server is being used, the app will show the endpoint at the bottom of the login prompt (if not using Ente's production server):

![Custom server indicator on the onboarding screen](https://help.ente.io/assets/web-custom-endpoint-indicator.BMuEaN8l.png)

The custom server indicator will appear on various screens during the login flow and at the bottom of the sidebar after login. Note that the custom server configuration is cleared when you reset the state during logout or when you press the change email button during login.

## How to Update Subscription to Unlimited

This section explains how to update your Ente subscription to unlimited storage using the CLI tool.

### Prerequisites

- An existing Ente account created on web/app
- Access to your Umbrel dashboard

### 1. Download and Set Up the CLI Tool

1. Go to [https://github.com/ente-io/ente/releases/tag/cli-v0.2.3](https://github.com/ente-io/ente/releases/tag/cli-v0.2.3) and download the `ente-cli` version for your operating system.
2. Extract the downloaded ZIP file. You'll find an executable named `ente`.
3. Create a file called `config.yaml` in the same directory as the `ente` executable.
4. Add the following configuration to the file:

```yaml
endpoint:
    api: "http://localhost:8080" # Update with your Ente's API URL and port
```

Example configuration:

```yaml
endpoint:
    api: "http://172.17.0.3:38080"
```

### 2. Sign In to Your Account

From the directory containing the `ente` executable, run the following command:

**Note:** For Windows users, use `./ente.exe` instead of `./ente`

```bash
./ente account add
```

Example output:

```
❯ ./ente account add
Enter app type (default: photos): 
Use default app type: photos
Enter export directory: /var/home/user/ente-cli-v0.2.3-linux-amd64
Enter email address: example@example.com
Enter password: 
Please wait authenticating...
Account added successfully
run `ente export` to initiate export of your account data
```

### 3. Get Your User ID

To update your subscription, you need to make your user an admin. First, get your user ID with this command:

```bash
./ente account list
```

Example output:

```
❯ ./ente account list
Configured accounts: 1
====================================
Email:     example@example.com
ID:        1580559962386438                 <--- Note this down
App:       photos
ExportDir: /var/home/user/ente-cli-v0.2.3-linux-amd64
====================================
```

### 4. Update Admin Configuration

1. Go to Umbrel's File app and download the `museum.yaml` file.
2. Update the admin section in `museum.yaml`:

```yaml
    # List of user IDs that can use the admin API endpoints.
    # admins: [] <- Uncomment this line and add your user id here.
    disable-registration: false
```

Example of updated `museum.yaml`:

```yaml
    # List of user IDs that can use the admin API endpoints.
    admins: [1580559962386438] # <- Add your user ID here
    disable-registration: false
```

3. Delete the original `museum.yaml` from the Files app and upload your updated version to the same directory.
4. Restart the Ente Photos app from the Umbrel dashboard.

### 5. Update Your Subscription

Run the following command to update your subscription to unlimited:

```bash
./ente admin update-subscription -a example@example.com -u example@example.com --no-limit true
```

Expected output:

```
Successfully updated storage and expiry date for user
```

Now open the Ente web interface or app. Your storage should show as 100 TB (Unlimited).

## How to Configure Custom Email Senders

This section explains how to set up custom email senders to receive OTPs and other notifications from your Ente Photos installation.

### 1. Access the Configuration File

1. Install Ente Photos from the Umbrel app store.
2. Open the **Files** app on the Umbrel dashboard.
3. Navigate to the `apps` → `ente-photos` directory.
4. Locate and download the `museum.yaml` file to your computer.

### 2. Configure the SMTP Settings

Open the downloaded `museum.yaml` file in your text editor. Locate the SMTP configuration section, which might look like the commented example below:

```yaml
# SMTP configuration (optional)
# Configure credentials for sending emails from museum (e.g., OTP emails).
# Notes:
# - Ensure the settings below are correct; otherwise, the sign-up process may get stuck.
# - Gmail SMTP host might encounter timeout errors; check your network latency with ping.
# smtp:
#     host: smtp.gmail.com
#     port: 465
#     username: example@gmail.com     # TODO: Change me
#     password: changeme              # TODO: Change me
#     email: example@gmail.com        # TODO: Change me
#     sender-name: Ente               # TODO: Change me
```

Uncomment the section and update with your SMTP details:

```yaml
smtp:
    host: smtp.gmail.com
    port: 465
    username: example@gmail.com      # Your email address
    password: changeme               # Your email password or app password
    email: example@gmail.com         # Sender email address
    sender-name: Ente                # Custom sender name
```

### 3. Update the Configuration File

1. Save your changes to the `museum.yaml` file.
2. Delete the original `museum.yaml` file from the Files app.
3. Upload your updated `museum.yaml` file to the same `apps/ente-photos` directory.

### 4. Apply the Changes

Restart the Ente Photos app from the Umbrel dashboard to load your new SMTP configuration.

### 5. Verify the Configuration

After restarting, your Ente Photos installation will use the custom email sender for sending notifications such as OTPs and password resets, eliminating the need to manually check server logs for verification codes.

## Additional Resources

If you're looking for additional guidance, Ente provides a comprehensive [self-hosting tutorial](https://help.ente.io/self-hosting/). We highly recommend checking it out for in-depth details and step-by-step troubleshooting.