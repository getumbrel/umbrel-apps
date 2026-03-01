# App Submission

### App name
Tunnelsats (umbrel-app v3.0.0)

### 256x256 SVG icon
*(Uploaded in PR diff)*
A minimalist orange and dark gray lock/triangle logo representing Lightning Network security via Tunnelsats. 
_We will help finalize this icon before the app goes live in the Umbrel App Store._

### Gallery images
*(Uploaded in PR diff)*
A high-quality dark-mode abstract dashboard representation of secure VPN routing on umbrelOS.
_We will help finalize these images before the app goes live in the Umbrel App Store._

### Description
Tunnelsats integrates with your LND and Core Lightning apps to provide anonymous, hybrid routing over the fast WireGuard protocol.

By utilizing Tunnelsats, your Lightning node will route all of its clearnet traffic through our global, privacy-preserving VPN servers to prevent your home IP address from being exposed or targeted.

**Architecture Note:** To conform with UmbrelOS 1.6+ immutable architecture, this application utilizes `network_mode: "host"` with `NET_ADMIN` and `NET_RAW` privileges to dynamically discover the internal Docker IP addresses of the LND & CLN containers. It then isolates their outbound traffic specifically over the Wireguard interface (`tunnelsatsv2`). A strict Killswitch is applied locally to drop LND/CLN physical interface traffic should the VPN disconnect.

### I have tested my app on:
- [x] umbrelOS on a Raspberry Pi
- [ ] umbrelOS on an Umbrel Home
- [ ] umbrelOS on Linux VM
