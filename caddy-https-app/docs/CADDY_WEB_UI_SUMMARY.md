# Caddy HTTPS Proxy - Web UI Added! 🎨

## What's New

A beautiful, **minimal, flat, pastel-colored** web interface has been added to the Caddy HTTPS Proxy app!

---

## 🎨 Design Philosophy

### Minimal
- Clean, uncluttered interface
- Only essential controls visible
- No complex menus or navigation

### Flat
- Modern vector icons
- No shadows or gradients (except subtle ones)
- Clean typography

### Pastel Colors
- 🌸 Soft pink backgrounds
- 💙 Calming blue accents
- 💚 Gentle green success states
- 💜 Purple info elements
- 💛 Warm yellow highlights

---

## 📱 Features

### 1. Status Dashboard
Real-time monitoring of:
- Proxy status (Running/Stopped with animated indicator)
- HTTPS port configuration
- HTTP port configuration  
- Current domain name

### 2. Configuration Management

#### Basic Settings Tab
- **Domain**: Change from umbrel.local to custom domain
- **HTTPS Port**: Configure secure access port
- **HTTP Port**: Configure redirect port

#### App Routes Tab
- **Caddyfile Editor**: Full text editor for advanced configuration
- **Example Routes**: One-click load example configurations
- Syntax-friendly monospace font

#### Advanced Settings Tab
- **Force HTTPS**: Toggle HTTP→HTTPS redirect
- **HSTS**: Enable/disable Strict-Transport-Security
- Warning indicators for important settings

### 3. Certificate Management
- View certificate status
- Check validity period
- **Regenerate Certificate** button
- Certificate type display

### 4. App Control
- **Save Configuration**: Apply changes
- **Restart App**: Restart Caddy with new config
- **Regenerate Certs**: Create new SSL certificates

---

## 🖥️ Screenshots

### Main Interface
```
┌─────────────────────────────────────────┐
│  🌈 Caddy HTTPS Proxy                   │
│  Secure your Umbrel apps with HTTPS    │
├─────────────────────────────────────────┤
│  ✅ Status                              │
│  ┌─────────┬─────────┬─────────┬─────┐ │
│  │ Running │ HTTPS   │ HTTP    │Dom. │ │
│  │   ●     │  8443   │  8080   │umb. │ │
│  └─────────┴─────────┴─────────┴─────┘ │
├─────────────────────────────────────────┤
│  ⚙️ Configuration                        │
│  [Basic] [Routes] [Advanced]            │
│                                         │
│  Domain: [umbrel.local________]         │
│  HTTPS Port: [8443___]                  │
│  HTTP Port: [8080___]                   │
│                                         │
│  [💾 Save] [🔄 Restart]                 │
└─────────────────────────────────────────┘
```

---

## 🔧 Technical Implementation

### Architecture

```
┌─────────────┐
│  Browser    │
│  (Client)   │
└──────┬──────┘
       │ HTTP
       │
┌──────▼──────┐
│  Node.js    │
│  Web Server │
│  (Port 8080)│
└──────┬──────┘
       │
       │ API Calls
       │
┌──────▼──────┐
│  Caddy      │
│  Proxy      │
└─────────────┘
```

### Files Added

1. **web/index.html** (1,100+ lines)
   - All-in-one HTML/CSS/JS
   - No external dependencies
   - Responsive design
   - Pastel color scheme

2. **web/server.js** (350+ lines)
   - Node.js HTTP server
   - REST API implementation
   - Configuration management
   - Docker integration

3. **web/start.sh**
   - Startup script
   - Dependency installation
   - Server launch

4. **web/README.md**
   - Complete documentation
   - API reference
   - Troubleshooting guide

### Updated Files

1. **docker-compose.yml**
   - Added `web` service
   - Node.js 18 container
   - Port 8080 exposure
   - Volume mounts for config

2. **umbrel-app.yml**
   - Changed port to 8080 (web UI port)

---

## 🚀 Usage

### Access the Web UI

1. **Through Umbrel Dashboard**:
   - Click on Caddy HTTPS Proxy app icon
   - Web UI opens automatically

2. **Direct Access**:
   ```
   http://umbrel.local:8080/
   ```

3. **Via IP**:
   ```
   http://192.168.1.XXX:8080/
   ```

### Configure Settings

1. **Basic Configuration**:
   - Navigate to **Configuration** → **Basic** tab
   - Change domain, ports
   - Click **Save Configuration**

2. **Add App Routes**:
   - Go to **Configuration** → **Routes** tab
   - Click **Load Example Routes**
   - Edit routes as needed
   - Click **Save Configuration**

3. **Advanced Settings**:
   - Navigate to **Configuration** → **Advanced** tab
   - Toggle Force HTTPS
   - Enable/disable HSTS
   - Click **Save Configuration**

### Restart App

After making configuration changes:

1. Click **Restart App** button
2. Confirm the restart
3. Wait for modal to complete (~5 seconds)
4. Configuration is now active!

### Regenerate Certificate

1. Scroll to **SSL Certificate** card
2. Click **Regenerate Certificate**
3. Confirm the action
4. New certificate generated in ~3 seconds

---

## 🎨 Color Palette

### Background Colors
```css
--bg-pink:   #fdf2f8  /* Light pink */
--bg-blue:   #f0f9ff  /* Light blue */
--bg-purple: #f5f3ff  /* Light purple */
```

### Accent Colors
```css
--blue:  #bae6fd → #7dd3fc  /* Info icons */
--green: #bbf7d0 → #86efac  /* Success states */
--purple:#e9d5ff → #d8b4fe  /* Info elements */
--pink:  #fbcfe8 → #f9a8d4  /* Accent elements */
--yellow:#fbbf24 → #f59e0b  /* Logo, warnings */
```

### Primary Actions
```css
--primary: #a5b4fc → #818cf8  /* Purple gradient */
--danger:  #fda4af → #fb7185  /* Red gradient */
```

---

## 📱 Responsive Design

### Desktop (> 640px)
- Full-width cards
- Side-by-side buttons
- Multi-column info grid

### Mobile (< 640px)
- Stacked layout
- Full-width buttons
- Single-column info grid
- Touch-friendly sizing

---

## 🔌 API Reference

### GET /api/config
Get current configuration

**Response:**
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
Save configuration

**Request:**
```json
{
  "domain": "umbrel.local",
  "httpsPort": 8443,
  "httpPort": 8080,
  "forceHttps": true,
  "hsts": true,
  "caddyfile": "handle /app* {\n  reverse_proxy app:3000\n}"
}
```

**Response:**
```json
{
  "success": true
}
```

### GET /api/status
Get app status

**Response:**
```json
{
  "running": true,
  "status": "running"
}
```

### POST /api/restart
Restart Caddy container

**Response:**
```json
{
  "success": true
}
```

### POST /api/certificate
Regenerate SSL certificate

**Response:**
```json
{
  "success": true
}
```

---

## 🎯 User Experience

### Loading States
- Spinner animation during restart
- Modal overlay for long operations
- Status updates in real-time

### Notifications
- Success notifications (green)
- Error notifications (red)
- Warning notifications (yellow)
- Auto-dismiss after 5 seconds

### Interactions
- Hover effects on buttons
- Tab switching animations
- Smooth transitions
- Pulse animation on status dot

---

## 🔒 Security Notes

### Current Implementation
- No authentication (local network only)
- CORS enabled for flexibility
- No rate limiting

### Recommendations for Production
1. Add password authentication
2. Implement rate limiting
3. Add HTTPS for web UI itself
4. Session management
5. CSRF protection

---

## 🐛 Troubleshooting

### Web UI Not Loading

**Problem**: Page doesn't load

**Solution**:
```bash
# Check if web container is running
docker ps | grep web

# View logs
docker logs umbrel-caddy-https-app_web_1

# Restart container
docker restart umbrel-caddy-https-app_web_1
```

### Configuration Not Saving

**Problem**: Changes don't persist

**Solution**:
```bash
# Check permissions
docker exec umbrel-caddy-https-app_web_1 ls -la /data

# Verify disk space
df -h
```

### API Not Responding

**Problem**: API calls fail

**Solution**:
```bash
# Check Node.js process
docker exec umbrel-caddy-https-app_web_1 ps aux

# Restart web server
docker restart umbrel-caddy-https-app_web_1
```

---

## 🚀 Future Enhancements

### Short-term
- [ ] Add authentication
- [ ] Real-time log viewer
- [ ] Certificate expiry warning
- [ ] Dark mode toggle

### Medium-term
- [ ] WebSocket for live updates
- [ ] Backup/restore config
- [ ] Export/import settings
- [ ] Mobile app

### Long-term
- [ ] Plugin system
- [ ] Custom themes
- [ ] Multi-language support
- [ ] Analytics dashboard

---

## 📊 Stats

- **Lines of Code**: ~1,500
- **HTML/CSS**: ~1,100 lines
- **JavaScript**: ~350 lines
- **Components**: 4 cards, 3 tabs, 6 buttons
- **API Endpoints**: 5
- **Colors**: 8 pastel shades
- **Icons**: 12 SVG icons

---

## ✅ Testing Checklist

- [x] Responsive design (mobile/desktop)
- [x] Tab switching
- [x] Configuration save/load
- [x] App restart functionality
- [x] Certificate regeneration
- [x] Error handling
- [x] Loading states
- [x] Notifications
- [x] API integration
- [x] Docker integration

---

## 🎉 Conclusion

The Caddy HTTPS Proxy now has a **beautiful, intuitive web interface** that makes managing your HTTPS configuration as simple as clicking a few buttons!

### Key Benefits

✅ **User-Friendly**: No command-line needed
✅ **Beautiful Design**: Pastel colors, minimal aesthetic
✅ **Full Control**: Configure everything from browser
✅ **Real-time**: See status and changes immediately
✅ **Mobile-Ready**: Works on any device

---

**Status**: ✅ Complete and Ready to Use
**Version**: 1.0.0
**Design**: Minimal, Flat, Pastel
**License**: Same as Umbrel project
