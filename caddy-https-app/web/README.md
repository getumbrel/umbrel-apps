# Caddy HTTPS Proxy - Web UI

🎨 **Beautiful, pastel-colored web interface for managing your Caddy HTTPS Proxy**

## Features

- 🌈 **Minimal, flat, pastel design** - Easy on the eyes
- ⚙️ **Configuration Management** - Change ports, domain, and routing
- 🔄 **App Restart** - Restart Caddy with new configuration
- 📜 **Certificate Management** - Regenerate SSL certificates
- 📊 **Real-time Status** - Monitor proxy status
- 🎯 **App Routes** - Configure which apps are accessible via HTTPS

## Access

Once installed, access the web UI at:

```
http://umbrel.local:8080/
```

Or through the Umbrel dashboard by clicking on the Caddy HTTPS Proxy app icon.

## Sections

### Status Card
- Shows current proxy status (Running/Stopped)
- Displays configured ports (HTTP/HTTPS)
- Shows current domain

### Configuration Card

#### Basic Settings Tab
- **Domain**: Your Umbrel server domain (default: umbrel.local)
- **HTTPS Port**: Secure access port (default: 8443)
- **HTTP Port**: Redirect port (default: 8080)

#### App Routes Tab
- Edit Caddyfile configuration
- Load example routes with one click
- Configure reverse proxy for your apps

#### Advanced Settings Tab
- Force HTTPS redirect toggle
- HSTS (Strict-Transport-Security) toggle
- Security warnings and info

### SSL Certificate Card
- View certificate status
- Check certificate type and validity
- Regenerate certificates button

## API Endpoints

The web UI provides a REST API for programmatic access:

### GET /api/config
Get current configuration

```json
{
  "domain": "umbrel.local",
  "httpsPort": 8443,
  "httpPort": 8080,
  "forceHttps": true,
  "hsts": true,
  "caddyfile": ""
}
```

### POST /api/config
Save new configuration

```bash
curl -X POST http://localhost:8080/api/config \
  -H "Content-Type: application/json" \
  -d '{"domain":"umbrel.local","httpsPort":8443}'
```

### GET /api/status
Get app status

```json
{
  "running": true,
  "status": "running"
}
```

### POST /api/restart
Restart the Caddy container

### POST /api/certificate
Regenerate SSL certificates

## Design Philosophy

The UI follows a **minimal, flat, pastel** design philosophy:

- **Minimal**: Clean interface with only essential controls
- **Flat**: No skeuomorphic elements, clean vectors
- **Pastel**: Soft, calming colors that are easy on the eyes

### Color Palette

- 🌸 **Pink**: `#fdf2f8` - Background gradients
- 💙 **Blue**: `#bae6fd` - Icon backgrounds
- 💚 **Green**: `#bbf7d0` - Success states
- 💜 **Purple**: `#e9d5ff` - Info elements
- 💛 **Yellow**: `#fbbf24` - Logo and warnings
- 🩷 **Pink**: `#fbcfe8` - Accent elements

## Technical Details

### Architecture

```
┌──────────────┐
│   Browser    │
│   (Web UI)   │
└──────┬───────┘
       │
       │ HTTP/8080
       │
┌──────▼───────┐
│  Node.js     │
│  Web Server  │
└──────┬───────┘
       │
       │ API Calls
       │
┌──────▼───────┐
│   Caddy      │
│   Proxy      │
└──────────────┘
```

### Files

- `index.html` - Main UI (all-in-one HTML/CSS/JS)
- `server.js` - Node.js API server
- `start.sh` - Startup script

### Dependencies

- Node.js 18+
- No external NPM packages (uses built-in modules only)

## Customization

### Change Port

Edit `docker-compose.yml`:

```yaml
environment:
  WEB_PORT: "9000"  # Change to desired port
```

### Add Custom CSS

Create `web/custom.css` and include in `index.html`:

```html
<link rel="stylesheet" href="custom.css">
```

### Modify Colors

Edit the CSS variables in `index.html`:

```css
:root {
  --pastel-pink: #fdf2f8;
  --pastel-blue: #bae6fd;
  /* etc */
}
```

## Troubleshooting

### Web UI Not Loading

1. **Check if web container is running**:
   ```bash
   docker ps | grep web
   ```

2. **Check logs**:
   ```bash
   docker logs umbrel-caddy-https-app_web_1
   ```

3. **Verify port mapping**:
   ```bash
   docker port umbrel-caddy-https-app_web_1
   ```

### API Not Responding

1. **Restart web container**:
   ```bash
   docker restart umbrel-caddy-https-app_web_1
   ```

2. **Check Node.js process**:
   ```bash
   docker exec umbrel-caddy-https-app_web_1 ps aux
   ```

### Configuration Not Saving

1. **Check permissions**:
   ```bash
   docker exec umbrel-caddy-https-app_web_1 ls -la /data
   ```

2. **Verify disk space**:
   ```bash
   df -h
   ```

## Security Notes

- Web UI runs on local network only
- No authentication by default (accessible to anyone on your network)
- Consider adding authentication for production use
- API endpoints are not rate-limited

## Future Enhancements

- [ ] Add authentication to web UI
- [ ] Real-time log viewing
- [ ] Certificate expiry notifications
- [ ] Backup/restore configuration
- [ ] Dark mode toggle
- [ ] Mobile responsive improvements
- [ ] WebSocket for live status updates

## License

Part of the Caddy HTTPS Proxy for Umbrel. Same license as main project.

---

**Made with 💜 for the Umbrel Community**
