export const VERSION = '1.6.11';
// SINGULARITY config.js — Umbrel-aware configuration
// On Umbrel, Bitcoin Core credentials are injected automatically via environment
// variables: APP_BITCOIN_NODE_IP, APP_BITCOIN_RPC_PORT, APP_BITCOIN_RPC_USER,
// APP_BITCOIN_RPC_PASS, APP_BITCOIN_ZMQ_HASHBLOCK_PORT
const env = (k, d) => (process.env[k] !== undefined && process.env[k] !== '' ? process.env[k] : d);

// Umbrel auto-connect: build RPC_URL and ZMQ_BLOCKS from Umbrel env vars if
// the explicit RPC_URL is not set. This means zero configuration on Umbrel.
function resolveRpcUrl() {
  if (process.env.RPC_URL) return process.env.RPC_URL;
  const host = process.env.APP_BITCOIN_NODE_IP || '127.0.0.1';
  const port = process.env.APP_BITCOIN_RPC_PORT || '8332';
  return `http://${host}:${port}/`;
}
function resolveZmqBlocks() {
  if (process.env.ZMQ_BLOCKS) return process.env.ZMQ_BLOCKS;
  const host = process.env.APP_BITCOIN_NODE_IP || '127.0.0.1';
  const port = process.env.APP_BITCOIN_ZMQ_HASHBLOCK_PORT || '28334';
  return `tcp://${host}:${port}`;
}
const num = (k, d) => Number(env(k, d));
const bool = (k, d) => String(env(k, d)).toLowerCase() === 'true';

export const CONFIG = {
  rpcUrl: resolveRpcUrl(),
  rpcUser: env('RPC_USER', '') || env('APP_BITCOIN_RPC_USER', ''),
  rpcPass: env('RPC_PASS', '') || env('APP_BITCOIN_RPC_PASS', ''),
  zmqBlocks: resolveZmqBlocks().split(',').map(s => s.trim()).filter(Boolean),
  network: env('BITCOIN_NETWORK', 'mainnet'),
  payoutAddress: env('PAYOUT_ADDRESS', ''),
  coinbaseTag: env('COINBASE_TAG', '/SINGULARITY/'),
  stratumPort: num('STRATUM_PORT', 2038),
  stratumBind: env('STRATUM_BIND', '0.0.0.0'),
  dashboardPort: num('DASHBOARD_PORT', 3337),
  dashboardBind: env('DASHBOARD_BIND', '0.0.0.0'),

  extranonce1Size: num('EXTRANONCE1_SIZE', 4),
  extranonce2Size: num('EXTRANONCE2_SIZE', 8),
  versionMask: parseInt(env('VERSION_MASK', '1fffe000'), 16) >>> 0,

  startDiff: num('START_DIFFICULTY', 1024),
  minDiff: num('MIN_DIFFICULTY', 256),
  maxDiff: num('MAX_DIFFICULTY', 0), // 0 = unlimited
  targetShareSecs: num('TARGET_SHARE_SECS', 8),
  retargetSecs: num('RETARGET_SECS', 30),

  templateRefreshMs: num('TEMPLATE_REFRESH_MS', 30000),
  pollFallbackMs: num('POLL_FALLBACK_MS', 1000),
  instantEmptyJob: bool('INSTANT_EMPTY_JOB', 'true'),
  materialFeeDeltaSats: num('MATERIAL_FEE_DELTA_SATS', 999999999), // since fees don't matter: effectively disabled
  staleGraceMs: num('STALE_GRACE_MS', 3000),
  workerIdleSecs: num('WORKER_IDLE_SECS', 300),
  maxConnections: num('MAX_CONNECTIONS', 500),

  dataDir: env('DATA_DIR', '/data'),
  deviceDomain: env('DEVICE_DOMAIN_NAME', ''),
  deviceHostname: env('DEVICE_HOSTNAME', ''),
};
