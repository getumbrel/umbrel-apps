import crypto from 'node:crypto';
import { spawn, spawnSync } from 'node:child_process';
import { createReadStream, existsSync } from 'node:fs';
import http from 'node:http';
import path from 'node:path';

const port = Number(process.env.PORT || 8080);
const workspace = process.env.CODEX_WORKSPACE || '/projects';
const authFile = process.env.CODEX_AUTH_FILE || '/run/secrets/codex/auth.json';
const maxSessions = 4;
const maxFrameBytes = 64 * 1024;
const sessions = new Map();

function headers() {
  return {
    'Content-Security-Policy': "default-src 'self'; connect-src 'self' ws: wss:; style-src 'self'; base-uri 'none'; frame-ancestors 'none'",
    'Referrer-Policy': 'no-referrer',
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
  };
}

function sendFrame(socket, payload) {
  const body = Buffer.from(payload);
  const size = body.length;
  let prefix;
  if (size < 126) {
    prefix = Buffer.from([0x81, size]);
  } else if (size < 65536) {
    prefix = Buffer.allocUnsafe(4);
    prefix[0] = 0x81;
    prefix[1] = 126;
    prefix.writeUInt16BE(size, 2);
  } else {
    prefix = Buffer.allocUnsafe(10);
    prefix[0] = 0x81;
    prefix[1] = 127;
    prefix.writeBigUInt64BE(BigInt(size), 2);
  }
  socket.write(Buffer.concat([prefix, body]));
}

function parseFrames(state, chunk, onText) {
  if (state.buffer.length + chunk.length > maxFrameBytes + 14) return false;
  state.buffer = Buffer.concat([state.buffer, chunk]);
  while (state.buffer.length >= 2) {
    const first = state.buffer[0];
    const second = state.buffer[1];
    const opcode = first & 15;
    let length = second & 127;
    let headerLength = 2;
    const masked = Boolean(second & 128);
    if (!(first & 128) || !masked) return false;
    if (length === 126) {
      if (state.buffer.length < 4) return true;
      length = state.buffer.readUInt16BE(2);
      headerLength = 4;
    } else if (length === 127) {
      if (state.buffer.length < 10) return true;
      const wideLength = state.buffer.readBigUInt64BE(2);
      if (wideLength > BigInt(maxFrameBytes)) return false;
      length = Number(wideLength);
      headerLength = 10;
    }
    if (length > maxFrameBytes) return false;
    if (state.buffer.length < headerLength + 4 + length) return true;
    const key = state.buffer.subarray(headerLength, headerLength + 4);
    const payloadOffset = headerLength + 4;
    const value = Buffer.from(state.buffer.subarray(payloadOffset, payloadOffset + length));
    for (let index = 0; index < value.length; index++) value[index] ^= key[index % 4];
    state.buffer = state.buffer.subarray(payloadOffset + length);
    if (opcode === 8) return false;
    if (opcode === 9 || opcode === 10) continue;
    if (opcode !== 1) return false;
    onText(value.toString('utf8'));
  }
  return true;
}

function gatewayMessage(socket, params) {
  sendFrame(socket, JSON.stringify({ method: 'gateway/session', params }));
}

function startSession(socket, sessionId) {
  const existing = sessions.get(sessionId);
  if (existing) {
    if (existing.socket && existing.socket !== socket) existing.socket.end();
    existing.socket = socket;
    gatewayMessage(socket, { sessionId, fresh: false });
    attachSocket(existing, socket);
    return;
  }
  if (sessions.size >= maxSessions) {
    sendFrame(socket, JSON.stringify({ error: 'Session limit reached' }));
    socket.end();
    return;
  }
  const child = spawn('codex', ['app-server', '--stdio'], {
    cwd: workspace,
    env: { ...process.env, HOME: '/data/codex-home', CODEX_HOME: '/data/codex-home' },
    stdio: ['pipe', 'pipe', 'pipe'],
  });
  const session = { id: sessionId, child, socket, pending: '' };
  sessions.set(sessionId, session);
  child.once('error', () => {
    sessions.delete(sessionId);
    try { session.socket?.end(); } catch {}
  });
  gatewayMessage(socket, { sessionId, fresh: true });
  child.stdout.on('data', (part) => {
    session.pending += part.toString('utf8');
    for (;;) {
      const newline = session.pending.indexOf('\n');
      if (newline < 0) break;
      const message = session.pending.slice(0, newline);
      session.pending = session.pending.slice(newline + 1);
      if (message && session.socket && !session.socket.destroyed) sendFrame(session.socket, message);
    }
  });
  // stderr stays server-side: it can contain filesystem paths and diagnostics.
  child.stderr.resume();
  child.once('exit', () => { sessions.delete(sessionId); try { session.socket?.end(); } catch {} });
  attachSocket(session, socket);
}

function attachSocket(session, socket) {
  const detach = () => { if (session.socket === socket) session.socket = null; };
  socket.once('close', detach);
  const state = { buffer: Buffer.alloc(0) };
  socket.on('data', (chunk) => parseFrames(state, chunk, (message) => {
    if (Buffer.byteLength(message) > maxFrameBytes) return socket.end();
    try {
      const rpc = JSON.parse(message);
      if (rpc.method === 'gateway/end') {
        session.child.kill('SIGTERM');
        sessions.delete(session.id);
        return socket.end();
      }
      session.child.stdin.write(`${message}\n`);
    } catch { sendFrame(socket, JSON.stringify({ error: 'Invalid JSON-RPC message' })); }
  }) || socket.end());
}

const server = http.createServer((request, response) => {
  const common = headers();
  if (request.method === 'GET' && request.url === '/healthz') {
    const codex = spawnSync('codex', ['--version'], { stdio: 'ignore', timeout: 2000 });
    const ready = existsSync(authFile) && existsSync('/runtime/codex-home/auth.json') && codex.status === 0;
    response.writeHead(ready ? 200 : 503, { ...common, 'Content-Type': 'application/json', 'Cache-Control': 'no-store' });
    response.end(JSON.stringify({ status: ready ? 'ok' : 'not-ready' }));
    return;
  }
  if (request.method === 'GET' && (request.url === '/' || request.url === '/index.html')) {
    response.writeHead(200, { ...common, 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' });
    createReadStream(path.join('/app', 'index.html')).pipe(response);
    return;
  }
  response.writeHead(404, common); response.end();
});

server.on('upgrade', (request, socket) => {
  const origin = request.headers.origin;
  const host = request.headers.host;
  let requestUrl;
  let originUrl;
  try {
    requestUrl = new URL(request.url, 'http://localhost');
    originUrl = typeof origin === 'string' ? new URL(origin) : null;
  } catch {
    socket.write('HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n'); socket.destroy(); return;
  }
  const sessionId = requestUrl.searchParams.get('session');
  const key = request.headers['sec-websocket-key'];
  const upgrade = request.headers.upgrade;
  const connection = request.headers.connection;
  const validKey = typeof key === 'string' && Buffer.from(key, 'base64').length === 16;
  const validUpgrade = typeof upgrade === 'string' && upgrade.toLowerCase() === 'websocket'
    && typeof connection === 'string' && connection.toLowerCase().split(',').map((value) => value.trim()).includes('upgrade');
  if (requestUrl.pathname !== '/ws' || !originUrl || !host || originUrl.host !== host
    || !['http:', 'https:'].includes(originUrl.protocol) || !/^[0-9a-f-]{36}$/i.test(sessionId || '')
    || request.headers['sec-websocket-version'] !== '13' || !validKey || !validUpgrade
    || !existsSync('/runtime/codex-home/auth.json')) {
    socket.write('HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n'); socket.destroy(); return;
  }
  const accept = crypto.createHash('sha1').update(`${key}258EAFA5-E914-47DA-95CA-C5AB0DC85B11`).digest('base64');
  socket.write(`HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: ${accept}\r\n\r\n`);
  startSession(socket, sessionId);
});

server.listen(port, '0.0.0.0');
