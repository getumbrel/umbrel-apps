// SINGULARITY zmtp.js — minimal ZMTP/3.0 SUB socket in pure Node (no libzmq).
// Speaks exactly what bitcoind's zmqpubhashblock/zmqpubrawblock publisher needs:
// greeting -> NULL handshake -> READY -> subscribe -> multipart messages.
import net from 'node:net';
import { EventEmitter } from 'node:events';

const SIGNATURE = Buffer.concat([Buffer.from([0xff]), Buffer.alloc(8, 0), Buffer.from([0x7f])]);

function greeting() {
  const g = Buffer.alloc(64, 0);
  SIGNATURE.copy(g, 0);
  g[10] = 3; g[11] = 0;                 // version 3.0
  g.write('NULL', 12, 'ascii');         // mechanism, zero-padded to 20
  g[32] = 0;                            // as-server = false
  return g;
}

function readyCommand() {
  const name = Buffer.from('READY');
  const prop = Buffer.concat([
    Buffer.from([11]), Buffer.from('Socket-Type'),
    Buffer.from([0, 0, 0, 3]), Buffer.from('SUB'),
  ]);
  const body = Buffer.concat([Buffer.from([name.length]), name, prop]);
  return frame(body, 0x04);
}

function frame(body, flags = 0x00) {
  if (body.length < 256) return Buffer.concat([Buffer.from([flags, body.length]), body]);
  const hdr = Buffer.alloc(9);
  hdr[0] = flags | 0x02;
  hdr.writeBigUInt64BE(BigInt(body.length), 1);
  return Buffer.concat([hdr, body]);
}

export class ZmtpSub extends EventEmitter {
  constructor(endpoint, topics = ['hashblock']) {
    super();
    const m = /^tcp:\/\/([^:]+):(\d+)$/.exec(endpoint);
    if (!m) throw new Error(`bad zmq endpoint: ${endpoint}`);
    this.host = m[1]; this.port = Number(m[2]);
    this.endpoint = endpoint;
    this.topics = topics;
    this.buf = Buffer.alloc(0);
    this.phase = 'greeting';
    this.parts = [];
    this.sock = null;
    this.alive = false;
    this.stopped = false;
    this.backoff = 500;
  }

  start() { this.stopped = false; this._connect(); }
  stop() { this.stopped = true; if (this.sock) this.sock.destroy(); }

  _connect() {
    if (this.stopped) return;
    this.buf = Buffer.alloc(0); this.phase = 'greeting'; this.parts = [];
    const s = net.connect({ host: this.host, port: this.port, noDelay: true });
    this.sock = s;
    s.setKeepAlive(true, 30000);
    // watchdog: 15s to finish connect+handshake; once streaming, 45min of
    // total silence forces a cheap reconnect (defeats half-open sockets that
    // die without FIN/RST — e.g. docker network blips — which would otherwise
    // mute block notifications SILENTLY while looking "connected")
    s.setTimeout(15000, () => s.destroy());
    s.on('connect', () => { s.write(greeting()); });
    s.on('data', (d) => this._onData(d));
    s.on('error', () => {});
    s.on('close', () => {
      if (this.alive) this.emit('down', this.endpoint);
      this.alive = false;
      if (!this.stopped) {
        setTimeout(() => this._connect(), this.backoff);
        this.backoff = Math.min(this.backoff * 2, 10000);
      }
    });
  }

  _onData(d) {
    this.buf = Buffer.concat([this.buf, d]);
    // hard caps: a broken/hostile peer can never grow our memory
    if (this.buf.length > 16 * 1024 * 1024) return this.sock.destroy();
    try { this._drain(); } catch (e) { this.sock.destroy(); }
  }

  _drain() {
    if (this.phase === 'greeting') {
      if (this.buf.length < 64) return;
      const g = this.buf.subarray(0, 64);
      this.buf = this.buf.subarray(64);
      if (g[0] !== 0xff || g[9] !== 0x7f) throw new Error('bad greeting');
      this.sock.write(readyCommand());
      this.phase = 'handshake';
    }
    while (true) {
      if (this.buf.length < 2) return;
      const flags = this.buf[0];
      let size, off;
      if (flags & 0x02) {
        if (this.buf.length < 9) return;
        size = Number(this.buf.readBigUInt64BE(1)); off = 9;
      } else { size = this.buf[1]; off = 2; }
      if (this.buf.length < off + size) return;
      const body = this.buf.subarray(off, off + size);
      this.buf = this.buf.subarray(off + size);

      if (flags & 0x04) { // command
        const nameLen = body[0];
        const name = body.subarray(1, 1 + nameLen).toString();
        if (this.phase === 'handshake' && name === 'READY') {
          // subscribe (ZMTP 3.0 style: message starting with 0x01 + topic)
          for (const t of this.topics)
            this.sock.write(frame(Buffer.concat([Buffer.from([0x01]), Buffer.from(t)])));
          this.phase = 'stream';
          this.alive = true;
          this.backoff = 500;
          // idle-reconnect watchdog: if no hashblock arrives for 15 minutes,
          // the ZMQ connection is likely dead (half-open TCP or frozen bitcoind).
          // TCP KEEPALIVE (30s) handles truly-dead sockets at the kernel level;
          // this catches the rarer case where the TCP stack reports alive but
          // bitcoind has stopped publishing. 15min = ~1.5× expected block time
          // before we give up and reconnect.
          this.sock.setTimeout(15 * 60 * 1000, () => this.sock.destroy()); // idle-reconnect watchdog
          this.emit('up', this.endpoint);
        } else if (name === 'ERROR') {
          throw new Error('zmtp peer error');
        }
        continue;
      }
      // message frame
      this.parts.push(Buffer.from(body));
      if (this.parts.reduce((a, p) => a + p.length, 0) > 8 * 1024 * 1024) throw new Error('oversized message');
      if (!(flags & 0x01)) { // last part
        const parts = this.parts; this.parts = [];
        if (parts.length >= 2) {
          this.emit('message', parts[0].toString('ascii'), parts[1], parts[2]);
        }
      }
    }
  }
}

// Multi-endpoint manager: first endpoint to deliver a given block wins; dupes ignored upstream.
export class ZmqBlockWatcher extends EventEmitter {
  constructor(endpoints) {
    super();
    this.subs = endpoints.map((e) => new ZmtpSub(e, ['hashblock']));
    for (const s of this.subs) {
      s.on('message', (topic, body) => {
        if (topic === 'hashblock') this.emit('hashblock', body.toString('hex'));
      });
      s.on('up', (e) => this.emit('up', e));
      s.on('down', (e) => this.emit('down', e));
    }
  }
  start() { for (const s of this.subs) s.start(); }
  stop() { for (const s of this.subs) s.stop(); }
  get anyAlive() { return this.subs.some((s) => s.alive); }
}
