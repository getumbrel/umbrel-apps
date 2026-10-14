# LanCache for Umbrel

This package integrates the official [LanCache.NET](https://lancache.net) game download and update caching proxy into the Umbrel App Store, fully compliant with **umbrelOS 2.0** packaging standards.

---

## Overview

[LanCache](https://lancache.net) is a high-performance local caching proxy server designed for home networks, multi-PC households, and LAN parties. When someone on your network downloads a game or patch from **Steam, Epic Games, Riot, Battle.net, EA App, PlayStation, Xbox, or Windows Update**, LanCache stores a local copy.

When any other device on your network requests the same game or update, LanCache delivers it at full local network wire speed (1 Gbps / 2.5 Gbps / 10 Gbps), eliminating repeated multi-gigabyte internet downloads and saving bandwidth.

---

## Package Architecture

```text
lancache/
├── umbrel-app.yml       # App Store manifest adhering to umbrelOS 2.0 schema & App Settings
├── docker-compose.yml   # Multi-service Compose file (app_proxy, web, monolithic, dns)
├── index.html.template  # Web dashboard template (envsubst-rendered with setup guide)
├── nginx.conf.template  # Nginx reverse proxy configuration template
├── exports.sh           # Safe environment variable defaults
├── hooks/
│   └── pre-start        # Lifecycle hook ensuring data and rendered files exist
├── data/
│   ├── cache/
│   │   └── .gitkeep     # Persistent cache storage scaffolding
│   └── logs/
│       └── .gitkeep     # Persistent log directory scaffolding
└── README.md            # App overview, configuration guide, and PR submission
```

---

## Services Topology

| Service | Image | Description |
| :--- | :--- | :--- |
| `app_proxy` | N/A (umbrelOS virtual proxy) | Routes browser traffic on host port `8260` to `lancache_web_1:80` with Umbrel authentication. |
| `web` | `nginx:1.27.4-alpine` | Lightweight static web dashboard displaying cache configuration, status, and network setup guides. |
| `monolithic` | `lancachenet/monolithic:latest` | Core caching engine that intercepts HTTP/HTTPS game chunks and stores them locally on disk. |
| `dns` | `lancachenet/lancache-dns:latest` | Specialized DNS resolver on port `53` (UDP/TCP) that redirects game CDN domains to your `LANCACHE_IP`. |

---

## Quick Start Configuration

### 1. Set Your Server IP in Umbrel Settings
1. Open your Umbrel dashboard.
2. Go to **App Store &rarr; LanCache &rarr; Settings** (or click the Settings gear icon on the LanCache app card).
3. Set `LANCACHE_IP` to your Umbrel server's actual local IP address on your home network (e.g. `192.168.1.50`).
4. Set `CACHE_DISK_SIZE` to your desired cache allocation (e.g. `500g`, `1000g`, or `2000g`).
5. Click **Save** to restart the containers with your configuration.

### 2. Point Client DNS to LanCache
For games to route through the cache, client devices must use your Umbrel server as their primary DNS:
- **Whole Network (Recommended):** Log into your home router's management page, navigate to **DHCP / LAN Settings**, and set the **Primary DNS Server** to your Umbrel server's IP address (`LANCACHE_IP`).
- **Single Computer Testing:** On Windows, Mac, or Linux, change your IPv4 DNS settings to point directly to your Umbrel server's IP address.

### 3. Verify DNS Redirection
Open a terminal or command prompt on your gaming PC and run:
```bash
nslookup lancache.steamcontent.com
```
The response should return your Umbrel server's local IP address!

### 4. Test Game Caching
1. Start downloading a game or update on Steam or another supported launcher on PC 1.
2. Once complete, start downloading the same game on PC 2.
3. PC 2 will download directly from your Umbrel server at full LAN wire speed!

---

## Umbrel Port 80 Routing Note

Game launchers (such as Steam) issue chunk downloads over standard HTTP port `80`. Because Umbrel's web dashboard listens on port `80` by default, this package maps the monolithic caching service to port `8261:80` out of the box so that Umbrel starts cleanly without port conflicts.

To transparently route incoming port `80` traffic to LanCache on Umbrel:
- **Option A (Router NAT Port Forward):** In your home router, add a NAT redirection rule that routes incoming LAN requests destined for port `80` on your Umbrel IP to port `8261`.
- **Option B (Secondary Host IP Alias):** Assign an alias IP to your server's network card (e.g. `ip addr add 192.168.1.51/24 dev eth0`) and map the container directly to that secondary IP.

---

## Submitting to the Umbrel App Store (`getumbrel/umbrel-apps`)

To submit this app for official inclusion in the Umbrel App Store:

### 1. Fork and Clone `getumbrel/umbrel-apps`
```bash
git clone https://github.com/<your-username>/umbrel-apps.git
cd umbrel-apps
git checkout -b add-lancache
```

### 2. Copy the `lancache` Package
```bash
cp -r "/path/to/lancache" ./lancache
```

### 3. Run the Official Linter
```bash
npm install
npm run lint:apps -- lancache --check-images
git diff --check
```

### 4. Commit and Push
```bash
git add lancache
git commit -m "Add LanCache app"
git push origin add-lancache
```

### 5. Open a Pull Request
Open a Pull Request against `getumbrel/umbrel-apps:master`.
