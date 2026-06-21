// SINGULARITY main.js
import { CONFIG, VERSION } from './config.js';
import { Rpc } from './rpc.js';
import { ZmqBlockWatcher } from './zmtp.js';
import { TemplateManager } from './template.js';
import { Registry } from './registry.js';
import { StratumServer } from './stratum.js';
import { Dashboard } from './dashboard.js';
import { addressToScript } from './util.js';
import fs from 'node:fs';
import path from 'node:path';

const log = (m) => console.log(`${new Date().toISOString()} ${m}`);

// long-run safety: any state we cannot reason about is worse than a restart.
// Log loudly and exit non-zero — docker's `restart: unless-stopped` revives us
// in seconds with a clean state (and miners reconnect automatically).
process.on('uncaughtException', (e) => { console.error(`FATAL uncaughtException: ${e?.stack || e}`); process.exit(1); });
process.on('unhandledRejection', (e) => { console.error(`FATAL unhandledRejection: ${e?.stack || e}`); process.exit(1); });

async function main() {
  log(`◉ SINGULARITY v${VERSION} solo pool starting`);
  // PAYOUT_ADDRESS اختياري — كل مينر يُعدّن لعنوانه الخاص
  // كل ASIC يضع عنوان Bitcoin الخاص به كـStratum username:
  //   bc1q...youraddress          ← يُعدّن لعنوانه مباشرة
  //   bc1q...youraddress.worker   ← نفس الشيء مع اسم عمل
  // مينر بدون عنوان صالح = يُرفض عند الـauthorize (لحماية المكافأة)
  if (CONFIG.payoutAddress) {
    try {
      const spk = addressToScript(CONFIG.payoutAddress, CONFIG.network);
      log(`payout (pool fallback): ${CONFIG.payoutAddress} -> ${spk.toString('hex')}`);
    } catch (e) { console.error(`PAYOUT_ADDRESS invalid: ${e.message}`); process.exit(1); }
  } else {
    log(`◉ per-miner mode: each ASIC mines to its own address (username = Bitcoin address)`);
    log(`  miners without a valid address will be rejected at authorize`);
  }

  const rpc = new Rpc(CONFIG.rpcUrl, CONFIG.rpcUser, CONFIG.rpcPass);

  // wait for the node
  for (;;) {
    try {
      const info = await rpc.getBlockchainInfo();
      log(`node ok: chain=${info.chain} height=${info.blocks} ibd=${info.initialblockdownload}`);
      if (!info.initialblockdownload) break;
      log('node in initial block download, waiting 15s…');
    } catch (e) { log(`waiting for bitcoind: ${e.message}`); }
    await new Promise((r) => setTimeout(r, 15000));
  }

  const tm = new TemplateManager(rpc, CONFIG);
  tm.on('log', log);

  const registry = new Registry(CONFIG);
  registry.on('block_found', (i) => log(`█ BLOCK ${i.height} ${i.hash} → ${i.submitResult}`));

  const stratum = new StratumServer(CONFIG, tm, registry, rpc);
  stratum.on('log', log);

  const zmq = new ZmqBlockWatcher(CONFIG.zmqBlocks);
  zmq.on('hashblock', (h) => { tm.stats.zmqAlive = true; tm.onNewTip(h, 'zmq').catch((e) => log(`tip error: ${e.message}`)); });
  zmq.on('up', (e) => { tm.stats.zmqAlive = true; log(`zmq up: ${e}`); });
  zmq.on('down', (e) => { tm.stats.zmqAlive = zmq.anyAlive; log(`zmq down: ${e}`); });

  await tm.start();
  zmq.start();
  await stratum.listen();
  log(`stratum listening on ${CONFIG.stratumBind}:${CONFIG.stratumPort}`);

  const dash = new Dashboard(CONFIG, registry, tm);
  await dash.listen();
  log(`dashboard on http://${CONFIG.dashboardBind}:${CONFIG.dashboardPort}`);

  // ---- consensus self-audit ------------------------------------------------
  // Build a real block from the CURRENT template (deliberately unsolved PoW)
  // and ask the user's OWN bitcoind to validate it via GBT proposal mode.
  // "high-hash" = every other consensus rule passed (merkle root, witness
  // commitment, coinbase value/structure, BIP34 height, all txs) — the node
  // itself certifies that a found block WILL be accepted. Runs at startup and
  // every 10 minutes against the freshest template.
  async function selfAudit() {
    try {
      const a = await tm.selfAudit();
      if (a.ok === true) {
        const ej = a.emptyOk === true ? ' · instant-empty-job path certified too' : (a.emptyOk === false ? ` · 🟥 EMPTY-JOB PATH REJECTED: ${a.emptyReason}` : '');
        log(`✅ consensus self-audit PASSED @${a.height} (${a.txs} txs): node says "${a.reason}" — merkle, witness commitment, coinbase and payout all certified by your bitcoind${ej}`);
      } else if (a.ok === false) {
        console.error(`🟥 CONSENSUS SELF-AUDIT FAILED @${a.height}: node rejected our block construction with "${a.reason}" — DO NOT rely on this pool until resolved`);
      }
    } catch (e) {
      log(`self-audit skipped (${e.message}) — will retry`);
    }
  }
  setTimeout(selfAudit, 3000);
  setInterval(selfAudit, 10 * 60 * 1000).unref();

  // hourly heartbeat: one human log line + one JSON line appended to
  // DATA_DIR/stats.jsonl — everything needed to audit health, progress and
  // LUCK over weeks. Key identity: Σ(credited diff) == the mathematically
  // expected best share for the work done, so luck = best / totalDiffSum
  // (1.0 = exactly on expectation; the long-run forensic in one number).
  const startedAt = Date.now();
  setInterval(() => {
    const j = tm.current;
    const hr = registry.poolHashrate();
    const luck = registry.totalDiffSum > 0 ? registry.bestShareEver / registry.totalDiffSum : 0;
    log(`♥ heartbeat: miners=${registry.miners.size} hashrate=${(hr/1e12).toFixed(1)}TH acc=${registry.totalAccepted} rej=${registry.totalRejected} best=${(registry.bestShareEver/1e9).toFixed(2)}G expBest=${(registry.totalDiffSum/1e9).toFixed(2)}G luck=${luck.toFixed(2)} blocks=${registry.blocksFound.length} job=${j ? `${j.kind}@${j.height}` : 'none'} gbt=${tm.stats.gbtMs}ms zmq=${tm.stats.zmqAlive} empty=${tm.stats.emptyJobs} full=${tm.stats.fullJobs}`);
    try {
      const line = JSON.stringify({
        t: new Date().toISOString(), uptimeH: +((Date.now() - startedAt) / 3600000).toFixed(2),
        height: j?.height ?? null, miners: registry.miners.size, hashrate: Math.round(hr),
        accepted: registry.totalAccepted, rejected: registry.totalRejected,
        best: registry.bestShareEver, expBest: registry.totalDiffSum, luck: +luck.toFixed(4),
        blocks: registry.blocksFound.length, gbtMs: tm.stats.gbtMs, zmq: tm.stats.zmqAlive,
        emptyJobs: tm.stats.emptyJobs, fullJobs: tm.stats.fullJobs,
        retarget: tm.stats.retarget ?? null,
      });
      fs.appendFileSync(path.join(CONFIG.dataDir, 'stats.jsonl'), line + '\n');
    } catch { /* stats file is best-effort */ }
  }, 3600 * 1000).unref();

  const shutdown = () => { log('shutting down'); stratum.close(); dash.close(); zmq.stop(); tm.stop(); process.exit(0); };
  process.on('SIGINT', shutdown);
  process.on('SIGTERM', shutdown);
}

main().catch((e) => { console.error(e); process.exit(1); });
