import { readFile, writeFile } from 'node:fs/promises';

const configPath = process.env.CODEX_CONFIG_FILE ?? '/data/codex-home/config.toml';
const endpoint = process.env.REMNIC_MCP_URL;
const startMarker = '# BEGIN CODEX-AGENT MANAGED REMNIC';
const endMarker = '# END CODEX-AGENT MANAGED REMNIC';

if (!endpoint) {
  process.exit(0);
}

const url = new URL(endpoint);
if (!['http:', 'https:'].includes(url.protocol)) {
  throw new Error('REMNIC_MCP_URL must use http or https');
}

let config = '';
try {
  config = await readFile(configPath, 'utf8');
} catch (error) {
  if (error.code !== 'ENOENT') throw error;
}

const block = `${startMarker}
[mcp_servers.remnic]
url = ${JSON.stringify(url.toString())}
bearer_token_env_var = "REMNIC_AUTH_TOKEN"
startup_timeout_sec = 90.0
${endMarker}`;
const managedPattern = new RegExp(
  `${startMarker.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}[\\s\\S]*?${endMarker.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`,
);

if (managedPattern.test(config)) {
  config = config.replace(managedPattern, block);
} else if (/^\s*\[mcp_servers\.remnic\]\s*$/m.test(config)) {
  console.error('Codex Agent: preserving user-managed Remnic MCP configuration');
  process.exit(0);
} else {
  config = `${config.trimEnd()}${config.trim() ? '\n\n' : ''}${block}\n`;
}

await writeFile(configPath, config, { mode: 0o600 });
