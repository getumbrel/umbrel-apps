# Twingate for Umbrel

This package integrates the official [Twingate](https://www.twingate.com) Zero Trust Network Access (ZTNA) Connector into the Umbrel App Store, fully compliant with **umbrelOS 2.0** packaging standards.

---

## Overview

[Twingate](https://www.twingate.com) provides modern Zero Trust Network Access (ZTNA) to securely connect to your Umbrel server, self-hosted services, and private network from anywhere in the world—without port forwarding, opening firewall pinholes, or exposing public IP addresses.

### Highlights
- **Zero Port Forwarding**: The connector establishes secure, outbound-only TLS and QUIC tunnels to Twingate's global relay network.
- **Modern Zero Trust Access**: Control access per user, device, and service with granular least-privilege security policies.
- **Native Web Dashboard**: Built-in responsive web dashboard accessible directly from the Umbrel home screen, providing connection status, live Prometheus activity metrics, and step-by-step onboarding.
- **Native umbrelOS 2.0 App Settings**: Configure `TWINGATE_NETWORK`, `TWINGATE_ACCESS_TOKEN`, and `TWINGATE_REFRESH_TOKEN` directly inside Umbrel's native App Settings UI.
- **Multi-Architecture**: Supports both `linux/amd64` (Intel/AMD x86_64 servers) and `linux/arm64` (Raspberry Pi 4/5, ARM SBCs).

---

## Package Structure

```text
twingate/
├── umbrel-app.yml       # App manifest adhering to umbrelOS schema and App Settings
├── docker-compose.yml   # Multi-service compose file (app_proxy, web, connector)
├── index.html.template  # Top-level rendered dashboard with live metrics and setup guide
├── nginx.conf.template  # Top-level rendered Nginx reverse proxy configuration
├── exports.sh           # Safe environment variable defaults
├── hooks/
│   └── pre-start        # Lifecycle hook ensuring data and rendered files exist
├── data/
│   └── .gitkeep         # Persistent data directory scaffolding
└── README.md            # App documentation & submission guide
```

---

## Services Architecture

| Service | Image | Description |
| :--- | :--- | :--- |
| `app_proxy` | N/A (umbrelOS virtual proxy) | Routes browser traffic on host port `8250` to `twingate_web_1:80` with Umbrel authentication. |
| `web` | `nginx:1.27.4-alpine` | Lightweight static web server that renders the setup dashboard and reverse-proxies connector metrics. |
| `connector` | `twingate/connector:1.93.0` | Upstream official Twingate Connector daemon running in stateless outbound mode. |

---

## Quick Start (User Setup)

1. **Install Twingate** from the Umbrel App Store.
2. Sign up for a free account at [twingate.com](https://www.twingate.com) and log in to your **Admin Console**.
3. In your Admin Console:
   - Go to **Remote Networks** &rarr; select or create a network (e.g., `Home Network`).
   - Click **Add Connector**, select **Docker** as deployment type, and click **Generate Tokens**.
   - Copy your **Network Slug**, **Access Token**, and **Refresh Token**.
4. In Umbrel:
   - Open **App Store &rarr; Twingate &rarr; Settings** (or click the settings icon on the Twingate card).
   - Enter your `TWINGATE_NETWORK`, `TWINGATE_ACCESS_TOKEN`, and `TWINGATE_REFRESH_TOKEN`.
   - Click **Save**. Umbrel will automatically restart the connector with your credentials.
5. In your Twingate Admin Console, click **Add Resource**:
   - **Resource Address**: Enter your Umbrel IP (e.g. `192.168.1.50`) or local subnet CIDR (e.g. `192.168.1.0/24`).
   - **Permissions**: Assign access to your user or group.
6. Download the Twingate client app on your computer or mobile device from [twingate.com/download](https://www.twingate.com/download/). Connect and enjoy direct, secure remote access to all your Umbrel apps!

---

## Submitting to the Umbrel App Store (`getumbrel/umbrel-apps`)

To submit this app for official inclusion in the Umbrel App Store:

### 1. Fork and Clone `getumbrel/umbrel-apps`
```bash
git clone https://github.com/<your-username>/umbrel-apps.git
cd umbrel-apps
git checkout -b add-twingate
```

### 2. Copy the `twingate` Folder
Copy this entire `twingate/` directory into the root of your `umbrel-apps` fork:
```bash
cp -r /path/to/twingate ./twingate
```

### 3. Run the Official Linter
Ensure there are no lint or schema errors:
```bash
npm install
npm run lint:apps -- twingate --check-images
git diff --check
```

### 4. Commit and Push
```bash
git add twingate
git commit -m "Add Twingate app"
git push origin add-twingate
```

### 5. Open a Pull Request
Open a Pull Request to `getumbrel/umbrel-apps:master` with the following template:

```markdown
### App Name & Version
- **App Name**: Twingate
- **Version**: 1.93.0
- **Upstream Website**: https://www.twingate.com
- **Upstream Docs**: https://www.twingate.com/docs/

### Description
Adds Twingate, a modern Zero Trust Network Access (ZTNA) solution that enables secure, encrypted remote access to Umbrel and private network services without open ports or port forwarding.

### Architecture & Features
- Official multi-arch upstream image `twingate/connector:1.93.0` pinned with SHA-256 digest.
- Lightweight embedded Nginx companion serving a dark-themed setup dashboard and live Prometheus metrics proxy.
- Native umbrelOS 2.0 `environment` settings support allowing users to manage credentials via the UI.
- No privileged container mode, no Docker socket access, and outbound-only traffic.

### Testing Performed
- [x] Verified `umbrel-app.yml` schema and field ordering.
- [x] Verified `docker-compose.yml` multi-arch image pinning.
- [x] Ran `npm run lint:apps -- twingate --check-images`.
- [x] Verified template rendering (`*.template`) via `envsubst`.
- [x] Verified web UI responsiveness and status indicators.
```
