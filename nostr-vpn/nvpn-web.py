#!/usr/bin/env python3
import http.server
import socketserver
import os
import subprocess
import signal

PORT = 8080
HOST = "127.0.0.1"  # Bind to localhost only - not exposed to network
DATA_DIR = os.environ.get('NVPN_DATA_DIR', '/data')

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('X-Frame-Options', 'DENY')
            self.send_header('X-XSS-Protection', '1; mode=block')
            self.end_headers()
            
            # Get status - simpler output for security
            try:
                result = subprocess.run(['nvpn', 'status'], capture_output=True, text=True, timeout=5)
                status = result.stdout if result.returncode == 0 else result.stderr
            except Exception as e:
                status = 'Not initialized'
            
            # Minimal HTML - no command exposure
            html = f"""<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Nostr VPN</title>
<style>
body {{ font-family: -apple-system, sans-serif; max-width: 500px; margin: 50px auto; padding: 20px; background: #1a1a2e; color: #eee; text-align: center; }}
h1 {{ color: #00d4ff; }}
.status {{ background: #16213e; padding: 20px; border-radius: 10px; margin: 20px 0; }}
pre {{ background: #0f0f23; padding: 10px; border-radius: 5px; overflow-x: auto; font-size: 12px; text-align: left; }}
</style>
</head>
<body>
<h1>Nostr VPN</h1>
<div class="status">
<h2>Status</h2>
<pre>{status}</pre>
</div>
<p>Use Umbrel terminal for management</p>
</body>
</html>"""
            self.wfile.write(html.encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # No logging for security

def signal_handler(sig, frame):
    print('Shutting down...')
    httpd.shutdown()

signal.signal(signal.SIGTERM, signal_handler)

# Bind to localhost only - not exposed to external network
with socketserver.TCPServer((HOST, PORT), Handler) as httpd:
    print(f'Nostr VPN status on http://{HOST}:{PORT}')
    httpd.serve_forever()