# Caddy HTTPS Proxy for Umbrel

🔒 **Add automatic HTTPS encryption to your Umbrel server**

Caddy HTTPS Proxy is a reverse proxy app for Umbrel that provides HTTPS support for all your self-hosted apps. It protects against man-in-the-middle attacks on untrusted local networks by encrypting all traffic between your devices and your Umbrel server.

## Features

- **Automatic HTTPS** - Self-signed certificates generated on install
- **HTTP → HTTPS Redirect** - Seamless upgrade for all connections
- **Security Headers** - HSTS, X-Frame-Options, X-Content-Type-Options
- **Zero Configuration** - Works out of the box
- **Dynamic Routing** - Easy to configure for multiple apps
- **Certificate Management** - Simple certificate regeneration
- **Mobile Support** - Step-by-step trust guides for iOS and Android

## Installation

1. Copy the `caddy-https-app` directory to your Umbrel app store:
   ```bash
   rsync -av caddy-https-app umbrel@umbrel.local:/home/umbrel/umbrel/app-stores/
   ```

2. Install from the Umbrel App Store or via CLI:
   ```bash
   umbreld client apps.install.mutate --appId caddy-https-proxy
   ```

3. Access the proxy at: `https://umbrel.local:8443/`

## Usage

### Default Configuration

After installation, the proxy is accessible at:
- **HTTPS**: `https://umbrel.local:8443/`
- **HTTP**: `http://umbrel.local:8080/` (redirects to HTTPS)

### Configuring App Routes

To route traffic to your apps, edit the Caddyfile:

```bash
# SSH into your Umbrel
ssh umbrel@umbrel.local

# Edit the Caddyfile
nano ~/umbrel/app-data/caddy-https-proxy/caddy/Caddyfile
```

Add routes for your apps:

```caddy
# Example: Route to Mempool app
handle /mempool* {
    reverse_proxy mempool_app_proxy:4000
}

# Example: Route to Nextcloud app
handle /nextcloud* {
    reverse_proxy nextcloud_app_proxy:4001
}

# Example: Route to Bitcoin RPC Explorer
handle /bitcoin* {
    reverse_proxy btc-rpc-explorer_web_1:3002
}
```

Then restart the app:

```bash
umbreld client apps.restart.mutate --appId caddy-https-proxy
```

### Accessing Apps

Once configured, access your apps securely:

```
https://umbrel.local:8443/mempool/
https://umbrel.local:8443/nextcloud/
https://umbrel.local:8443/bitcoin/
```

## 📱 Mobile Certificate Trust Guide

### Why Trust the Certificate?

Self-signed certificates are not automatically trusted by mobile operating systems. When you first access your Umbrel via HTTPS on mobile, you'll see a "Your connection is not private" warning. This is **normal and expected** for local network services.

**You have two options:**

1. **Accept the warning each time** (safe for local network use)
2. **Trust the certificate once** (eliminates warnings permanently)

### Step 1: Export the Certificate

First, download the certificate from your Umbrel:

```bash
# From your computer (not the Umbrel device)
scp umbrel@umbrel.local:~/umbrel/app-data/caddy-https-proxy/certs/umbrel.crt .
```

You now have `umbrel.crt` on your computer.

---

### iOS (iPhone/iPad)

#### Install the Certificate

1. **Send the certificate to your iOS device:**
   - Email `umbrel.crt` to yourself
   - Or use AirDrop from your Mac
   - Or upload to iCloud Drive and open from Files app

2. **Install the profile:**
   - Open the `umbrel.crt` file on your iOS device
   - Tap "Allow" when prompted
   - Go to **Settings → General → VPN & Device Management**
   - Tap "Install Profile" under "Downloaded Profile"
   - Enter your device passcode
   - Tap "Install" twice more

3. **Enable full trust:**
   - Go to **Settings → General → About**
   - Scroll down and tap **Certificate Trust Settings**
   - Under "Enable full trust for root certificates", find "Umbrel"
   - Toggle the switch to **ON**
   - Tap "Continue" → "Trust"

4. **Verify:**
   - Open Safari
   - Go to `https://umbrel.local:8443/`
   - The warning should be gone!

#### Troubleshooting iOS

- **Still seeing warnings?** Try:
  - Close and reopen Safari
  - Clear Safari history and website data
  - Restart your iOS device
  - Make sure you enabled **full trust** (not just installed)

- **Can't find Certificate Trust Settings?**
  - Make sure the profile is installed first
  - Go to Settings → General → About → scroll to bottom

---

### Android

#### Install the Certificate

1. **Transfer the certificate to your Android device:**
   - Connect your phone to your computer via USB
   - Copy `umbrel.crt` to your phone's Download folder
   - Or upload to Google Drive and download on phone

2. **Install the certificate:**
   - Open **Settings** on your Android device
   - Go to **Security** → **Encryption & Credentials**
   - Tap **Install a certificate** → **CA certificate**
   - Select "umbrel.crt" from your Downloads
   - Enter your device PIN/pattern/password
   - Tap **OK** to confirm

3. **Name the certificate:**
   - Enter a name like "Umbrel"
   - Tap **OK**

4. **Verify:**
   - Open Chrome or Firefox
   - Go to `https://umbrel.local:8443/`
   - The warning should be gone!

#### Android Version-Specific Instructions

**Android 11+:**
- Settings → Security & Privacy → Encryption & Credentials → Install from storage

**Android 10:**
- Settings → Security → Advanced → Encryption & Credentials → Install from storage

**Android 9 and below:**
- Settings → Security → Install from storage

#### Troubleshooting Android

- **Can't find the option?** Some manufacturers hide it:
  - Samsung: Settings → Biometrics and security → Other security settings
  - OnePlus: Settings → Security & lock screen → Advanced
  - Xiaomi: Settings → Passwords & security → Privacy → Special permissions

- **Still seeing warnings?** Try:
  - Clear browser cache and data
  - Try a different browser (Firefox often works better)
  - Restart your Android device

---

### 🖥️ Desktop Browsers (Optional)

While most desktop browsers will show a warning that you can bypass, you can also trust the certificate:

#### Windows

1. Double-click `umbrel.crt`
2. Click **Install Certificate**
3. Choose **Local Machine** → **Next**
4. Select **Place all certificates in the following store**
5. Click **Browse** → **Trusted Root Certification Authorities** → **OK**
6. Click **Next** → **Finish**

#### macOS

1. Double-click `umbrel.crt`
2. It opens in **Keychain Access**
3. Double-click the "Umbrel" certificate
4. Expand **Trust**
5. Set "When using this certificate" to **Always Trust**
6. Close the window (enter password if prompted)

#### Linux (Ubuntu/Debian)

```bash
# Copy certificate to trusted store
sudo cp umbrel.crt /usr/local/share/ca-certificates/
sudo update-ca-certificates
```

---

## 🔒 Certificate Management

### View Certificate Fingerprint

```bash
# Get certificate SHA256 fingerprint
openssl x509 -in ~/umbrel/app-data/caddy-https-proxy/certs/umbrel.crt \
  -noout -fingerprint -sha256
```

Compare this fingerprint with what your browser shows to ensure you're connecting to the correct server.

### Regenerate Certificates

If you need to regenerate certificates (e.g., changed domain or compromised):

```bash
# Delete existing certificates
rm ~/umbrel/app-data/caddy-https-proxy/certs/*

# Restart the app to trigger regeneration
umbreld client apps.restart.mutate --appId caddy-https-proxy
```

### Certificate Expiry

- **Validity Period**: 10 years from generation date
- **Renewal Reminder**: Web UI shows expiry date (future feature)
- **Auto-Renewal**: Not enabled by default (manual renewal recommended)

---

## 🏗️ Architecture

### Network Flow Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                    EXTERNAL NETWORK                          │
│                  (Your Local Network)                        │
│                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   Laptop    │  │   Mobile    │  │   Tablet    │         │
│  │  Browser    │  │   Browser   │  │   Browser   │         │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘         │
│         │                │                │                 │
│         └────────────────┴────────────────┘                 │
│                          │                                   │
│                          │ HTTPS (8444) or HTTP (8081)      │
│                          │                                   │
└──────────────────────────┼───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                   UMBREL DEVICE                              │
│                                                              │
│  ┌────────────────────────────────────────────────────┐     │
│  │              Caddy HTTPS Proxy                     │     │
│  │                                                    │     │
│  │  ┌─────────────┐    ┌──────────────┐              │     │
│  │  │   Caddy     │    │   Web UI     │              │     │
│  │  │   Proxy     │    │   Server     │              │     │
│  │  │  (80/443)   │    │   (8080)     │              │     │
│  │  └──────┬──────┘    └──────┬───────┘              │     │
│  │         │                  │                       │     │
│  └─────────┼──────────────────┼───────────────────────┘     │
│            │                  │ External Ports               │
│            │                  │                              │
│  ┌─────────▼──────────────────▼───────────────────────┐     │
│  │              app_proxy Container                   │     │
│  │         (Umbrel Authentication)                    │     │
│  │                  (Port 8080)                       │     │
│  └─────────────────────┬──────────────────────────────┘     │
│                        │                                     │
│                        │ Internal Docker Network             │
│                        │ (10.21.0.0/16)                      │
│  ┌─────────────────────┼──────────────────────────────┐     │
│  │                     │                              │     │
│  │  ┌──────────────────▼──────────┐                  │     │
│  │  │     App 1 Proxy             │                  │     │
│  │  │   (mempool_app_proxy:4000)  │                  │     │
│  │  └─────────────────────────────┘                  │     │
│  │                                                    │     │
│  │  ┌─────────────────────────────┐                  │     │
│  │  │     App 2 Proxy             │                  │     │
│  │  │   (nextcloud_app_proxy:4001)│                  │     │
│  │  └─────────────────────────────┘                  │     │
│  │                                                    │     │
│  │  ┌─────────────────────────────┐                  │     │
│  │  │     App 3 Proxy             │                  │     │
│  │  │   (btc-rpc-explorer:3002)   │                  │     │
│  │  └─────────────────────────────┘                  │     │
│  │                                                    │     │
│  │  ... (more apps as needed) ...                    │     │
│  └────────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────┘
```

### Port Assignment

```
EXTERNAL PORTS (Accessible from your network):
├─ 8081  → HTTP (redirects to HTTPS)
├─ 8444  → HTTPS (Caddy reverse proxy)
└─ 8080  → Web UI (configuration interface)

INTERNAL PORTS (Docker network only):
├─ 4000  → mempool_app_proxy
├─ 4001  → nextcloud_app_proxy
├─ 3002  → btc-rpc-explorer
└─ ...   → other app proxies
```

### Request Flow Example

```
User Browser (HTTPS)
    ↓
    │ Request: https://umbrel.local:8444/mempool/
    │
    ▼
Caddy Proxy (Port 8444)
    │ - TLS termination (decrypts HTTPS)
    │ - Checks security headers
    │ - Routes based on path (/mempool/*)
    │
    ▼
app_proxy (Port 8080)
    │ - Umbrel authentication check
    │ - Validates session token
    │
    ▼
mempool_app_proxy (Port 4000)
    │ - App-specific proxy
    │
    ▼
mempool_web container
    │ - Serves the actual web UI
    │
    ▼
Response flows back through the chain (encrypted)
```

---

## Advanced Configuration

### Custom Ports

Edit `exports.sh` before installation:

```bash
export APP_HTTP_PORT="8080"
export APP_HTTPS_PORT="8443"
```

### Custom Domain

The app automatically uses your Umbrel's domain (`umbrel.local`). To use a custom domain, edit the Caddyfile after installation:

```caddy
:8443 {
    tls /certs/umbrel.crt /certs/umbrel.key

    # Add your custom domain
    @customdomain host mydomain.local
    handle @customdomain {
        respond "Custom domain response" 200
    }
}
```

### WebSocket Support

Caddy automatically handles WebSocket upgrades. No additional configuration needed.

### Subdomain Routing

For subdomain-based routing (advanced):

```caddy
# Route mempool.umbrel.local to Mempool app
mempool.umbrel.local:8443 {
    tls /certs/umbrel.crt /certs/umbrel.key
    reverse_proxy mempool_app_proxy:4000
}
```

---

## Troubleshooting

### Browser Shows Certificate Warning

This is **expected** for self-signed certificates. To proceed:

1. Click "Advanced" or "Details"
2. Click "Proceed to site" or "Accept risk"

This is normal and safe for local network use.

**To eliminate warnings permanently**, see the [Mobile Certificate Trust Guide](#-mobile-certificate-trust-guide) above.

### App Not Accessible

1. **Check if Caddy is running**:
   ```bash
   docker ps | grep caddy
   ```

2. **Check Caddy logs**:
   ```bash
   docker logs umbrel-caddy-https-app_caddy_1
   ```

3. **Verify route configuration**:
   ```bash
   cat ~/umbrel/app-data/caddy-https-proxy/caddy/Caddyfile
   ```

4. **Test connectivity**:
   ```bash
   curl -k https://umbrel.local:8443/
   ```

### Port Conflicts

If ports 8080 or 8443 are already in use:

1. Uninstall the app
2. Edit `exports.sh` to use different ports
3. Reinstall the app

### Certificate Errors

If certificates are invalid or expired:

```bash
# Regenerate certificates
rm ~/umbrel/app-data/caddy-https-proxy/certs/*
umbreld client apps.restart.mutate --appId caddy-https-proxy
```

### Mobile Can't Connect

1. **Ensure same network**: Mobile and Umbrel must be on the same WiFi network
2. **Check firewall**: Make sure ports 8081 and 8444 are not blocked
3. **Try IP address**: Use `https://192.168.1.XXX:8444/` instead of domain
4. **Clear browser cache**: On mobile, clear browser cache and try again

---

## Security Considerations

### Self-Signed Certificates

**Pros:**
- Easy setup, no external dependencies
- Provides encryption on local network
- Standard practice for local services

**Cons:**
- Browser warnings (can be eliminated by trusting)
- Manual trust required per device
- Not valid for public internet

### Network Security

- All client-to-server traffic is encrypted
- Internal Docker network traffic remains unencrypted (trusted)
- HSTS prevents protocol downgrade attacks
- Security headers protect against common web vulnerabilities

### Best Practices

1. **Trust the certificate** on all your devices to eliminate warnings
2. **Verify the fingerprint** matches what's shown in the app
3. **Use strong passwords** for your Umbrel account
4. **Keep Umbrel updated** for security patches
5. **Regularly check** certificate expiry (every few years)

---

## Technical Details

### Container Architecture

```
┌─────────────────────┐
│  app_proxy          │ ← Umbrel auth proxy
│  (port 8080)        │
└─────────────────────┘
         │
┌─────────────────────┐
│  caddy              │ ← HTTPS reverse proxy
│  (ports 8081, 8444) │
└─────────────────────┘
         │
┌─────────────────────┐
│  web                │ ← Node.js Web UI
│  (port 8080)        │
└─────────────────────┘
```

### Files

- `docker-compose.yml` - Container configuration
- `umbrel-app.yml` - App manifest
- `Caddyfile.template` - Caddy configuration template
- `exports.sh` - Environment variables
- `scripts/post-install.sh` - Setup script
- `scripts/pre-start.sh` - Pre-start configuration

### Data Storage

- **Certificates**: `~/umbrel/app-data/caddy-https-proxy/certs/`
- **Configuration**: `~/umbrel/app-data/caddy-https-proxy/caddy/`
- **Web UI**: `~/umbrel/app-data/caddy-https-proxy/web/`

---

## Development

### Local Testing

1. Clone the repository
2. Start with Docker Compose:
   ```bash
   docker compose up
   ```
3. Access at `https://localhost:8443/`

### Building Docker Image

```bash
docker build -t caddy-https-proxy .
```

---

## Contributing

Contributions are welcome! Please submit issues and pull requests to the main Umbrel apps repository.

### Areas for Contribution

- [ ] Mobile certificate trust automation
- [ ] mkcert integration for trusted certs
- [ ] Certificate expiry notifications
- [ ] Dark mode for Web UI
- [ ] Additional language support
- [ ] Performance optimizations

---

## License

Part of the Umbrel project. See main repository for license information.

## Support

- **Issues**: [GitHub Issues](https://github.com/getumbrel/umbrel-apps/issues)
- **Documentation**: [Umbrel Docs](https://github.com/getumbrel/umbrel-apps#readme)
- **Community**: [Umbrel Community Forum](https://community.umbrel.com/)
- **Discord**: [Umbrel Discord](https://discord.gg/umbrel)

---

**Made with ❤️ for the Umbrel Community**
