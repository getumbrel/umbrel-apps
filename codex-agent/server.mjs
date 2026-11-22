import crypto from 'node:crypto';
import { spawn, spawnSync } from 'node:child_process';
import { lookup } from 'node:dns/promises';
import { chmodSync, createReadStream, existsSync } from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const port = Number(process.env.PORT || 8080);
const workspace = process.env.CODEX_WORKSPACE || '/projects';
const persistentAuthFile = process.env.CODEX_PERSISTENT_AUTH_FILE || '/data/codex-home/auth.json';
const bridgeApiKey = process.env.BRIDGE_API_KEY || '';
const codexBin = process.env.CODEX_BIN || 'codex';
const trustedProxyHostname = process.env.TRUSTED_PROXY_HOSTNAME || '';
const maxRequestBytes = 1024 * 1024;
const maxConcurrentTurns = 4;
const publicDirectory = path.join(path.dirname(fileURLToPath(import.meta.url)), 'public');
let activeTurns = 0;
let deviceLogin = null;
let authFailure = null;

function securityHeaders() {
  return {
    'Content-Security-Policy': "default-src 'self'; connect-src 'self'; style-src 'self'; script-src 'self'; base-uri 'none'; frame-ancestors 'none'",
    'Referrer-Policy': 'no-referrer',
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
  };
}

function json(response, status, body) {
  response.writeHead(status, { ...securityHeaders(), 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' });
  response.end(JSON.stringify(body));
}

function unauthorized(response) {
  response.writeHead(401, { ...securityHeaders(), 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store', 'WWW-Authenticate': 'Bearer' });
  response.end(JSON.stringify({ error: { message: 'Invalid API key', type: 'authentication_error', code: 'invalid_api_key' } }));
}

function forbidden(response) {
  return json(response, 403, { error: { message: 'This route is available only through Umbrel app_proxy.', type: 'authentication_error' } });
}

function unsupportedMediaType(response) {
  return json(response, 415, { error: { message: 'Content-Type must be application/json.', type: 'invalid_request_error' } });
}

function normalizeAddress(address) {
  return String(address || '').replace(/^::ffff:/, '');
}

async function fromTrustedProxy(request) {
  if (!trustedProxyHostname) return false;
  try {
    const addresses = await lookup(trustedProxyHostname, { all: true });
    return addresses.some(({ address }) => normalizeAddress(address) === normalizeAddress(request.socket.remoteAddress));
  } catch {
    return false;
  }
}

function hasJsonContentType(request) {
  return String(request.headers['content-type'] || '').split(';', 1)[0].trim().toLowerCase() === 'application/json';
}

function authorized(request) {
  const header = request.headers.authorization;
  if (!bridgeApiKey || typeof header !== 'string' || !header.startsWith('Bearer ')) return false;
  const supplied = Buffer.from(header.slice(7));
  const expected = Buffer.from(bridgeApiKey);
  return supplied.length === expected.length && crypto.timingSafeEqual(supplied, expected);
}

function codexEnvironment() {
  const childEnvironment = { ...process.env };
  delete childEnvironment.BRIDGE_API_KEY;
  return { ...childEnvironment, HOME: '/data/codex-home', CODEX_HOME: '/data/codex-home' };
}

function codexAuthenticated() {
  if (!existsSync(persistentAuthFile)) return false;
  return spawnSync(codexBin, ['login', 'status'], { env: codexEnvironment(), stdio: 'ignore', timeout: 3000 }).status === 0;
}

function deviceLoginStatus() {
  if (deviceLogin) {
    const { status, verificationUrl, userCode, startedAt, error } = deviceLogin;
    return { status, ...(verificationUrl ? { verificationUrl } : {}), ...(userCode ? { userCode } : {}), ...(error ? { error } : {}), startedAt };
  }
  if (!authFailure && codexAuthenticated()) return { status: 'authenticated' };
  return { status: 'unauthenticated', ...(authFailure ? { error: authFailure } : {}) };
}

function parseDeviceInstructions(output) {
  const verificationUrl = output.match(/https:\/\/[^\s"'<>]+/i)?.[0];
  const userCode = output.match(/\b[A-Z0-9]{4,8}-[A-Z0-9]{4,8}\b/)?.[0];
  return { verificationUrl, userCode };
}

function startDeviceLogin({ force = false } = {}) {
  if (!force && !authFailure && codexAuthenticated()) return { status: 'authenticated' };
  if (deviceLogin?.status === 'pending') return deviceLoginStatus();
  authFailure = null;
  const state = { status: 'pending', startedAt: new Date().toISOString(), verificationUrl: undefined, userCode: undefined, error: undefined, output: '' };
  const child = spawn(codexBin, ['login', '-c', 'cli_auth_credentials_store="file"', '--device-auth'], { env: codexEnvironment(), stdio: ['ignore', 'pipe', 'pipe'] });
  state.child = child;
  deviceLogin = state;
  const collect = (chunk) => {
    state.output = `${state.output}${chunk.toString('utf8')}`.slice(-8192);
    const instructions = parseDeviceInstructions(state.output);
    if (instructions.verificationUrl) state.verificationUrl = instructions.verificationUrl;
    if (instructions.userCode) state.userCode = instructions.userCode;
  };
  child.stdout.on('data', collect);
  child.stderr.on('data', collect);
  child.once('error', () => { state.status = 'failed'; state.error = 'Unable to start Codex device login.'; });
  child.once('exit', (code) => {
    if (codexAuthenticated()) {
      try {
        chmodSync(persistentAuthFile, 0o600);
      } catch {
        // The login succeeded; report it even if an unusual volume rejects chmod.
      }
      state.status = 'authenticated';
      authFailure = null;
      deviceLogin = null;
    } else if (state.status === 'pending') {
      state.status = code === 0 ? 'expired' : 'failed';
      state.error = code === 0 ? 'The device code expired before authentication completed.' : 'Codex device login did not complete. Start a new login and try again.';
    }
    delete state.child;
    state.output = '';
  });
  return deviceLoginStatus();
}

function rememberAuthenticationFailure(error) {
  const message = String(error?.message || '');
  if (/log in again|sign in again|refresh token|access token.*refreshed|session has ended/i.test(message)) {
    authFailure = 'Codex needs you to reconnect your ChatGPT account. Start a new device login below.';
    deviceLogin = null;
  }
}

function contentToText(content) {
  if (typeof content === 'string') return content;
  if (!Array.isArray(content)) return '';
  return content.map((part) => {
    if (!part || typeof part !== 'object') return '';
    if (part.type === 'text' && typeof part.text === 'string') return part.text;
    if (part.type === 'image_url') return '[Image attached]';
    return '';
  }).filter(Boolean).join('\n');
}

function buildPrompt(messages) {
  const transcript = messages.map((message) => {
    const role = ['system', 'user', 'assistant', 'tool'].includes(message.role) ? message.role : 'user';
    return `${role.toUpperCase()}: ${contentToText(message.content)}`;
  }).filter((line) => !line.endsWith(': ')).join('\n\n');
  return `Continue this chat conversation as Codex. Work in the configured workspace, use tools when useful, and give the user a clear final answer.\n\n${transcript}`;
}

function readJson(request) {
  return new Promise((resolve, reject) => {
    let size = 0;
    const chunks = [];
    request.on('data', (chunk) => {
      size += chunk.length;
      if (size > maxRequestBytes) {
        reject(Object.assign(new Error('Request body is too large'), { status: 413 }));
        request.destroy();
        return;
      }
      chunks.push(chunk);
    });
    request.once('error', reject);
    request.once('end', () => {
      try { resolve(JSON.parse(Buffer.concat(chunks).toString('utf8'))); } catch { reject(Object.assign(new Error('Invalid JSON body'), { status: 400 })); }
    });
  });
}

function writeRpc(child, message) {
  child.stdin.write(`${JSON.stringify(message)}\n`);
}

function runCodexTurn(payload, onDelta, onDone, onError) {
  const child = spawn(codexBin, ['app-server', '--stdio'], {
    cwd: workspace,
    env: codexEnvironment(),
    stdio: ['pipe', 'pipe', 'pipe'],
  });
  let buffer = '';
  let finished = false;
  const finish = (error) => {
    if (finished) return;
    finished = true;
    try { child.kill('SIGTERM'); } catch {}
    if (error) onError(error); else onDone();
  };
  const handle = (message) => {
    if (message.id === 1 && message.error) return finish(new Error(message.error.message || 'Codex initialization failed'));
    if (message.id === 2 && message.error) return finish(new Error(message.error.message || 'Unable to start Codex thread'));
    if (message.id === 2 && message.result?.thread?.id) {
      const params = {
        threadId: message.result.thread.id,
        input: [{ type: 'text', text: buildPrompt(payload.messages) }],
        cwd: workspace,
        approvalPolicy: process.env.CODEX_APPROVAL_POLICY || 'never',
        sandboxPolicy: { type: 'workspaceWrite', writableRoots: [workspace], networkAccess: false },
      };
      if (payload.model && payload.model !== 'codex-agent') params.model = payload.model;
      writeRpc(child, { method: 'turn/start', id: 3, params });
      return;
    }
    if (message.id === 3 && message.error) return finish(new Error(message.error.message || 'Unable to start Codex turn'));
    if (message.method === 'item/agentMessage/delta') {
      const delta = message.params?.delta ?? message.params?.text ?? '';
      if (typeof delta === 'string' && delta) onDelta(delta);
    }
    if (message.method === 'turn/completed') {
      const turn = message.params?.turn;
      if (turn?.status === 'completed') return finish();
      return finish(new Error(turn?.error?.message || `Codex turn ${turn?.status || 'failed'}`));
    }
    if (message.method === 'error') {
      const errorMessage = message.params?.error?.message || 'Codex request failed';
      // app-server can announce a transient reconnect while it restores its
      // upstream session. It is not a failed turn and is followed by normal
      // JSON-RPC responses when the connection returns.
      if (/^reconnecting(?:\.\.\.|…)?\s+\d+\/\d+$/i.test(errorMessage)) return;
      return finish(new Error(errorMessage));
    }
  };
  child.once('error', (error) => finish(error));
  child.once('exit', (code) => { if (!finished) finish(new Error(`Codex exited before completing the turn (code ${code ?? 'unknown'})`)); });
  child.stderr.resume();
  child.stdout.on('data', (chunk) => {
    buffer += chunk.toString('utf8');
    for (;;) {
      const newline = buffer.indexOf('\n');
      if (newline < 0) break;
      const line = buffer.slice(0, newline);
      buffer = buffer.slice(newline + 1);
      if (!line) continue;
      try { handle(JSON.parse(line)); } catch { finish(new Error('Codex returned malformed JSON-RPC output')); }
    }
  });
  writeRpc(child, { method: 'initialize', id: 1, params: { clientInfo: { name: 'umbrel_codex_agent_bridge', title: 'Umbrel Codex Agent Bridge', version: '0.3.8' } } });
  writeRpc(child, { method: 'initialized', params: {} });
  writeRpc(child, { method: 'thread/start', id: 2, params: {} });
  return () => finish(new Error('Client disconnected'));
}

function completionId() { return `chatcmpl-${crypto.randomUUID()}`; }

function sse(response, value) { response.write(`data: ${JSON.stringify(value)}\n\n`); }

async function handleCompletion(request, response) {
  if (!authorized(request)) return unauthorized(response);
  if (authFailure || !codexAuthenticated()) return json(response, 503, { error: { message: 'Codex authentication is not ready. Complete setup in the Codex Agent app.', type: 'service_unavailable' } });
  let payload;
  try { payload = await readJson(request); } catch (error) { return json(response, error.status || 400, { error: { message: error.message, type: 'invalid_request_error' } }); }
  if (!Array.isArray(payload.messages) || payload.messages.length === 0) return json(response, 400, { error: { message: 'messages must be a non-empty array', type: 'invalid_request_error' } });
  if (activeTurns >= maxConcurrentTurns) return json(response, 429, { error: { message: 'Codex bridge is busy; retry shortly', type: 'rate_limit_error' } });
  activeTurns += 1;
  const id = completionId();
  const created = Math.floor(Date.now() / 1000);
  let text = '';
  const settle = () => { activeTurns -= 1; };
  if (payload.stream) {
    response.writeHead(200, { ...securityHeaders(), 'Content-Type': 'text/event-stream; charset=utf-8', 'Cache-Control': 'no-cache, no-transform', Connection: 'keep-alive', 'X-Accel-Buffering': 'no' });
    sse(response, { id, object: 'chat.completion.chunk', created, model: payload.model || 'codex-agent', choices: [{ index: 0, delta: { role: 'assistant' }, finish_reason: null }] });
    const cancel = runCodexTurn(payload, (delta) => {
      text += delta;
      sse(response, { id, object: 'chat.completion.chunk', created, model: payload.model || 'codex-agent', choices: [{ index: 0, delta: { content: delta }, finish_reason: null }] });
    }, () => {
      sse(response, { id, object: 'chat.completion.chunk', created, model: payload.model || 'codex-agent', choices: [{ index: 0, delta: {}, finish_reason: 'stop' }] });
      response.end('data: [DONE]\n\n'); settle();
    }, (error) => {
      rememberAuthenticationFailure(error);
      sse(response, { error: { message: error.message, type: 'server_error' } });
      response.end('data: [DONE]\n\n'); settle();
    });
    request.once('aborted', cancel);
    response.once('close', () => { if (!response.writableEnded) cancel(); });
    return;
  }
  runCodexTurn(payload, (delta) => { text += delta; }, () => {
    settle();
    json(response, 200, { id, object: 'chat.completion', created, model: payload.model || 'codex-agent', choices: [{ index: 0, message: { role: 'assistant', content: text }, finish_reason: 'stop' }] });
  }, (error) => { rememberAuthenticationFailure(error); settle(); json(response, 500, { error: { message: error.message, type: 'server_error' } }); });
}

const server = http.createServer(async (request, response) => {
  const pathname = new URL(request.url, 'http://localhost').pathname;
  if (request.method === 'GET' && pathname === '/healthz') {
    const codex = spawnSync(codexBin, ['--version'], { env: codexEnvironment(), stdio: 'ignore', timeout: 2000 });
    const running = Boolean(bridgeApiKey) && codex.status === 0;
    return json(response, running ? 200 : 503, { status: running ? (!authFailure && codexAuthenticated() ? 'ok' : 'needs-authentication') : 'not-ready' });
  }
  const isAdminRoute = pathname === '/' || pathname === '/index.html' || pathname === '/app.css' || pathname === '/app.js' || pathname.startsWith('/api/auth/');
  if (isAdminRoute && !(await fromTrustedProxy(request))) return forbidden(response);
  if (request.method === 'GET' && pathname === '/api/auth/status') return json(response, 200, deviceLoginStatus());
  if (request.method === 'POST' && pathname === '/api/auth/device/start') {
    if (!hasJsonContentType(request)) return unsupportedMediaType(response);
    const force = new URL(request.url, 'http://localhost').searchParams.get('force') === '1';
    return json(response, 202, startDeviceLogin({ force }));
  }
  if (request.method === 'POST' && pathname === '/api/auth/device/cancel') {
    if (!hasJsonContentType(request)) return unsupportedMediaType(response);
    if (deviceLogin?.child) deviceLogin.child.kill('SIGTERM');
    deviceLogin = null;
    return json(response, 200, { status: codexAuthenticated() ? 'authenticated' : 'unauthenticated' });
  }
  if (request.method === 'GET' && pathname === '/v1/models') {
    if (!authorized(request)) return unauthorized(response);
    return json(response, 200, { object: 'list', data: [{ id: 'codex-agent', object: 'model', created: 0, owned_by: 'openai' }] });
  }
  if (request.method === 'POST' && pathname === '/v1/chat/completions') return handleCompletion(request, response);
  const staticFiles = {
    '/': ['index.html', 'text/html; charset=utf-8'],
    '/index.html': ['index.html', 'text/html; charset=utf-8'],
    '/app.css': ['app.css', 'text/css; charset=utf-8'],
    '/app.js': ['app.js', 'text/javascript; charset=utf-8'],
  };
  if (request.method === 'GET' && staticFiles[pathname]) {
    const [file, contentType] = staticFiles[pathname];
    response.writeHead(200, { ...securityHeaders(), 'Content-Type': contentType, 'Cache-Control': 'no-store' });
    return createReadStream(path.join(publicDirectory, file)).pipe(response);
  }
  return json(response, 404, { error: { message: 'Not found', type: 'invalid_request_error' } });
});

server.listen(port, '0.0.0.0');
