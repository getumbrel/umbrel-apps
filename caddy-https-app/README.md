# Caddy HTTPS Proxy for Umbrel

🔒 **Add automatic HTTPS encryption to your Umbrel server**

Caddy HTTPS Proxy is a reverse proxy app for Umbrel that provides HTTPS support for all your self-hosted apps. It protects against man-in-the-middle attacks on untrusted local networks by encrypting all traffic between your devices and your Umbrel server.

## Features

- ✅ **Automatic HTTPS** - Self-signed certificates generated on install
- ✅ **HTTP → HTTPS Redirect** - Seamless upgrade for all connections
- ✅ **Security Headers** - HSTS, X-Frame-Options, X-Content-Type-Options
- ✅ **Zero Configuration** - Works out of the box
- ✅ **Dynamic Routing** - Easy to configure for multiple apps
- ✅ **Certificate Management** - Simple certificate regeneration

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

## Certificate Management

### View Certificate Fingerprint

```bash
# Get certificate SHA256 fingerprint
openssl x509 -in ~/umbrel/app-data/caddy-https-proxy/certs/umbrel.crt \
  -noout -fingerprint -sha256
```

### Regenerate Certificates

If you need to regenerate certificates (e.g., changed domain):

```bash
# Delete existing certificates
rm ~/umbrel/app-data/caddy-https-proxy/certs/*

# Restart the app to trigger regeneration
umbreld client apps.restart.mutate --appId caddy-https-proxy
```

### Trust the Certificate (Optional)

To eliminate browser warnings, trust the certificate on your devices:

1. Export the certificate from your Umbrel:
   ```bash
   scp umbrel@umbrel.local:~/umbrel/app-data/caddy-https-proxy/certs/umbrel.crt .
   ```

2. Import `umbrel.crt` into your OS/browser's trusted certificate authorities

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

## Troubleshooting

### Browser Shows Certificate Warning

This is **expected** for self-signed certificates. To proceed:

1. Click "Advanced" or "Details"
2. Click "Proceed to site" or "Accept risk"

This is normal and safe for local network use.

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

## Security Considerations

### Self-Signed Certificates

- **Pros**: Easy setup, no external dependencies, provides encryption
- **Cons**: Browser warnings, manual trust required per device

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

## Technical Details

### Architecture

```
┌─────────────────┐
│   Browser       │
│  (HTTPS)        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Caddy Proxy    │
│  (Port 8443)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Umbrel Apps    │
│  (HTTP)         │
└─────────────────┘
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

## Contributing

Contributions are welcome! Please submit issues and pull requests to the main Umbrel apps repository.

## License

Part of the Umbrel project. See main repository for license information.

## Support

- **Issues**: [GitHub Issues](https://github.com/getumbrel/umbrel-apps/issues)
- **Documentation**: [Umbrel Docs](https://github.com/getumbrel/umbrel-apps#readme)
- **Community**: [Umbrel Community Forum](https://community.umbrel.com/)

---

**Made with ❤️ for the Umbrel Community**
