import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

test('compose exposes no host port and gives Codex access to MCP services', async () => {
  const compose = await readFile(new URL('../docker-compose.yml', import.meta.url), 'utf8');
  assert.match(compose, /codex_agent_private:\n    internal: true/);
  assert.match(compose, /app:\n[\s\S]*?networks:\n      default: \{\}\n      codex_agent_private: \{\}/);
  assert.doesNotMatch(compose, /ports:/);
});

test('app-server uses stdio rather than a WebSocket listener', async () => {
  const source = await readFile(new URL('../server.mjs', import.meta.url), 'utf8');
  assert.match(source, /\['app-server', '--stdio'\]/);
  assert.doesNotMatch(source, /--listen/);
});

test('the client performs the required initialized acknowledgement', async () => {
  const ui = await readFile(new URL('../public/index.html', import.meta.url), 'utf8');
  const source = await readFile(new URL('../server.mjs', import.meta.url), 'utf8');
  assert.match(ui, /method:'initialized'/);
  assert.match(ui, /send\('thread\/start'/);
  assert.match(source, /readUInt16BE\(2\)/);
  assert.match(source, /readBigUInt64BE\(2\)/);
  assert.match(source, /state\.buffer\.length \+ chunk\.length > maxFrameBytes \+ 14/);
  assert.match(source, /request\.headers\['sec-websocket-version'\] !== '13'/);
  assert.match(source, /Buffer\.from\(key, 'base64'\)\.length === 16/);
});

test('Codex state is persistent while its OAuth credential stays in tmpfs', async () => {
  const source = await readFile(new URL('../server.mjs', import.meta.url), 'utf8');
  const entrypoint = await readFile(new URL('../entrypoint.sh', import.meta.url), 'utf8');
  const compose = await readFile(new URL('../docker-compose.yml', import.meta.url), 'utf8');
  assert.match(source, /CODEX_HOME: '\/data\/codex-home'/);
  assert.match(entrypoint, /ln -s \/runtime\/codex-home\/auth\.json \/data\/codex-home\/auth\.json/);
  assert.match(compose, /runtime-secrets:\/run\/secrets\/codex:ro/);
  assert.doesNotMatch(compose, /auth\.json:\/data/);
});

test('Remnic authentication remains a runtime secret', async () => {
  const entrypoint = await readFile(new URL('../entrypoint.sh', import.meta.url), 'utf8');
  const compose = await readFile(new URL('../docker-compose.yml', import.meta.url), 'utf8');
  const configure = await readFile(new URL('../configure-remnic.mjs', import.meta.url), 'utf8');
  assert.match(entrypoint, /REMNIC_AUTH_TOKEN=\$\(cat "\$REMNIC_AUTH_FILE"\)/);
  assert.match(entrypoint, /export REMNIC_AUTH_TOKEN/);
  assert.match(compose, /REMNIC_AUTH_FILE: \/run\/secrets\/codex\/remnic-auth-token/);
  assert.match(configure, /bearer_token_env_var = "REMNIC_AUTH_TOKEN"/);
  assert.doesNotMatch(configure, /process\.env\.REMNIC_AUTH_TOKEN/);
});

test('application files are readable by host-mapped runtime users', async () => {
  const dockerfile = await readFile(new URL('../Dockerfile', import.meta.url), 'utf8');
  assert.match(dockerfile, /chmod -R a\+rX \/app/);
});

test('the browser client reports the package version', async () => {
  const ui = await readFile(new URL('../public/index.html', import.meta.url), 'utf8');
  const packageJson = JSON.parse(await readFile(new URL('../package.json', import.meta.url), 'utf8'));
  assert.match(ui, new RegExp(`version:'${packageJson.version}'`));
});

test('Remnic configuration preserves existing settings without storing the token', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'codex-agent-remnic-'));
  const configPath = join(directory, 'config.toml');
  const token = 'test-token-that-must-not-be-persisted';
  await writeFile(configPath, 'model = "gpt-5"\n');

  const scriptPath = fileURLToPath(new URL('../configure-remnic.mjs', import.meta.url));
  const result = spawnSync(process.execPath, [scriptPath], {
    env: {
      ...process.env,
      CODEX_CONFIG_FILE: configPath,
      REMNIC_MCP_URL: 'http://remnic_server_1:4318/mcp',
      REMNIC_AUTH_TOKEN: token,
    },
    encoding: 'utf8',
  });
  assert.equal(result.status, 0, result.stderr);
  const config = await readFile(configPath, 'utf8');
  assert.match(config, /^model = "gpt-5"/);
  assert.match(config, /url = "http:\/\/remnic_server_1:4318\/mcp"/);
  assert.doesNotMatch(config, new RegExp(token));
  await rm(directory, { recursive: true, force: true });
});
