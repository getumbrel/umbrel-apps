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

test('the bridge completes browser device-code setup before serving authenticated streamed completions', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'codex-agent-bridge-'));
  const legacyAuth = join(directory, 'legacy-auth.json');
  const persistentAuth = join(directory, 'auth.json');
  const mockCodex = join(directory, 'mock-codex.mjs');
  const port = 18080 + Math.floor(Math.random() * 1000);
  await writeFile(legacyAuth, '{}');
  await writeFile(mockCodex, `#!/usr/bin/env node
import { existsSync, writeFileSync } from 'node:fs';
if (process.env.BRIDGE_API_KEY) process.exit(91);
if (process.argv.includes('--version')) process.exit(0);
if (process.argv.includes('login')) {
  if (process.argv.includes('status')) process.exit(existsSync(process.env.CODEX_PERSISTENT_AUTH_FILE) ? 0 : 1);
  if (process.argv.includes('--device-auth')) {
    console.error('Open https://auth.openai.com/device and enter code: TEST-CODE');
    setTimeout(() => { writeFileSync(process.env.CODEX_PERSISTENT_AUTH_FILE, '{}'); process.exit(0); }, 100);
    process.stdin.resume();
  }
}
let buffer = '';
process.stdin.on('data', (chunk) => {
  buffer += chunk;
  for (;;) {
    const newline = buffer.indexOf('\\n'); if (newline < 0) break;
    const message = JSON.parse(buffer.slice(0, newline)); buffer = buffer.slice(newline + 1);
    if (message.id === 1) console.log(JSON.stringify({ id: 1, result: {} }));
    if (message.id === 2) console.log(JSON.stringify({ id: 2, result: { thread: { id: 'thread-test' } } }));
    if (message.id === 3) {
      console.log(JSON.stringify({ method: 'error', params: { error: { message: 'Reconnecting... 2/5' } } }));
      console.log(JSON.stringify({ method: 'item/agentMessage/delta', params: { delta: 'Bridge works.' } }));
      console.log(JSON.stringify({ method: 'turn/completed', params: { turn: { status: 'completed' } } }));
    }
  }
});
`);
  await chmod(mockCodex, 0o755);
  const server = spawn(process.execPath, ['server.mjs'], { cwd: root, env: { ...process.env, PORT: String(port), CODEX_BIN: mockCodex, CODEX_AUTH_FILE: legacyAuth, CODEX_PERSISTENT_AUTH_FILE: persistentAuth, BRIDGE_API_KEY: 'test-bridge-key', TRUSTED_PROXY_HOSTNAME: '127.0.0.1', CODEX_WORKSPACE: directory }, stdio: 'ignore' });
  try {
    await waitForHealth(port);
    const page = await request(port, 'GET', '/');
    assert.equal(page.status, 200);
    assert.match(page.headers['content-security-policy'], /script-src 'self'/);
    assert.doesNotMatch(page.headers['content-security-policy'], /unsafe-inline/);
    assert.match(page.body, /<script src="\/app\.js" defer><\/script>/);
    const script = await request(port, 'GET', '/app.js');
    assert.equal(script.status, 200);
    assert.match(script.headers['content-type'], /text\/javascript/);
    assert.match(script.body, /fetch\('\.\/api\/auth\/device\/start'/);
    const stylesheet = await request(port, 'GET', '/app.css');
    assert.equal(stylesheet.status, 200);
    assert.match(stylesheet.headers['content-type'], /text\/css/);
    assert.deepEqual(JSON.parse((await request(port, 'GET', '/api/auth/status')).body), { status: 'unauthenticated' });
    assert.equal((await request(port, 'POST', '/api/auth/device/start')).status, 415);
    let deviceLogin = JSON.parse((await request(port, 'POST', '/api/auth/device/start', '{}')).body);
    assert.equal(deviceLogin.status, 'pending');
    for (let index = 0; index < 50 && !deviceLogin.userCode; index += 1) {
      await new Promise((resolve) => setTimeout(resolve, 10));
      deviceLogin = JSON.parse((await request(port, 'GET', '/api/auth/status')).body);
    }
    assert.equal(deviceLogin.verificationUrl, 'https://auth.openai.com/device');
    assert.equal(deviceLogin.userCode, 'TEST-CODE');
    for (let index = 0; index < 50; index += 1) {
      if (JSON.parse((await request(port, 'GET', '/api/auth/status')).body).status === 'authenticated') break;
      await new Promise((resolve) => setTimeout(resolve, 20));
    }
    assert.equal(JSON.parse((await request(port, 'GET', '/api/auth/status')).body).status, 'authenticated');
    assert.equal(JSON.parse((await request(port, 'POST', '/api/auth/device/start?force=1', '{}')).body).status, 'pending');
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

test('Umbrel exposes browser setup and protects the shared-network bridge with a derived key', async () => {
  const [compose, exportsFile, manifest, setupPage, librechatConfig, librechatHook, librechatManifest, openWebuiManifest] = await Promise.all([
    readFile(new URL('../docker-compose.yml', import.meta.url), 'utf8'),
    readFile(new URL('../exports.sh', import.meta.url), 'utf8'),
    readFile(new URL('../umbrel-app.yml', import.meta.url), 'utf8'),
    readFile(new URL('../public/index.html', import.meta.url), 'utf8'),
    readFile(new URL('../../librechat/data/api/librechat.yaml', import.meta.url), 'utf8'),
    readFile(new URL('../../librechat/hooks/pre-start', import.meta.url), 'utf8'),
    readFile(new URL('../../librechat/umbrel-app.yml', import.meta.url), 'utf8'),
    readFile(new URL('../../open-webui/umbrel-app.yml', import.meta.url), 'utf8'),
  ]);
  assert.doesNotMatch(compose, /ports:/);
  assert.match(compose, /BRIDGE_API_KEY: \$\{APP_PASSWORD\}/);
  assert.match(compose, /TRUSTED_PROXY_HOSTNAME: \$\{APP_PROXY_HOSTNAME\}/);
  assert.doesNotMatch(compose, /host\.docker\.internal/);
  assert.doesNotMatch(exportsFile, /^\s*export\s+/m);
  assert.match(manifest, /deterministicPassword: true/);
  assert.match(manifest, /dependencies: \[\]/);
  assert.doesNotMatch(manifest, /must be placed at/);
  assert.match(setupPage, /http:\/\/codex-agent_app_1:8080\/v1/);
  assert.match(setupPage, /Umbrel password as the API key/);
  assert.match(setupPage, /Admin Settings → Connections/);
  assert.match(setupPage, /Choose <em>Codex Agent<\/em>/);
  assert.match(setupPage, /<script src="\/app\.js" defer><\/script>/);
  assert.match(setupPage, /<link rel="stylesheet" href="\/app\.css">/);
  assert.match(librechatConfig, /name: "Codex Agent"/);
  assert.match(librechatConfig, /apiKey: "user_provided"/);
  assert.match(librechatConfig, /baseURL: "http:\/\/codex-agent_app_1:8080\/v1"/);
  assert.match(librechatHook, /added optional Codex Agent endpoint configuration/);
  assert.match(librechatManifest, /version: "0\.8\.7-build-1"/);
  assert.doesNotMatch(openWebuiManifest, /implements:\n  - librechat/);
  const uiScript = await readFile(new URL('../public/app.js', import.meta.url), 'utf8');
  assert.match(uiScript, /fetch\('\.\/api\/auth\/device\/start'/);
});

test('a revoked Codex session returns to the device-login gate without exposing credentials', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'codex-agent-expired-'));
  const persistentAuth = join(directory, 'auth.json');
  const mockCodex = join(directory, 'mock-codex.mjs');
  const port = 19080 + Math.floor(Math.random() * 500);
  await writeFile(persistentAuth, '{}');
  await writeFile(mockCodex, `#!/usr/bin/env node
import { existsSync } from 'node:fs';
if (process.env.BRIDGE_API_KEY) process.exit(91);
if (process.argv.includes('--version')) process.exit(0);
if (process.argv.includes('login')) {
  if (process.argv.includes('status')) process.exit(existsSync(process.env.CODEX_PERSISTENT_AUTH_FILE) ? 0 : 1);
  if (process.argv.includes('--device-auth')) { console.error('Open https://auth.openai.com/device and enter code: TEST-CODE'); process.stdin.resume(); }
}
let buffer = '';
process.stdin.on('data', (chunk) => {
  buffer += chunk;
  for (;;) {
    const newline = buffer.indexOf('\\n'); if (newline < 0) break;
    const message = JSON.parse(buffer.slice(0, newline)); buffer = buffer.slice(newline + 1);
    if (message.id === 1) console.log(JSON.stringify({ id: 1, result: {} }));
    if (message.id === 2) console.log(JSON.stringify({ id: 2, result: { thread: { id: 'thread-expired' } } }));
    if (message.id === 3) console.log(JSON.stringify({ id: 3, error: { message: 'Your access token could not be refreshed. Please log in again.' } }));
  }
});
`);
  await chmod(mockCodex, 0o755);
  const server = spawn(process.execPath, ['server.mjs'], { cwd: root, env: { ...process.env, PORT: String(port), CODEX_BIN: mockCodex, CODEX_PERSISTENT_AUTH_FILE: persistentAuth, BRIDGE_API_KEY: 'test-bridge-key', TRUSTED_PROXY_HOSTNAME: '127.0.0.1', CODEX_WORKSPACE: directory }, stdio: 'ignore' });
  try {
    await waitForHealth(port);
    const completion = await request(port, 'POST', '/v1/chat/completions', JSON.stringify({ messages: [{ role: 'user', content: 'Hello' }] }), { Authorization: 'Bearer test-bridge-key' });
    assert.equal(completion.status, 500);
    const status = JSON.parse((await request(port, 'GET', '/api/auth/status')).body);
    assert.equal(status.status, 'unauthenticated');
    assert.match(status.error, /reconnect your ChatGPT account/);
    assert.equal(JSON.parse((await request(port, 'POST', '/api/auth/device/start', '{}')).body).status, 'pending');
  } finally {
    server.kill('SIGTERM');
    await rm(directory, { recursive: true, force: true });
  }
});

test('Codex stays on stdio and owns its browser-created credential privately', async () => {
  const [source, entrypoint, compose, dockerfile] = await Promise.all([
    readFile(new URL('../server.mjs', import.meta.url), 'utf8'),
    readFile(new URL('../entrypoint.sh', import.meta.url), 'utf8'),
    readFile(new URL('../docker-compose.yml', import.meta.url), 'utf8'),
    readFile(new URL('../Dockerfile', import.meta.url), 'utf8'),
  ]);
  assert.match(source, /\['app-server', '--stdio'\]/);
  assert.match(source, /Umbrel Codex Agent Bridge', version: '0\.3\.8'/);
  assert.match(source, /\['login', '-c', 'cli_auth_credentials_store="file"', '--device-auth'\]/);
  assert.match(source, /rememberAuthenticationFailure/);
  assert.match(source, /reconnecting/);
  assert.match(source, /searchParams\.get\('force'\) === '1'/);
  assert.match(entrypoint, /Migrate existing host-local credentials once/);
  assert.doesNotMatch(source, /--listen/);
  assert.match(source, /crypto\.timingSafeEqual/);
  assert.match(source, /delete childEnvironment\.BRIDGE_API_KEY/);
  assert.match(source, /networkAccess: false/);
  assert.match(source, /fromTrustedProxy/);
  assert.match(entrypoint, /Migrate existing host-local credentials once/);
  assert.match(entrypoint, /if \[ -L "\$CODEX_PERSISTENT_AUTH_FILE" \]; then/);
  assert.doesNotMatch(entrypoint, /test -r "\$CODEX_AUTH_FILE"/);
  assert.match(compose, /runtime-secrets:\/run\/secrets\/codex:ro/);
  assert.doesNotMatch(compose, /codex_agent_private/);
  assert.match(dockerfile, /apt-get install --yes --no-install-recommends ca-certificates/);
});
