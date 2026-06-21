// SINGULARITY dashboard.js — http + Server-Sent Events. No frameworks.
import http from 'node:http';
import os from 'node:os';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { VERSION } from './config.js';
import { fmtScaled } from './util.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const INDEX = fs.readFileSync(path.join(__dirname, '..', 'static', 'index.html'));

function detectHostLanIp(dataDir) {
  try {
    const fromFile = fs.readFileSync(path.join(dataDir, 'host_lan_ip'), 'utf8').trim();
    if (fromFile && !fromFile.startsWith('10.21.')) return fromFile;
  } catch {}
  for (const ifaces of Object.values(os.networkInterfaces())) {
    for (const iface of ifaces || []) {
      if (iface.family !== 'IPv4' || iface.internal) continue;
      if (iface.address.startsWith('10.21.')) continue; // umbrel apps subnet, not miner LAN
      return iface.address;
    }
  }
  return '';
}

export class Dashboard {
  constructor(cfg, registry, tm) {
    this.cfg = cfg;
    this.registry = registry;
    this.tm = tm;
    this.sseClients = new Set();
    this.server = http.createServer((req, res) => this.route(req, res));
    this.tick = setInterval(() => this.pushState(), 1000);
    this.heartbeat = setInterval(() => this.pingSse(), 15000);
    registry.on('block_found', (info) => this.pushEvent('block', info));
    registry.on('best_share', (info) => this.pushEvent('best', info));
  }

  listen() {
    return new Promise((res) => this.server.listen(this.cfg.dashboardPort, this.cfg.dashboardBind, res));
  }
  close() { clearInterval(this.tick); clearInterval(this.heartbeat); this.server.close(); for (const r of this.sseClients) r.end(); }

  snap() {
    return {
      version: VERSION,
      connect: {
        stratumPort: this.cfg.stratumPort,
        deviceDomain: this.cfg.deviceDomain,
        deviceHostname: this.cfg.deviceHostname,
        lanIp: detectHostLanIp(this.cfg.dataDir),
      },
      ...this.registry.snapshot(this.tm.current, this.tm.stats),
    };
  }

  route(req, res) {
    const url = req.url.split('?')[0];

    // ── Umbrel Home Widget API ──────────────────────────────────────────────
    // Returns pool stats in Umbrel widget format (4-cell grid)
    // Shown on Umbrel Home screen without opening the app
    if (url === '/widget-api/stats') {
      const snap = this.snap();
      const hr = snap.poolHashrate || 0;
      const hrFormatted = hr >= 1e15 ? (hr / 1e15).toFixed(2) + ' PH/s'
                        : hr >= 1e12 ? (hr / 1e12).toFixed(2) + ' TH/s'
                        : hr >= 1e9  ? (hr / 1e9).toFixed(2)  + ' GH/s'
                        :                (hr / 1e6).toFixed(2)  + ' MH/s';
      const bestShare = snap.bestShareEver || 0;
      const bestFormatted = bestShare > 0 ? fmtScaled(bestShare) : '0';
      const blocksCount = snap.blocksFound?.length ?? 0;
      res.writeHead(200, {
        'Content-Type': 'application/json',
        'Cache-Control': 'no-store',
        'Access-Control-Allow-Origin': '*',
      });
      return res.end(JSON.stringify({
        type: 'four-stats',
        refresh: '5s',
        link: '',
        items: [
          { title: 'Hash Rate', text: hrFormatted },
          { title: 'Miners', text: String(snap.miners?.length ?? 0) },
          { title: 'Blocks Found', text: String(blocksCount) },
          { title: 'Best Share', text: bestFormatted },
        ],
      }));
    }

    // ── Umbrel Widget: block height (alternative endpoint) ─────────────────
    if (url === '/widget-api/height') {
      const snap = this.snap();
      res.writeHead(200, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' });
      return res.end(JSON.stringify({ height: snap.job?.height ?? 0 }));
    }

    if (url === '/' || url === '/index.html') {
      // no-store: phones must NEVER show a stale dashboard after an update
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store, max-age=0', 'Pragma': 'no-cache' });
      return res.end(INDEX);
    }
    if (url === '/api/state') {
      res.writeHead(200, {
        'Content-Type': 'application/json',
        'Cache-Control': 'no-store',
        'Access-Control-Allow-Origin': '*',  // allow external dashboard consumers
      });
      return res.end(JSON.stringify(this.snap()));
    }
    if (url === '/events') {
      res.writeHead(200, {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no',
      });
      res.write(`event: state\ndata: ${JSON.stringify(this.snap())}\n\n`);
      this.sseClients.add(res);
      req.on('close', () => this.sseClients.delete(res));
      return;
    }
    res.writeHead(404); res.end('not found');
  }

  pushState() {
    if (this.sseClients.size === 0) return;
    const data = `event: state\ndata: ${JSON.stringify(this.snap())}\n\n`;
    for (const r of this.sseClients) { try { r.write(data); } catch { this.sseClients.delete(r); } }
  }

  pingSse() {
    if (this.sseClients.size === 0) return;
    for (const r of this.sseClients) { try { r.write(': ping\n\n'); } catch { this.sseClients.delete(r); } }
  }

  pushEvent(name, payload) {
    const data = `event: ${name}\ndata: ${JSON.stringify(payload)}\n\n`;
    for (const r of this.sseClients) { try { r.write(data); } catch { this.sseClients.delete(r); } }
  }
}
