// SINGULARITY registry.js — in-memory miner state. Nothing persists except found blocks.
import { EventEmitter } from 'node:events';
import fs from 'node:fs';

// pure & unit-testable: hashrate (H/s) from a share log over a sliding window
export const HASHRATE_WINDOW_MS = 600000;
export function windowHashrate(shareLog, now, firstSeen) {
  const cutoff = now - HASHRATE_WINDOW_MS;
  // prune in place (log is chronological)
  let drop = 0;
  while (drop < shareLog.length && shareLog[drop][0] < cutoff) drop++;
  if (drop) shareLog.splice(0, drop);
  if (shareLog.length === 0) return 0;
  let sum = 0;
  for (const [, d] of shareLog) sum += d;
  // observation window: capped at WINDOW, never shorter than the miner's life,
  // floored at 30s so one early lucky share can't print an absurd rate
  const elapsed = Math.max(30000, Math.min(HASHRATE_WINDOW_MS, now - firstSeen));
  return (sum * 4294967296) / (elapsed / 1000);
}
import path from 'node:path';
import { nowMs } from './util.js';

export class Registry extends EventEmitter {
  constructor(cfg) {
    super();
    this.cfg = cfg;
    this.miners = new Map();       // workerName -> stats
    this.order = [];               // stable display order (first-seen)
    this.startedAt = nowMs();
    this.bestShareEver = 0;
    this.bestShareWorker = '';
    this.best = null;
    this.totalDiffSum = 0; // Σ credited diff == E[best share] — the luck yardstick
    this.totalAccepted = 0;
    this.totalRejected = 0;
    this.blocksFound = [];
    this.foundPath = path.join(cfg.dataDir, 'found_blocks.jsonl');
    this.purgeTimer = setInterval(() => this.purgeIdle(), 5000);
    try {
      fs.mkdirSync(cfg.dataDir, { recursive: true });
      if (fs.existsSync(this.foundPath)) {
        this.blocksFound = fs.readFileSync(this.foundPath, 'utf8')
          .split('\n').filter(Boolean).map((l) => JSON.parse(l)).slice(-50);
      }
    } catch { /* dataDir optional */ }
  }

  miner(name) {
    let m = this.miners.get(name);
    if (!m) {
      m = {
        name,
        firstSeen: nowMs(),
        lastShare: 0,
        lastSeen: nowMs(),
        sessions: 0,
        accepted: 0,
        rejected: 0,
        rejects: { stale: 0, duplicate: 0, lowdiff: 0, format: 0, ntime: 0, version: 0 },
        lastReject: '',
        stale: 0,
        duplicate: 0,
        bestShare: 0,
        diff: this.cfg.startDiff,
        acceptedDiffSum: 0,
        shareLog: [],
        bestShareHash: '',
        bestShareAt: 0,
        hashrateEma: 0,          // H/s
        lastShareHash: '',
        agent: '',
        address: '',
        versionRolling: false,
      };
      this.miners.set(name, m);
      this.order.push(name);
      this.emit('miner_join', m);
    }
    return m;
  }

  touch(name) {
    const m = this.miners.get(name);
    if (m) m.lastSeen = nowMs();
  }

  // hashrate: 10-minute sliding window over accepted shares, each credited at
  // the EXACT difficulty it was validated against (grace shares at the OLD
  // diff, not the new one). Unbiased: E[Σdiff/sec]·2^32 = true hashrate.
  // 600s at one share / 8s ≈ 75 samples → ±11% statistical noise instead of
  // the ±50-70% the old 15s EMA produced; decays naturally when a device
  // goes quiet instead of freezing at the last value.
  recordAccepted(name, shareDiff, creditDiff, hashHex) {
    const m = this.miner(name);
    const t = nowMs();
    m.accepted++;
    this.totalAccepted++;
    this.totalDiffSum += creditDiff;
    m.lastShare = t;
    m.lastSeen = t;
    m.acceptedDiffSum += creditDiff;
    m.shareLog.push([t, creditDiff]);
    if (m.shareLog.length > 5000) m.shareLog.splice(0, m.shareLog.length - 5000);
    m.lastShareHash = hashHex;
    if (shareDiff > m.bestShare) { m.bestShare = shareDiff; m.bestShareHash = hashHex; m.bestShareAt = t; }
    if (shareDiff > this.bestShareEver) {
      this.bestShareEver = shareDiff;
      this.bestShareWorker = name;
      this.best = { value: shareDiff, worker: name, hash: hashHex, at: t };
      this.emit('best_share', this.best);
    }
  }

  recordRejected(name, reason) {
    const m = this.miner(name);
    m.lastSeen = nowMs();
    m.rejected++;
    this.totalRejected++;
    if (m.rejects[reason] !== undefined) m.rejects[reason]++;
    m.lastReject = reason;
    if (reason === 'stale') m.stale++;
    if (reason === 'duplicate') m.duplicate++;
  }

  recordBlock(info) {
    this.blocksFound.push(info);
    try { fs.appendFileSync(this.foundPath, JSON.stringify(info) + '\n'); }
    catch (e) { console.error(`WARNING: could not persist found block to ${this.foundPath}: ${e.message} (block WAS submitted to bitcoind)`); }
    this.emit('block_found', info);
  }

  purgeIdle() {
    const cutoff = nowMs() - this.cfg.workerIdleSecs * 1000;
    for (const [name, m] of this.miners) {
      if (m.lastSeen < cutoff && m.sessions === 0) {
        this.miners.delete(name);
        this.order = this.order.filter((n) => n !== name);
        this.emit('miner_gone', name);
      }
    }
  }

  poolHashrate(now = nowMs()) {
    let h = 0;
    for (const m of this.miners.values()) h += windowHashrate(m.shareLog, now, m.firstSeen);
    return h;
  }

  snapshot(job, tmStats) {
    return {
      now: nowMs(),
      startedAt: this.startedAt,
      poolHashrate: this.poolHashrate(),
      bestShareEver: this.bestShareEver,
      bestShareWorker: this.bestShareWorker,
      best: this.best,
      totalAccepted: this.totalAccepted,
      totalDiffSum: this.totalDiffSum,
      totalRejected: this.totalRejected,
      job: job ? {
        id: job.id, height: job.height, kind: job.kind,
        prevhash: job.prevhashBE, txCount: job.txs.length,
        valueSats: job.valueSats.toString(), networkDiff: job.networkDiff,
        age: nowMs() - job.createdAt, nbits: job.nbits, clean: job.clean,
      } : null,
      tm: tmStats,
      blocksFound: this.blocksFound.slice(-10),
      miners: this.order.map((n) => {
        const m = this.miners.get(n);
        if (!m) return null;
        return {
          name: m.name, hashrate: windowHashrate(m.shareLog, nowMs(), m.firstSeen), diff: m.diff,
          accepted: m.accepted, rejected: m.rejected, stale: m.stale,
          duplicate: m.duplicate, bestShare: m.bestShare,
          lastShare: m.lastShare, sessions: m.sessions,
          lastShareHash: m.lastShareHash, agent: m.agent, address: m.address,
          bestShareHash: m.bestShareHash, bestShareAt: m.bestShareAt,
          rejects: m.rejects, lastReject: m.lastReject,
          versionRolling: m.versionRolling, firstSeen: m.firstSeen,
        };
      }).filter(Boolean),
    };
  }
}
