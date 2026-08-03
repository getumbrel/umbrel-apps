import assert from 'node:assert/strict';
import http from 'node:http';
import { spawn } from 'node:child_process';
import { chmod, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import test from 'node:test';
import { join } from 'node:path';

const root = new URL('..', import.meta.url);

function request(port, method, pathname, body, headers = {}) {
  return new Promise((resolve, reject) => {
    const req = http.request({ host: '127.0.0.1', port, method, path: pathname, headers: { ...headers, ...(body ? { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body) } : {}) } }, (res) => {
      let response = '';
      res.setEncoding('utf8'); res.on('data', (chunk) => { response += chunk; });
      res.on('end', () => resolve({ status: res.statusCode, headers: res.headers, body: response }));
    });
    req.once('error', reject); if (body) req.write(body); req.end();
  });
}

async function waitForHealth(port) {
  for (let index = 0; index < 50; index += 1) {
    try { if ((await request(port, 'GET', '/healthz')).status === 200) return; } catch {}
    await new Promise((resolve) => setTimeout(resolve, 20));
  }
  throw new Error('bridge did not become healthy');
}

test('the bridge implements an authenticated, streamed OpenAI-compatible Codex endpoint', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'codex-agent-bridge-'));
  const auth = join(directory, 'auth.json');
  const runtimeAuth = join(directory, 'runtime-auth.json');
  const mockCodex = join(directory, 'mock-codex.mjs');
  const port = 18080 + Math.floor(Math.random() * 1000);
  await Promise.all([writeFile(auth, '{}'), writeFile(runtimeAuth, '{}')]);
  await writeFile(mockCodex, `#!/usr/bin/env node
if (process.argv.includes('--version')) process.exit(0);
let buffer = '';
process.stdin.on('data', (chunk) => {
  buffer += chunk;
  for (;;) {
    const newline = buffer.indexOf('\\n'); if (newline < 0) break;
    const message = JSON.parse(buffer.slice(0, newline)); buffer = buffer.slice(newline + 1);
    if (message.id === 1) console.log(JSON.stringify({ id: 1, result: {} }));
    if (message.id === 2) console.log(JSON.stringify({ id: 2, result: { thread: { id: 'thread-test' } } }));
    if (message.id === 3) {
      console.log(JSON.stringify({ method: 'item/agentMessage/delta', params: { delta: 'Bridge works.' } }));
      console.log(JSON.stringify({ method: 'turn/completed', params: { turn: { status: 'completed' } } }));
    }
  }
});
`);
  await chmod(mockCodex, 0o755);
  const server = spawn(process.execPath, ['server.mjs'], { cwd: root, env: { ...process.env, PORT: String(port), CODEX_BIN: mockCodex, CODEX_AUTH_FILE: auth, CODEX_RUNTIME_AUTH_FILE: runtimeAuth, BRIDGE_API_KEY: 'test-bridge-key', CODEX_WORKSPACE: directory }, stdio: 'ignore' });
  try {
    await waitForHealth(port);
    assert.equal((await request(port, 'GET', '/v1/models')).status, 401);
    const models = await request(port, 'GET', '/v1/models', undefined, { Authorization: 'Bearer test-bridge-key' });
    assert.equal(models.status, 200);
    assert.deepEqual(JSON.parse(models.body).data.map((model) => model.id), ['codex-agent']);
    const completion = await request(port, 'POST', '/v1/chat/completions', JSON.stringify({ model: 'codex-agent', stream: true, messages: [{ role: 'user', content: 'Say hello' }] }), { Authorization: 'Bearer test-bridge-key' });
    assert.equal(completion.status, 200);
    assert.match(completion.headers['content-type'], /text\/event-stream/);
    assert.match(completion.body, /Bridge works\./);
    assert.match(completion.body, /\[DONE\]/);
  } finally {
    server.kill('SIGTERM');
    await rm(directory, { recursive: true, force: true });
  }
});

test('Umbrel only exposes the browser setup route and protects the shared-network bridge with a derived key', async () => {
  const [compose, exportsFile, manifest, librechatConfig, librechatManifest, openWebui] = await Promise.all([
    readFile(new URL('../docker-compose.yml', import.meta.url), 'utf8'),
    readFile(new URL('../exports.sh', import.meta.url), 'utf8'),
    readFile(new URL('../umbrel-app.yml', import.meta.url), 'utf8'),
    readFile(new URL('../../librechat/data/api/librechat.yaml', import.meta.url), 'utf8'),
    readFile(new URL('../../librechat/umbrel-app.yml', import.meta.url), 'utf8'),
    readFile(new URL('../../open-webui/umbrel-app.yml', import.meta.url), 'utf8'),
  ]);
  assert.doesNotMatch(compose, /ports:/);
  assert.match(compose, /BRIDGE_API_KEY: \$\{APP_CODEX_AGENT_BRIDGE_API_KEY\}/);
  assert.match(exportsFile, /APP_CODEX_AGENT_BRIDGE_API_KEY="\$\{APP_PASSWORD\}"/);
  assert.match(manifest, /deterministicPassword: true/);
  assert.match(manifest, /dependencies:\n  - librechat/);
  assert.doesNotMatch(librechatManifest, /implements:/);
  assert.match(openWebui, /implements:\n  - librechat/);
  assert.match(librechatConfig, /name: "Codex Agent"/);
  assert.match(librechatConfig, /apiKey: "user_provided"/);
  assert.match(librechatConfig, /baseURL: "http:\/\/codex-agent_app_1:8080\/v1"/);
});

test('Codex stays on stdio and the bridge does not persist the OAuth credential', async () => {
  const [source, entrypoint, compose] = await Promise.all([
    readFile(new URL('../server.mjs', import.meta.url), 'utf8'),
    readFile(new URL('../entrypoint.sh', import.meta.url), 'utf8'),
    readFile(new URL('../docker-compose.yml', import.meta.url), 'utf8'),
  ]);
  assert.match(source, /\['app-server', '--stdio'\]/);
  assert.doesNotMatch(source, /--listen/);
  assert.match(source, /crypto\.timingSafeEqual/);
  assert.match(entrypoint, /ln -s \/runtime\/codex-home\/auth\.json \/data\/codex-home\/auth\.json/);
  assert.match(compose, /runtime-secrets:\/run\/secrets\/codex:ro/);
});
