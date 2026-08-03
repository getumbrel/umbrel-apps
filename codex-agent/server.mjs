import crypto from 'node:crypto';
import { spawn, spawnSync } from 'node:child_process';
import { createReadStream, existsSync } from 'node:fs';
import http from 'node:http';
import path from 'node:path';

const port = Number(process.env.PORT || 8080);
const workspace = process.env.CODEX_WORKSPACE || '/projects';
const authFile = process.env.CODEX_AUTH_FILE || '/run/secrets/codex/auth.json';
const runtimeAuthFile = process.env.CODEX_RUNTIME_AUTH_FILE || '/runtime/codex-home/auth.json';
const bridgeApiKey = process.env.BRIDGE_API_KEY || '';
const codexBin = process.env.CODEX_BIN || 'codex';
const maxRequestBytes = 1024 * 1024;
const maxConcurrentTurns = 4;
let activeTurns = 0;

function securityHeaders() {
  return {
    'Content-Security-Policy': "default-src 'self'; connect-src 'self'; style-src 'self'; base-uri 'none'; frame-ancestors 'none'",
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

function authorized(request) {
  const header = request.headers.authorization;
  if (!bridgeApiKey || typeof header !== 'string' || !header.startsWith('Bearer ')) return false;
  const supplied = Buffer.from(header.slice(7));
  const expected = Buffer.from(bridgeApiKey);
  return supplied.length === expected.length && crypto.timingSafeEqual(supplied, expected);
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
  return `Continue this LibreChat conversation as Codex. Work in the configured workspace, use tools when useful, and give the user a clear final answer.\n\n${transcript}`;
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
    env: { ...process.env, HOME: '/data/codex-home', CODEX_HOME: '/data/codex-home' },
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
        sandboxPolicy: { type: 'workspaceWrite', writableRoots: [workspace], networkAccess: true },
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
    if (message.method === 'error') return finish(new Error(message.params?.error?.message || 'Codex request failed'));
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
  writeRpc(child, { method: 'initialize', id: 1, params: { clientInfo: { name: 'umbrel_codex_agent_bridge', title: 'Umbrel Codex Agent Bridge', version: '0.2.0' } } });
  writeRpc(child, { method: 'initialized', params: {} });
  writeRpc(child, { method: 'thread/start', id: 2, params: {} });
  return () => finish(new Error('Client disconnected'));
}

function completionId() { return `chatcmpl-${crypto.randomUUID()}`; }

function sse(response, value) { response.write(`data: ${JSON.stringify(value)}\n\n`); }

async function handleCompletion(request, response) {
  if (!authorized(request)) return unauthorized(response);
  if (!existsSync(authFile) || !existsSync(runtimeAuthFile)) return json(response, 503, { error: { message: 'Codex authentication is not ready', type: 'service_unavailable' } });
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
  }, (error) => { settle(); json(response, 500, { error: { message: error.message, type: 'server_error' } }); });
}

const server = http.createServer((request, response) => {
  const pathname = new URL(request.url, 'http://localhost').pathname;
  if (request.method === 'GET' && pathname === '/healthz') {
    const codex = spawnSync(codexBin, ['--version'], { stdio: 'ignore', timeout: 2000 });
    const ready = Boolean(bridgeApiKey) && existsSync(authFile) && existsSync(runtimeAuthFile) && codex.status === 0;
    return json(response, ready ? 200 : 503, { status: ready ? 'ok' : 'not-ready' });
  }
  if (request.method === 'GET' && pathname === '/v1/models') {
    if (!authorized(request)) return unauthorized(response);
    return json(response, 200, { object: 'list', data: [{ id: 'codex-agent', object: 'model', created: 0, owned_by: 'openai' }] });
  }
  if (request.method === 'POST' && pathname === '/v1/chat/completions') return handleCompletion(request, response);
  if (request.method === 'GET' && (pathname === '/' || pathname === '/index.html')) {
    response.writeHead(200, { ...securityHeaders(), 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' });
    return createReadStream(path.join('/app', 'index.html')).pipe(response);
  }
  return json(response, 404, { error: { message: 'Not found', type: 'invalid_request_error' } });
});

server.listen(port, '0.0.0.0');
