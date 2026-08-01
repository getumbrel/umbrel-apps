import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

test('compose keeps Codex off the Umbrel main network', async () => {
  const compose = await readFile(new URL('../docker-compose.yml', import.meta.url), 'utf8');
  assert.match(compose, /codex_agent_private:\n    internal: true/);
  assert.match(compose, /app:\n[\s\S]*?networks:\n      codex_agent_private: \{\}/);
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
