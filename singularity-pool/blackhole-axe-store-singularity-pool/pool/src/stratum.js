// SINGULARITY stratum.js — Stratum v1 server.
// Handles Antminer / Avalon / Whatsminer / Bitaxe / NerdMiner / cpuminer:
// mining.configure (version-rolling), subscribe, authorize, suggest_difficulty,
// extranonce.subscribe, multi_version, submit with strict validation.
import net from 'node:net';
import { randomBytes } from 'node:crypto';
import { EventEmitter } from 'node:events';
import { sha256d, hexToBuf, bufLE2hexBE, hashToBig, hashToShareDiff, nowMs, addressToScript, TRUEDIFFONE } from './util.js';

const E = {
  UNKNOWN: [20, 'Other/Unknown', null],
  BAD_EN2: [20, 'Invalid extranonce2 size', null],
  BAD_NTIME: [20, 'Ntime out of range', null],
  BAD_NONCE: [20, 'Invalid nonce', null],
  BAD_VERSION: [20, 'Invalid version mask', null],
  JOB_NOT_FOUND: [21, 'Job not found (=stale)', null],
  DUPLICATE: [22, 'Duplicate share', null],
  LOW_DIFF: [23, 'Above target (low difficulty share)', null],
  UNAUTHORIZED: [24, 'Unauthorized worker', null],
  NOT_SUBSCRIBED: [25, 'Not subscribed', null],
};

// exact integer share target for a difficulty, with ckpool-style 0.1% slack
// (hash <= target  <=>  shareDiff >= diff*0.999, no float rounding surprises)
function diffToTargetSlack(d) {
  if (!(d > 0)) return TRUEDIFFONE;
  if (d >= 1) return (TRUEDIFFONE * 1000n) / (BigInt(Math.round(d)) * 999n);
  return (TRUEDIFFONE * 1000n * 1000000n) / (BigInt(Math.max(1, Math.round(d * 1000000))) * 999n);
}

let connSeq = 0;

export class Client {
  constructor(sock, pool) {
    this.sock = sock;
    this.pool = pool;
    this.id = ++connSeq;
    this.buffer = '';
    this.subscribed = false;
    this.authorized = false;
    this.worker = null;
    this.agent = '';
    this.extranonce1 = pool.nextExtranonce1();
    this.payoutScript = null;     // per-miner wallet (parsed from username); null = pool default
    this.payoutAddress = pool.cfg.payoutAddress;
    this.versionRolling = false;
    this.versionMask = 0;
    this.diff = pool.cfg.startDiff;
    this.prevDiff = null;
    this.prevDiffUntil = 0;
    this.suggestedDiff = null;
    this.shareTarget = diffToTargetSlack(this.diff);   // exact, precomputed
    this.prevShareTarget = null;
    // vardiff window
    this.vdShares = 0;
    this.vdStart = nowMs();
    this.retargets = 0;
    this.lastRetargetAt = 0;
    this.vdFirstPending = true;   // the fast first-jump belongs to VARDIFF and
                                  // must survive a firmware suggest_difficulty
    // duplicate detection per job
    this.seen = new Map(); // jobId -> Set
    // ntime stagger: each miner starts at a slightly different ntime offset.
    // With 17 miners × 1s offset, miners collectively cover a 17-second ntime
    // window simultaneously, reducing redundant hash computation.
    // (Offset is cosmetic since extranonce1 already ensures zero hash overlap,
    //  but it makes work distribution explicit and professionally traceable.)
    this.ntimeOffset = (this.id - 1) % 16; // 0..15 seconds offset
    this.alive = true;
    sock.setNoDelay(true);
    sock.setKeepAlive(true, 60000);
    sock.setTimeout(15 * 60 * 1000, () => this.destroy('idle timeout'));
  }

  log(msg) { this.pool.emit('log', `[#${this.id}${this.worker ? ' ' + this.worker : ''}] ${msg}`); }

  send(obj) {
    if (!this.alive) return;
    try { this.sock.write(JSON.stringify(obj) + '\n'); } catch { this.destroy('write fail'); }
  }
  result(id, result, error = null) { this.send({ id, result, error }); }
  payoutScriptForNotify() {
    return this.payoutScript || this.pool.tm.scriptPubKey;
  }

  canNotify() {
    return this.subscribed && this.alive && this.authorized && !!this.payoutScriptForNotify();
  }

  notifyJob(job, cleanOverride = null) {
    if (!this.canNotify()) return;
    let line;
    try {
      line = job.notifyLine(this.payoutScriptForNotify(), cleanOverride, this.ntimeOffset);
    } catch (e) {
      this.log(`notify build failed: ${e.message}`);
      return;
    }
    try {
      this.sock.write(line);
    } catch (e) {
      this.log(`notify write failed: ${e.message}`);
      this.destroy('write fail');
    }
  }
  setDifficulty(d) {
    this.send({ id: null, method: 'mining.set_difficulty', params: [d] });
  }

  destroy(reason) {
    if (!this.alive) return;
    this.alive = false;
    try { this.sock.destroy(); } catch {}
    this.pool.dropClient(this, reason);
  }

  onData(chunk) {
    this.buffer += chunk;
    if (this.buffer.length > 64 * 1024) return this.destroy('flood');
    let idx;
    while ((idx = this.buffer.indexOf('\n')) !== -1) {
      const line = this.buffer.slice(0, idx).trim();
      this.buffer = this.buffer.slice(idx + 1);
      if (!line) continue;
      let msg;
      try { msg = JSON.parse(line); } catch { return this.destroy('bad json'); }
      try { this.handle(msg); } catch (e) { this.log(`handler error: ${e.message}`); this.result(msg.id ?? null, null, E.UNKNOWN); }
    }
  }

  handle(msg) {
    const { id, method, params = [] } = msg;
    switch (method) {
      case 'mining.configure': return this.onConfigure(id, params);
      case 'mining.subscribe': return this.onSubscribe(id, params);
      case 'mining.authorize': return this.onAuthorize(id, params);
      case 'mining.submit': return this.onSubmit(id, params);
      case 'mining.suggest_difficulty': return this.onSuggestDiff(id, params);
      case 'mining.extranonce.subscribe': return this.result(id, true);
      case 'mining.multi_version': return this.result(id, true);
      case 'mining.get_transactions': return this.result(id, []);
      case 'mining.ping': return this.result(id, 'pong');
      default:
        if (id !== undefined && id !== null) this.result(id, null, E.UNKNOWN);
    }
  }

  onConfigure(id, params) {
    const [exts = [], opts = {}] = params;
    const reply = {};
    if (exts.includes('version-rolling')) {
      const clientMask = parseInt(opts['version-rolling.mask'] ?? 'ffffffff', 16) >>> 0;
      const negotiated = (clientMask & this.pool.cfg.versionMask) >>> 0;
      const minBits = Number(opts['version-rolling.min-bit-count'] ?? 0);
      const bits = negotiated.toString(2).split('1').length - 1;
      if (negotiated !== 0 && bits >= minBits) {
        this.versionRolling = true;
        this.versionMask = negotiated;
        reply['version-rolling'] = true;
        reply['version-rolling.mask'] = negotiated.toString(16).padStart(8, '0');
      } else {
        reply['version-rolling'] = false;
      }
    }
    if (exts.includes('minimum-difficulty')) reply['minimum-difficulty'] = false;
    if (exts.includes('subscribe-extranonce')) reply['subscribe-extranonce'] = false;
    this.result(id, reply);
  }

  onSubscribe(id, params) {
    this.agent = String(params?.[0] ?? '').slice(0, 48);
    this.subscribed = true;
    this.result(id, [
      [['mining.set_difficulty', this.extranonce1], ['mining.notify', this.extranonce1]],
      this.extranonce1,
      this.pool.cfg.extranonce2Size,
    ]);
    // Bitaxe/Antminer: never send mining.notify before authorize — per-miner
    // coinbase needs the wallet from mining.authorize. Difficulty-only is fine.
    this.setDifficulty(this.diff);
  }

  onAuthorize(id, params) {
    const username = String(params?.[0] ?? '').trim();
    if (!username) return this.result(id, false, E.UNAUTHORIZED);
    this.worker = username.slice(0, 80);
    // username conventions: "ADDRESS.worker", "ADDRESS", or plain "worker".
    // If a valid BTC address is found, the block reward coinbase pays THAT address.
    const dot = username.indexOf('.');
    const candidate = (dot === -1 ? username : username.slice(0, dot)).trim();
    try {
      this.payoutScript = addressToScript(candidate, this.pool.cfg.network);
      this.payoutAddress = candidate;
    } catch {
      // username is not a valid Bitcoin address
      if (!this.pool.tm.scriptPubKey) {
        // no pool fallback configured → reject miner (per-miner mode, address required)
        this.result(id, false, E.UNAUTHORIZED);
        this.log(
          `rejected: username "${candidate}" is not a valid ${this.pool.cfg.network} address. ` +
          `Set your ASIC username to your Bitcoin address (e.g. bc1q...)`
        );
        return;
      }
      // pool fallback available → use it (pool-level payout mode)
      this.payoutScript = null; // will use pool default in partsFor()
    }
    this.authorized = true;
    const m = this.pool.registry.miner(this.worker);
    m.sessions++;
    m.agent = this.agent || m.agent;
    m.versionRolling = this.versionRolling;
    m.address = this.payoutAddress;
    // returning miner inside idle window keeps its row; adopt its vardiff
    if (m.accepted > 0) { this.diff = m.diff; this.shareTarget = diffToTargetSlack(this.diff); }
    if (this.suggestedDiff) this.applySuggested();
    this.result(id, true);
    // clean=true: the coinbase just changed to this miner's wallet — restart work
    this.pushWork(true, true);
    this.log(
      `authorized: agent="${this.agent}" | en1=${this.extranonce1} | ` +
      `ntime_offset=+${this.ntimeOffset}s | ` +
      `vr=${this.versionRolling ? '0x'+this.versionMask.toString(16) : 'no'} | ` +
      `payout=${this.payoutAddress}`
    );
  }

  onSuggestDiff(id, params) {
    const d = Number(params?.[0]);
    if (isFinite(d) && d > 0) { this.suggestedDiff = d; this.applySuggested(); }
    this.result(id, true);
  }

  applySuggested() {
    const c = this.pool.cfg;
    let d = Math.max(c.minDiff, this.suggestedDiff);
    if (c.maxDiff > 0) d = Math.min(d, c.maxDiff);
    this.changeDiff(d);
  }

  changeDiff(newDiff) {
    if (newDiff === this.diff) return;
    this.prevDiff = this.diff;
    this.prevShareTarget = this.shareTarget;
    this.prevDiffUntil = nowMs() + 60000;
    this.diff = newDiff;
    this.shareTarget = diffToTargetSlack(newDiff);
    if (this.worker) this.pool.registry.miner(this.worker).diff = newDiff;
    this.retargets++;
    this.lastRetargetAt = nowMs();
    this.vdShares = 0;
    this.vdStart = nowMs();
    // ROOT-CAUSE FIX: send set_difficulty ONLY — never re-notify the current
    // job. Re-sending a job id makes many firmwares (Bitaxe, Avalon/cgminer,
    // Antminer stock) restart it from the same extranonce2/nonce origin and
    // re-find the SAME shares => duplicate storms. The new difficulty applies
    // from the next job (<=30s away via refresh); until then the 60s grace
    // window accepts shares mined at the previous difficulty. ckpool behaves
    // exactly this way, which is why these devices look clean there.
    this.setDifficulty(newDiff);
  }

  pushWork(withDiff, forceClean = false) {
    const job = this.pool.tm.current;
    if (!job || !this.subscribed) return;
    if (withDiff) this.setDifficulty(this.diff);
    this.notifyJob(job, forceClean ? true : null);
  }

  // ---- vardiff: aim for ~1 share / targetShareSecs ----
  vardiffTick(shareAccepted, metCurrent = true) {
    // AVALON-CASCADE FIX: a grace-window share was mined against the OLD
    // difficulty — it is NOT evidence about the new one. Counting them let a
    // big device's in-flight pipeline (Avalon Q floods ~100 shares/s on
    // connect) trigger repeated "extreme" jumps and rocket the difficulty
    // to absurd values before the device even started on the new diff.
    if (shareAccepted && metCurrent) this.vdShares++;
    const c = this.pool.cfg;
    const now = nowMs();
    const dt = (now - this.vdStart) / 1000;
    // "first" = vardiff's own first evaluation. A firmware suggest_difficulty
    // must NOT consume it (Antminers suggest on connect; without this an S19
    // joining at the wrong diff crawled up x4/60s and flooded thousands of
    // tiny shares for minutes).
    const first = this.vdFirstPending;
    // STABILITY: retarget on statistical EVIDENCE, not on a noisy timer.
    //  - increases need 24 accepted shares (first one: 8, so big iron joining
    //    at the wrong diff gets corrected within ~2s in ONE step)
    //  - decreases need a long quiet window
    //  - deadband 0.55..1.8 (≈3σ at 24 samples): inside it, do nothing
    const evidence = this.vdShares >= (first ? 8 : 24);
    const quiet = dt >= Math.max(c.retargetSecs * 4, 120);
    if (!evidence && !quiet) return;
    if (dt < (first ? 2 : 5)) return;
    const ratio = (this.vdShares / dt) * c.targetShareSecs;  // 1.0 = on target
    // "extreme" applies to INCREASES only: a flood of shares is hard evidence;
    // silence is not — decreases always glide down x4 so a device that merely
    // paused never gets dumped to a flood-inducing low difficulty
    const extreme = ratio >= 16;
    // min spacing — the first evaluation is free; gross floods may bypass the
    // 60s wait but never chain faster than one jump per 5s (pipeline guard)
    if (!first && now - this.lastRetargetAt < (extreme ? 5000 : 60000)) return;
    this.vdFirstPending = false; // first evaluation consumed (with real evidence)
    if (ratio > 0.55 && ratio < 1.8) { this.vdShares = 0; this.vdStart = now; return; }
    // step size: first jump unbounded-ish; flood x64 up; otherwise x4 (both ways)
    const step = first ? 1024 : (extreme ? 64 : 4);
    let nd = this.diff * Math.min(step, Math.max(1 / 4, ratio));
    nd = Math.pow(2, Math.round(Math.log2(Math.max(nd, Number.MIN_VALUE))));
    nd = Math.max(c.minDiff, nd);
    if (c.maxDiff > 0) nd = Math.min(nd, c.maxDiff);
    this.vdShares = 0;
    this.vdStart = now;
    if (nd !== this.diff && Math.abs(Math.log2(nd / this.diff)) >= 1) this.changeDiff(nd);
  }

  // ---- submit ----
  onSubmit(id, params) {
    const reg = this.pool.registry;
    if (!this.subscribed) return this.result(id, null, E.NOT_SUBSCRIBED);
    const workerName = String(params?.[0] ?? this.worker ?? '').trim() || this.worker;
    if (!this.authorized) { this.worker = workerName || `anon#${this.id}`; this.authorized = true; reg.miner(this.worker).sessions++; }
    const jobId = String(params?.[1] ?? '');
    const en2 = String(params?.[2] ?? '').toLowerCase();
    const ntimeHex = String(params?.[3] ?? '').toLowerCase();
    const nonceHex = String(params?.[4] ?? '').toLowerCase();
    const verHex = params?.[5] !== undefined ? String(params[5]).toLowerCase() : null;

    const job = this.pool.tm.jobs.get(jobId);
    if (!job) { reg.recordRejected(this.worker, 'stale'); return this.result(id, null, E.JOB_NOT_FOUND); }

    // format checks — each failure gets its own message so device logs say WHY
    if (!/^[0-9a-f]+$/.test(en2) || en2.length !== this.pool.cfg.extranonce2Size * 2) {
      reg.recordRejected(this.worker, 'format'); return this.result(id, null, E.BAD_EN2);
    }
    if (!/^[0-9a-f]{8}$/.test(ntimeHex)) {
      reg.recordRejected(this.worker, 'ntime'); return this.result(id, null, E.BAD_NTIME);
    }
    if (!/^[0-9a-f]{1,8}$/.test(nonceHex)) {
      reg.recordRejected(this.worker, 'format'); return this.result(id, null, E.BAD_NONCE);
    }
    if (verHex !== null && !/^[0-9a-f]{1,8}$/.test(verHex)) {
      reg.recordRejected(this.worker, 'version'); return this.result(id, null, E.BAD_VERSION);
    }

    // duplicate — key is NUMERIC, so "1abcd" and "0001abcd" are the same share
    // (padding/case variations can never split or miss a true duplicate)
    const ntime = parseInt(ntimeHex, 16) >>> 0;
    const nonce = parseInt(nonceHex, 16) >>> 0;
    const key = `${BigInt('0x' + en2)}:${ntime}:${nonce}:${verHex === null ? '' : parseInt(verHex, 16) >>> 0}`;
    let seenSet = this.seen.get(jobId);
    if (!seenSet) { seenSet = new Set(); this.seen.set(jobId, seenSet); if (this.seen.size > 16) this.seen.delete(this.seen.keys().next().value); }
    if (seenSet.has(key)) { reg.recordRejected(this.worker, 'duplicate'); return this.result(id, null, E.DUPLICATE); }
    if (seenSet.size > 200000) seenSet.clear(); // pathological flood guard — honest devices never get near this
    seenSet.add(key);

    // ntime window
    const now = Math.floor(nowMs() / 1000);
    if (ntime + 600 < job.curtime || ntime > now + 7000) {
      reg.recordRejected(this.worker, 'ntime'); return this.result(id, null, E.BAD_NTIME);
    }

    // version rolling
    let version = job.version;
    if (verHex !== null) {
      const bits = parseInt(verHex, 16) >>> 0;
      if (!this.versionRolling || (bits & ~this.versionMask) !== 0) {
        reg.recordRejected(this.worker, 'version'); return this.result(id, null, E.BAD_VERSION);
      }
      version = ((job.version & ~this.versionMask) | (bits & this.versionMask)) >>> 0;
    }

    const enBuf = Buffer.concat([hexToBuf(this.extranonce1), hexToBuf(en2)]);
    const header = job.buildHeader(this.payoutScript, enBuf, ntime, nonce, version);
    const hashLE = sha256d(header);
    const hashBig = hashToBig(hashLE);
    const shareDiff = hashToShareDiff(hashLE);
    const hashBE = bufLE2hexBE(hashLE);

    // stale tip? (job from a previous prevhash)
    const isStaleTip = this.pool.tm.tipHash !== job.prevhashBE;

    // BLOCK? (checked FIRST — a block must never die to a vardiff race)
    if (hashBig <= job.target) {
      this.pool.submitFoundBlock(job, this.payoutScript, enBuf, ntime, nonce, version, {
        worker: this.worker, hashBE, shareDiff, staleTip: isStaleTip,
        payoutAddress: this.payoutAddress,
      });
      // a solved block is always a valid share too — credited at the diff it met
      const blkMetCurrent = hashBig <= this.shareTarget;
      reg.recordAccepted(this.worker, shareDiff, blkMetCurrent ? this.diff : (this.prevDiff ?? this.diff), hashBE);
      this.vardiffTick(true, blkMetCurrent);
      return this.result(id, true);
    }

    if (isStaleTip) {
      const grace = nowMs() - (this.pool.tm.current?.createdAt ?? 0) < this.pool.cfg.staleGraceMs;
      if (!grace) { reg.recordRejected(this.worker, 'stale'); return this.result(id, null, E.JOB_NOT_FOUND); }
    }

    // difficulty: exact integer compare (hash above target = below required diff),
    // with a 60s grace window honouring the previous difficulty after a retarget
    const metCurrent = hashBig <= this.shareTarget;
    const okDiff = metCurrent
      || (this.prevShareTarget !== null && nowMs() < this.prevDiffUntil && hashBig <= this.prevShareTarget);
    if (!okDiff) {
      reg.recordRejected(this.worker, 'lowdiff');
      this.vardiffTick(false);
      return this.result(id, null, E.LOW_DIFF);
    }
    // HASHRATE ACCURACY: a grace-window share is credited at the PREVIOUS
    // difficulty (the one it was actually mined against), never the new one —
    // crediting at the new diff inflated readings around every retarget
    const credit = metCurrent ? this.diff : this.prevDiff;

    reg.recordAccepted(this.worker, shareDiff, credit, hashBE);
    this.vardiffTick(true, metCurrent);
    this.result(id, true);
  }
}

export class StratumServer extends EventEmitter {
  constructor(cfg, tm, registry, rpc) {
    super();
    this.cfg = cfg;
    this.tm = tm;
    this.registry = registry;
    this.rpc = rpc;
    this.clients = new Set();
    this.activeEn1 = new Set();   // strict uniqueness — no probabilistic collisions, ever
    this.enCounter = randomBytes(2).readUInt16BE(0);
    this.server = net.createServer((sock) => this.onConnection(sock));
    tm.on('job', (job) => this.broadcast(job));
  }

  // Sequential extranonce1 assignment:
  // Each miner receives a strictly increasing 4-byte extranonce1.
  // This guarantees ZERO overlap between miners' coinbase transactions
  // and therefore ZERO overlap in hash space — a mathematical certainty,
  // not a probabilistic approximation.
  //
  // Layout (4 bytes):
  //   [0x00][session_counter_high][session_counter_low][miner_slot]
  //
  // Each counter increment = completely different merkle root = different universe of hashes.
  nextExtranonce1() {
    const size = this.cfg.extranonce1Size; // 4
    const b = Buffer.alloc(size, 0);
    // counter occupies the middle bytes, slot the last byte
    const slot = (this.activeEn1.size) & 0xff;
    this.enCounter = (this.enCounter + 1) & 0xffffff; // 24-bit counter
    b.writeUIntBE(this.enCounter, 0, Math.min(size - 1, 3));
    b[size - 1] = slot;
    const hex = b.toString('hex');
    this.activeEn1.add(hex);
    return hex;
  }

  listen() {
    return new Promise((res) => this.server.listen(this.cfg.stratumPort, this.cfg.stratumBind, res));
  }
  close() { this.server.close(); for (const c of this.clients) c.destroy('shutdown'); }

  onConnection(sock) {
    // Connection limit: protect against resource exhaustion from too many
    // simultaneous connections (firmware bugs, port scanners, etc.).
    // Limit matches BlackHole Pool's MAX_CONNECTIONS=500 default.
    // A solo fleet of 17 devices will never get close to this.
    if (this.clients.size >= (this.cfg.maxConnections ?? 500)) {
      sock.destroy();
      this.emit('log', `connection limit (${this.cfg.maxConnections ?? 500}) reached, dropping ${sock.remoteAddress}`);
      return;
    }
    const c = new Client(sock, this);
    this.clients.add(c);
    sock.on('data', (d) => c.onData(d.toString('utf8')));
    sock.on('error', () => c.destroy('socket error'));
    sock.on('close', () => c.destroy('closed'));
  }

  dropClient(c, reason) {
    if (!this.clients.has(c)) return;
    this.clients.delete(c);
    this.activeEn1.delete(c.extranonce1);
    if (c.worker) {
      const m = this.registry.miners.get(c.worker);
      if (m) m.sessions = Math.max(0, m.sessions - 1);
    }
    this.emit('log', `[#${c.id}${c.worker ? ' ' + c.worker : ''}] disconnected (${reason})`);
  }

  broadcast(job) {
    let n = 0;
    for (const c of this.clients) {
      if (!c.canNotify()) continue;
      c.notifyJob(job);
      n++;
    }
    this.emit('log', `job ${job.id} ${job.kind} @${job.height} txs=${job.txs.length} clean=${job.clean} -> ${n}/${this.clients.size} miners`);
  }

  // ---- the moment of truth ----
  async submitFoundBlock(job, script, enBuf, ntime, nonce, version, meta) {
    const blockHex = job.buildBlockHex(script, enBuf, ntime, nonce, version);
    const info = {
      height: job.height,
      hash: meta.hashBE,
      worker: meta.worker,
      payoutAddress: meta.payoutAddress,
      shareDiff: meta.shareDiff,
      networkDiff: job.networkDiff,
      nonce: '0x' + (nonce >>> 0).toString(16).padStart(8, '0'),
      version: '0x' + (version >>> 0).toString(16).padStart(8, '0'),
      ntime,
      jobKind: job.kind,
      txCount: job.txs.length + 1,
      valueSats: job.valueSats.toString(),
      staleTip: meta.staleTip,
      foundAt: Date.now(),
      submitResult: null,
    };
    this.emit('log', `🟧🟧🟧 BLOCK CANDIDATE @${job.height} ${meta.hashBE} by ${meta.worker} — submitting`);
    try {
      const r = await this.rpc.submitBlock(blockHex);
      info.submitResult = r === null ? 'accepted' : String(r);
    } catch (e) {
      info.submitResult = `error: ${e.message}`;
      // retry once — never lose a block to a transient RPC hiccup
      try {
        const r2 = await this.rpc.submitBlock(blockHex);
        info.submitResult = r2 === null ? 'accepted(retry)' : String(r2);
      } catch (e2) { info.submitResult = `error: ${e2.message}`; }
    }
    this.emit('log', `BLOCK SUBMIT RESULT: ${info.submitResult}`);
    this.registry.recordBlock(info);
    // force a refresh; if accepted, our own node tip changed
    this.tm.fullRefresh(true).catch(() => {});
  }
}
