# Caddy HTTPS Proxy - App-Based Approach

## Overview

This directory contains an alternative implementation of the Caddy HTTPS proxy as a **standalone Umbrel app** that can be installed from the Umbrel App Store. This approach follows the official [Umbrel App Framework](https://github.com/getumbrel/umbrel-apps) and provides HTTPS support without modifying the core umbrelOS system.

## 🎯 Use Case

This app-based approach is ideal for:

- **Immediate deployment** - No need to wait for core OS updates
- **User choice** - Users can opt-in to HTTPS support
- **Easy updates** - Updates through the normal app update mechanism
- **Community contribution** - Can be submitted to the official app store
- **Testing ground** - Validate the concept before integrating into core OS

## 📁 Directory Structure

```
caddy-https-app/
├── docker-compose.yml          # Docker container configuration
├── umbrel-app.yml              # App manifest for Umbrel
├── exports.sh                  # Environment variable exports
├── Caddyfile.template          # Caddy configuration template
├── README.md                   # User documentation
├── scripts/
│   ├── post-install.sh         # Setup after installation
│   └── pre-start.sh            # Configuration before each start
└── (data directories created at runtime)
    ├── caddy/                  # Caddy configuration
    └── certs/                  # SSL certificates
```

## 🔧 Installation

### Method 1: Local Testing

1. **Copy to Umbrel app store**:
   ```bash
   rsync -av --exclude=".gitkeep" caddy-https-app \
     umbrel@umbrel.local:/home/umbrel/umbrel/app-stores/
   ```

2. **Install via Umbrel UI**:
   - Go to App Store
   - Find "Caddy HTTPS Proxy"
   - Click Install

3. **Or install via CLI**:
   ```bash
   umbreld client apps.install.mutate --appId caddy-https-proxy
   ```

### Method 2: Submit to App Store

1. **Fork the umbrel-apps repository**:
   ```bash
   git clone https://github.com/your-username/umbrel-apps.git
   cd umbrel-apps
   ```

2. **Copy the app**:
   ```bash
   cp -r ../umbrel/caddy-https-app ./
   ```

3. **Commit and push**:
   ```bash
   git add caddy-https-app
   git commit -m "Add Caddy HTTPS Proxy app"
   git push
   ```

4. **Create Pull Request** on [getumbrel/umbrel-apps](https://github.com/getumbrel/umbrel-apps)

## 🚀 Features

### Automatic Certificate Generation

On installation, the app automatically generates self-signed certificates:
- 2048-bit RSA encryption
- SHA-256 signatures
- 10-year validity
- SAN entries for domain and IP

### HTTP to HTTPS Redirect

All HTTP traffic is automatically redirected to HTTPS:
```
http://umbrel.local:8080/ → https://umbrel.local:8443/
```

### Security Headers

Every response includes security headers:
```
Strict-Transport-Security: max-age=31536000; includeSubDomains
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
```

### Dynamic App Routing

Easily configure routes to your apps by editing the Caddyfile:
```caddy
handle /mempool* {
    reverse_proxy mempool_app_proxy:4000
}

handle /nextcloud* {
    reverse_proxy nextcloud_app_proxy:4001
}
```

## 📖 Configuration

### Default Ports

- **HTTP**: 8080 (redirects to HTTPS)
- **HTTPS**: 8443 (secure access)

To change ports, edit `exports.sh` before installation:
```bash
export APP_HTTP_PORT="8081"
export APP_HTTPS_PORT="8444"
```

### Custom Domain

The app uses your Umbrel's domain by default (`umbrel.local`).

### Adding App Routes

1. **SSH into your Umbrel**:
   ```bash
   ssh umbrel@umbrel.local
   ```

2. **Edit the Caddyfile**:
   ```bash
   nano ~/umbrel/app-data/caddy-https-proxy/caddy/Caddyfile
   ```

3. **Add routes for your apps**:
   ```caddy
   # Mempool
   handle /mempool* {
       reverse_proxy mempool_app_proxy:4000
   }
   
   # Nextcloud
   handle /nextcloud* {
       reverse_proxy nextcloud_app_proxy:4001
   }
   
   # Bitcoin RPC Explorer
   handle /bitcoin* {
       reverse_proxy btc-rpc-explorer_web_1:3002
   }
   ```

4. **Restart the app**:
   ```bash
   umbreld client apps.restart.mutate --appId caddy-https-proxy
   ```

5. **Access apps securely**:
   ```
   https://umbrel.local:8443/mempool/
   https://umbrel.local:8443/nextcloud/
   https://umbrel.local:8443/bitcoin/
   ```

## 🔒 Security

### Certificate Trust

The app uses self-signed certificates, which will show browser warnings. This is **expected and safe** for local network use.

To eliminate warnings:

1. **Export the certificate**:
   ```bash
   scp umbrel@umbrel.local:~/umbrel/app-data/caddy-https-proxy/certs/umbrel.crt .
   ```

2. **Import into your OS/browser**:
   - **Windows**: Double-click → Install Certificate → Trusted Root Certification Authorities
   - **macOS**: Double-click → Add to Keychain → Trust
   - **Linux**: Add to `/usr/local/share/ca-certificates/` and run `update-ca-certificates`
   - **Firefox/Chrome**: Settings → Privacy & Security → Certificates → View Certificates → Import

3. **Verify fingerprint** (optional but recommended):
   ```bash
   # On Umbrel
   openssl x509 -in ~/umbrel/app-data/caddy-https-proxy/certs/umbrel.crt \
     -noout -fingerprint -sha256
   
   # Compare with what your browser shows
   ```

## 🐛 Troubleshooting

### Browser Shows "Your Connection Is Not Private"

This is **normal** for self-signed certificates.

**Solution**: Click "Advanced" → "Proceed to site"

### App Routes Not Working

1. **Check Caddyfile syntax**:
   ```bash
   docker exec umbrel-caddy-https-app_caddy_1 \
     caddy validate --config /config/Caddyfile
   ```

2. **Check Caddy logs**:
   ```bash
   docker logs umbrel-caddy-https-app_caddy_1
   ```

3. **Verify app proxy ports**:
   ```bash
   docker ps | grep app_proxy
   ```

### Port Already in Use

**Error**: `bind: address already in use`

**Solution**: Change ports in `exports.sh` and reinstall:
```bash
export APP_HTTP_PORT="8081"
export APP_HTTPS_PORT="8444"
```

### Certificates Expired

Certificates are valid for 10 years, but if you need to regenerate:

```bash
# Delete old certificates
rm ~/umbrel/app-data/caddy-https-proxy/certs/*

# Restart app
umbreld client apps.restart.mutate --appId caddy-https-proxy
```

## 📊 Comparison: App vs Core Integration

| Feature | App Approach | Core Integration |
|---------|-------------|------------------|
| **Deployment** | Immediate | Requires OS update |
| **User Choice** | Opt-in | System-wide |
| **Updates** | App store | OS updates |
| **Complexity** | Low | High |
| **Maintenance** | Community | Core team |
| **Testing** | Easy | Requires full OS test |
| **Adoption** | Gradual | Universal |

## 🎯 Next Steps

### For Users

1. Install the app from the app store
2. Configure routes for your apps
3. Access apps via HTTPS
4. Trust the certificate on your devices

### For Developers

1. Test the app thoroughly
2. Submit to umbrel-apps repository
3. Gather community feedback
4. Iterate based on usage patterns

### For Umbrel Team

1. Review the app implementation
2. Consider for official app store inclusion
3. Evaluate for future core integration
4. Provide feedback to community

## 🤝 Contributing

This app follows the official [Umbrel App Framework](https://github.com/getumbrel/umbrel-apps).

To contribute:
1. Fork the repository
2. Make improvements
3. Test on your Umbrel
4. Submit a pull request

## 📚 Resources

- [Umbrel App Framework Documentation](https://github.com/getumbrel/umbrel-apps#readme)
- [Caddy Documentation](https://caddyserver.com/docs/)
- [Umbrel Community Forum](https://community.umbrel.com/)
- [Umbrel Developer Discord](https://discord.gg/umbrel)

## ⚡ Quick Start

```bash
# Install
umbreld client apps.install.mutate --appId caddy-https-proxy

# Configure routes (edit Caddyfile)
ssh umbrel@umbrel.local
nano ~/umbrel/app-data/caddy-https-proxy/caddy/Caddyfile

# Restart
umbreld client apps.restart.mutate --appId caddy-https-proxy

# Access
open https://umbrel.local:8443/
```

---

**Status**: Ready for Testing & Submission  
**Version**: 1.0.0  
**License**: Same as Umbrel project
