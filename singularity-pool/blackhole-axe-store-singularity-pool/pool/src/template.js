// SINGULARITY template.js — the critical path.
// New tip (ZMQ) -> instant empty-subsidy job in ~1ms (miners never hash a dead tip)
// -> full getblocktemplate job follows -> slow refresh keeps ntime fresh.
import { EventEmitter } from 'node:events';
import {
  sha256d, hexToBuf, bufToHex, hexBE2bufLE, bufLE2hexBE, swap32, varint,
  u32LE, u64LE, bip34Push, nbitsToTarget, targetToDiff, addressToScript, subsidyAt, nowMs,
} from './util.js';

// ---- coinbase ----------------------------------------------------------
// Layout: [version][in: null prevout][scriptSig = BIP34(height) + tag + EN1 + EN2][seq]
//         [outs: payout, witness-commitment][locktime]
// coinb1/coinb2 are the LEGACY serialization split around the extranonce
// (txid excludes witness, so the miner-side hash is correct).
// For block submission we re-serialize WITH the segwit marker and the
// 32-byte witness reserved value, as consensus requires.
export function buildCoinbaseParts({ height, valueSats, scriptPubKey, tag, enTotal, witnessCommitment }) {
  const sigPre = Buffer.concat([bip34Push(height), Buffer.from(tag, 'utf8')]);
  const scriptLen = sigPre.length + enTotal;
  if (scriptLen > 100) throw new Error('coinbase scriptSig too long');

  const head = Buffer.concat([
    u32LE(2),                       // tx version
    varint(1),                      // input count
    Buffer.alloc(32, 0),            // prevout hash
    Buffer.from('ffffffff', 'hex'), // prevout index
    varint(scriptLen),
    sigPre,                         // ... extranonce goes here
  ]);

  const outs = [];
  outs.push(Buffer.concat([u64LE(valueSats), varint(scriptPubKey.length), scriptPubKey]));
  if (witnessCommitment) {
    const wc = hexToBuf(witnessCommitment); // full scriptPubKey from Core (6a24aa21a9ed...)
    outs.push(Buffer.concat([u64LE(0n), varint(wc.length), wc]));
  }
  const tail = Buffer.concat([
    // BIP54 forward-compatibility (Consensus Cleanup): the coinbase nSequence
    // must NOT be final and nLockTime must equal height-1, so every coinbase
    // is provably unique and BIP30 validation can die forever. Valid under
    // today's rules too (locktime height-1 => final exactly at our height),
    // and guarantees blocks stay valid the day BIP54 activates.
    Buffer.from('feffffff', 'hex'), // sequence 0xfffffffe (not final), LE
    varint(outs.length),
    ...outs,
    u32LE(height - 1),              // nLockTime = height - 1 (BIP54)
  ]);

  return { coinb1: head, coinb2: tail, hasWitness: !!witnessCommitment };
}

export function coinbaseLegacy(parts, enBuf) {
  return Buffer.concat([parts.coinb1, enBuf, parts.coinb2]);
}

export function coinbaseWithWitness(parts, enBuf) {
  if (!parts.hasWitness) return coinbaseLegacy(parts, enBuf);
  const legacy = coinbaseLegacy(parts, enBuf);
  // splice marker+flag after version, witness stack before locktime
  const version = legacy.subarray(0, 4);
  const middle = legacy.subarray(4, legacy.length - 4);
  const locktime = legacy.subarray(legacy.length - 4);
  const witness = Buffer.concat([varint(1), varint(32), Buffer.alloc(32, 0)]);
  return Buffer.concat([version, Buffer.from([0x00, 0x01]), middle, witness, locktime]);
}

// ---- merkle ------------------------------------------------------------
// Stratum branch: fold from the coinbase txid upward.
export function merkleBranch(txidsLE) {
  const branch = [];
  let level = [null, ...txidsLE];
  while (level.length > 1) {
    if (level.length % 2) level.push(level[level.length - 1]);
    branch.push(level[1]);
    const next = [null];
    for (let i = 2; i < level.length; i += 2) {
      next.push(sha256d(Buffer.concat([level[i], level[i + 1]])));
    }
    level = next;
  }
  return branch;
}

export function merkleRootFromBranch(coinbaseTxidLE, branch) {
  let h = coinbaseTxidLE;
  for (const b of branch) h = sha256d(Buffer.concat([h, b]));
  return h;
}

// full root from complete txid list (used in tests for cross-validation)
export function merkleRootFull(txidsLE) {
  let level = txidsLE.slice();
  if (level.length === 0) return Buffer.alloc(32, 0);
  while (level.length > 1) {
    if (level.length % 2) level.push(level[level.length - 1]);
    const next = [];
    for (let i = 0; i < level.length; i += 2)
      next.push(sha256d(Buffer.concat([level[i], level[i + 1]])));
    level = next;
  }
  return level[0];
}

// ---- job ---------------------------------------------------------------
// pure & unit-testable: difficulty retarget estimate from the node's own chain
// (no external services — your node knows everything needed)
export function computeRetarget({ tipHeight, firstTs, now }) {
  const epochStart = Math.floor(tipHeight / 2016) * 2016;
  const mined = tipHeight - epochStart;             // blocks after the epoch's first
  if (mined < 10) return null;                      // too early to estimate
  const avgBlockSecs = (now - firstTs) / mined;
  if (!(avgBlockSecs > 0)) return null;
  let estChangePct = (600 / avgBlockSecs - 1) * 100;
  estChangePct = Math.max(-75, Math.min(300, estChangePct)); // consensus clamp x4 / /4
  const retargetHeight = epochStart + 2016;
  const remainingBlocks = retargetHeight - tipHeight;
  return {
    retargetHeight,
    remainingBlocks,
    progressPct: (mined / 2016) * 100,
    avgBlockSecs,
    estChangePct,
    etaDays: (remainingBlocks * avgBlockSecs) / 86400,
  };
}

let jobSeq = 0;

export class Job {
  constructor({ template, prevhashBE, height, version, nbits, curtime, valueSats, txs, witnessCommitment, clean, scriptPubKey, tag, enTotal, kind }) {
    this.id = (++jobSeq).toString(16).padStart(4, '0');
    this.kind = kind; // 'empty' | 'full' | 'refresh'
    this.height = height;
    this.prevhashBE = prevhashBE;
    this.prevhashLE = hexBE2bufLE(prevhashBE);
    this.version = version >>> 0;
    this.nbits = nbits;                       // hex string
    this.curtime = curtime;                   // uint
    this.valueSats = valueSats;
    this.txs = txs;                           // [{data, txidLE}]
    this.clean = clean;
    this.createdAt = nowMs();
    this.target = nbitsToTarget(nbits);
    this.networkDiff = targetToDiff(this.target);

    // per-payout-address coinbase parts (each miner can mine to its own wallet)
    this.tag = tag;
    this.enTotal = enTotal;
    this.witnessCommitment = witnessCommitment;
    this.defaultScript = scriptPubKey;
    this.partsCache = new Map(); // scriptHex -> parts
    this.branch = merkleBranch(txs.map((t) => t.txidLE));
    this.branchHex = this.branch.map(bufToHex);
    this.prevhashStratum = bufToHex(swap32(this.prevhashLE));
  }

  partsFor(script) {
    const s = script || this.defaultScript;
    if (!s) throw new Error(
      'No payout script: miner has no valid Bitcoin address and PAYOUT_ADDRESS is not set. ' +
      'Set the miner Stratum username to a valid Bitcoin address (e.g. bc1q...).'
    );
    const key = s.toString('hex');
    let p = this.partsCache.get(key);
    if (!p) {
      p = buildCoinbaseParts({
        height: this.height, valueSats: this.valueSats, scriptPubKey: s,
        tag: this.tag, enTotal: this.enTotal, witnessCommitment: this.witnessCommitment,
      });
      p.coinb1Hex = bufToHex(p.coinb1);
      p.coinb2Hex = bufToHex(p.coinb2);
      this.partsCache.set(key, p);
    }
    return p;
  }

  notifyParams(script, cleanOverride = null, ntimeOffset = 0) {
    const p = this.partsFor(script);
    // per-miner ntime: base curtime + miner's stagger offset
    // ensures miners search different ntime lanes simultaneously
    const ntime = (this.curtime + ntimeOffset) >>> 0;
    return [
      this.id,
      this.prevhashStratum,
      p.coinb1Hex,
      p.coinb2Hex,
      this.branchHex,
      this.version.toString(16).padStart(8, '0'),
      this.nbits,
      ntime.toString(16).padStart(8, '0'),
      cleanOverride === null ? this.clean : cleanOverride,
    ];
  }

  // pre-serialized notify line (broadcast fast path: one cached string per
  // wallet per job — fanning out to N miners is N raw socket writes, ~0 CPU)
  notifyLine(script, cleanOverride = null, ntimeOffset = 0) {
    // cache key includes ntimeOffset — each miner's notify is unique
    const key = (script ? script.toString('hex') : 'd')
      + '|' + (cleanOverride === null ? 'j' : cleanOverride ? '1' : '0')
      + '|' + ntimeOffset;
    if (!this.lineCache) this.lineCache = new Map();
    let line = this.lineCache.get(key);
    if (!line) {
      line = JSON.stringify({
        id: null,
        method: 'mining.notify',
        params: this.notifyParams(script, cleanOverride, ntimeOffset),
      }) + '\n';
      this.lineCache.set(key, line);
    }
    return line;
  }

  // header (80 bytes, internal byte order) for a submitted share
  buildHeader(script, enBuf, ntime, nonce, version) {
    const cbTxid = sha256d(coinbaseLegacy(this.partsFor(script), enBuf));
    const root = merkleRootFromBranch(cbTxid, this.branch);
    const h = Buffer.alloc(80);
    h.writeUInt32LE(version >>> 0, 0);
    this.prevhashLE.copy(h, 4);
    root.copy(h, 36);
    h.writeUInt32LE(ntime >>> 0, 68);
    h.writeUInt32LE(parseInt(this.nbits, 16) >>> 0, 72);
    h.writeUInt32LE(nonce >>> 0, 76);
    return h;
  }

  buildBlockHex(script, enBuf, ntime, nonce, version) {
    const header = this.buildHeader(script, enBuf, ntime, nonce, version);
    const cb = coinbaseWithWitness(this.partsFor(script), enBuf);
    const chunks = [header, varint(this.txs.length + 1), cb];
    for (const t of this.txs) chunks.push(t.dataBuf);
    return bufToHex(Buffer.concat(chunks));
  }
}

// ---- template manager --------------------------------------------------
export class TemplateManager extends EventEmitter {
  constructor(rpc, cfg) {
    super();
    this.rpc = rpc;
    this.cfg = cfg;
    // pool-level fallback script — null if no PAYOUT_ADDRESS configured (per-miner mode)
    this.scriptPubKey = cfg.payoutAddress
      ? addressToScript(cfg.payoutAddress, cfg.network)
      : null;
    this.enTotal = cfg.extranonce1Size + cfg.extranonce2Size;
    this.current = null;          // current Job
    this.jobs = new Map();        // id -> Job (recent window)
    this.tipHash = null;          // prevhash (BE hex) jobs are built on
    this.refreshTimer = null;
    this.pollTimer = null;
    this.fetching = false;
    this.pendingTip = null;
    this.stats = { gbtMs: 0, lastGbtAt: 0, emptyJobs: 0, fullJobs: 0, zmqAlive: false };
  }

  async start() {
    await this.fullRefresh(true);
    this.refreshTimer = setInterval(() => {
      this.fullRefresh(false).catch((e) => this.emit('log', `refresh error: ${e.message}`));
    }, this.cfg.templateRefreshMs);
    this.pollTimer = setInterval(() => this.pollTip(), this.cfg.pollFallbackMs);
  }

  stop() {
    clearInterval(this.refreshTimer);
    clearInterval(this.pollTimer);
  }

  // consensus self-audit: build a real (unsolved) block from the current full
  // template and have bitcoind validate it via GBT proposal mode.
  auditScript() {
    if (this.scriptPubKey) return this.scriptPubKey;
    // per-miner mode: validate consensus with a fixed burn address
    return addressToScript('bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh', this.cfg.network);
  }

  async selfAudit() {
    const job = this.current;
    if (!job || job.kind === 'empty') return { ok: null, reason: 'no-full-job' };
    const script = this.auditScript();
    const hex = job.buildBlockHex(script, Buffer.alloc(this.enTotal, 0), job.curtime, 0, job.version);
    const r = await this.rpc.proposeBlock(hex);
    const ok = r === 'high-hash' || r === null || r === 'inconclusive';
    // ALSO certify the instant-empty-job path — the construction that guards
    // the ~90ms window after every new tip. Built EXACTLY like onNewTip does,
    // then validated by the node, so a block found in that window is provably
    // submittable. (Skipped across a retarget boundary, same as the real path.)
    let emptyOk = null, emptyReason = 'skipped-retarget-boundary';
    try {
      const hdr = await this.rpc.getBlockHeader(this.tipHash);
      const nextHeight = hdr.height + 1;
      if (nextHeight % 2016 !== 0) {
        const ej = new Job({
          prevhashBE: this.tipHash, height: nextHeight, version: 0x20000000,
          nbits: hdr.bits, curtime: Math.max(Math.floor(nowMs() / 1000), hdr.mediantime + 1),
          valueSats: subsidyAt(nextHeight), txs: [], witnessCommitment: null, clean: true,
          scriptPubKey: this.scriptPubKey, tag: this.cfg.coinbaseTag, enTotal: this.enTotal, kind: 'empty',
        });
        const er = await this.rpc.proposeBlock(ej.buildBlockHex(this.auditScript(), Buffer.alloc(this.enTotal, 0), ej.curtime, 0, ej.version));
        emptyOk = er === 'high-hash' || er === null || er === 'inconclusive';
        emptyReason = er ?? 'valid';
      }
    } catch (e) { emptyReason = e.message; }
    return { ok, reason: r ?? 'valid', height: job.height, txs: job.txs.length, emptyOk, emptyReason };
  }

  // refresh the retarget estimate from the node (cached per epoch start)
  async updateRetarget(tipHeight) {
    try {
      const epochStart = Math.floor(tipHeight / 2016) * 2016;
      if (this.epochStartCached !== epochStart) {
        const h = await this.rpc.getBlockHash(epochStart);
        const hdr = await this.rpc.getBlockHeader(h);
        this.epochFirstTs = hdr.time ?? hdr.mediantime;
        this.epochStartCached = epochStart;
      }
      this.stats.retarget = computeRetarget({
        tipHeight, firstTs: this.epochFirstTs, now: Math.floor(nowMs() / 1000),
      });
    } catch { this.stats.retarget = this.stats.retarget ?? null; }
  }

  rememberJob(job) {
    this.jobs.set(job.id, job);
    if (this.jobs.size > 64) {
      const oldest = this.jobs.keys().next().value;
      this.jobs.delete(oldest);
    }
  }

  // ZMQ fallback: cheap getbestblockhash poll
  async pollTip() {
    if (this.fetching) return;
    try {
      const best = await this.rpc.getBestBlockHash();
      if (best !== this.tipHash) await this.onNewTip(best, 'poll');
    } catch { /* node briefly unavailable; refresh loop will recover */ }
  }

  // critical path: a new block was announced
  async onNewTip(hashBE, source) {
    if (hashBE === this.tipHash || hashBE === this.pendingTip) return;
    this.pendingTip = hashBE;
    this.latestAnnounced = hashBE;     // newest tip we KNOW exists
    this.announceAt = nowMs();
    const t0 = nowMs();
    this.emit('log', `new tip ${hashBE.slice(0, 16)}… via ${source}`);

    // kick the full template fetch IMMEDIATELY (runs concurrently with the
    // instant job below — on a local node GBT may even win the race).
    // clean is auto-derived: if the instant job already flushed miners onto
    // this tip, the follow-up full job arrives with clean=false (no restart).
    const fullP = this.fullRefresh(false).catch((e) => this.emit('log', `refresh error: ${e.message}`));

    if (this.cfg.instantEmptyJob) {
      try {
        const hdr = await this.rpc.getBlockHeader(hashBE); // ~1ms vs GBT's 100ms+
        const nextHeight = hdr.height + 1;
        // skip if GBT already delivered the full job for this tip (never regress),
        // if an even NEWER tip was announced while the header was in flight,
        // and across a retarget boundary (can't predict nbits)
        if (this.tipHash !== hashBE && this.latestAnnounced === hashBE && nextHeight % 2016 !== 0) {
          const job = new Job({
            prevhashBE: hashBE,
            height: nextHeight,
            version: 0x20000000,
            nbits: hdr.bits,
            curtime: Math.max(Math.floor(nowMs() / 1000), hdr.mediantime + 1),
            valueSats: subsidyAt(nextHeight), // fees unknown yet — we target the block, not the fees
            txs: [],
            witnessCommitment: null,
            clean: true,
            scriptPubKey: this.scriptPubKey,
            tag: this.cfg.coinbaseTag,
            enTotal: this.enTotal,
            kind: 'empty',
          });
          this.current = job;
          this.tipHash = hashBE;
          this.rememberJob(job);
          this.stats.emptyJobs++;
          this.emit('job', job);
          this.emit('log', `⚡ instant empty job @${nextHeight} in ${nowMs() - t0}ms`);
        }
      } catch (e) {
        this.emit('log', `instant job failed (${e.message}); full template is already on the way`);
      }
    }
    await fullP;
    this.pendingTip = null;
  }

  async fullRefresh(forceClean) {
    if (this.fetching) {
      // a GBT is already in flight; if we're processing a new tip, make sure
      // another pass runs right after it (the in-flight one may be stale)
      if (this.pendingTip || forceClean) this.refetchWanted = true;
      return;
    }
    this.fetching = true;
    const t0 = nowMs();
    const startedAt = t0;
    try {
      const tpl = await this.rpc.getBlockTemplate();
      this.stats.gbtMs = nowMs() - t0;
      this.stats.lastGbtAt = nowMs();
      // BLOCK-RACE GUARD: if a NEWER tip was announced while this GBT was in
      // flight, this template is built on a dead tip — drop it and refetch.
      // (Announced BEFORE the fetch started is fine: the node answered after
      // seeing it, so the template already reflects the newest tip.)
      if (this.latestAnnounced && tpl.previousblockhash !== this.latestAnnounced
          && this.announceAt >= startedAt) {
        this.refetchWanted = true;
        return;
      }
      // GBT may also reveal a tip we were never told about (missed ZMQ + poll
      // race / reorg) — trust it, it is the node's authoritative current tip
      if (tpl.previousblockhash !== this.latestAnnounced) {
        this.latestAnnounced = tpl.previousblockhash;
        this.announceAt = nowMs();
      }
      const sameTip = tpl.previousblockhash === this.tipHash;
      const clean = forceClean || !sameTip;
      // ── Same-prevhash notify governor ────────────────────────────────────
      // Rule 1: empty → full ALWAYS bypasses (never leave miners on zero-tx block)
      // Rule 2: full → refresh is suppressed unless fee delta is material or
      //         the job is stale (older than templateRefreshMs/2)
      const isEmptyToFull = sameTip && this.current?.kind === 'empty';
      if (!isEmptyToFull && sameTip && !clean && this.current
          && this.current.kind !== 'empty'
          && nowMs() - this.current.createdAt < this.cfg.templateRefreshMs * 0.5) {
        // suppress same-prevhash refresh unless fee delta is material
        const feeDelta = Number(BigInt(tpl.coinbasevalue) - this.current.valueSats);
        if (feeDelta < (this.cfg.materialFeeDeltaSats ?? 50000)) return;
      }
      if (isEmptyToFull) {
        this.emit('log', `⚡ empty→full upgrade @${tpl.height} (${tpl.transactions.length} txs)`);
      }

      const txs = tpl.transactions.map((t) => ({
        dataBuf: hexToBuf(t.data),
        txidLE: hexBE2bufLE(t.txid || t.hash),
      }));
      const job = new Job({
        prevhashBE: tpl.previousblockhash,
        height: tpl.height,
        version: tpl.version,
        nbits: tpl.bits,
        curtime: tpl.curtime,
        valueSats: BigInt(tpl.coinbasevalue),
        txs,
        witnessCommitment: tpl.default_witness_commitment || null,
        // upgrading an instant empty job to the full template on the SAME tip:
        // clean=false so miners keep their in-flight work (the empty job stays
        // valid — even a block found on it is still a perfectly valid block)
        clean,
        scriptPubKey: this.scriptPubKey,
        tag: this.cfg.coinbaseTag,
        enTotal: this.enTotal,
        kind: sameTip && !forceClean ? (this.current?.kind === 'empty' ? 'full' : 'refresh') : 'full',
      });
      // forensics: how long after the tip announcement did the FULL job land?
      if (job.kind === 'full' && this.announceAt) {
        this.emit('log', `tip -> full job in +${nowMs() - this.announceAt}ms (gbt ${this.stats.gbtMs}ms, ${txs.length} txs)`);
      }
      this.current = job;
      this.tipHash = tpl.previousblockhash;
      this.rememberJob(job);
      this.stats.fullJobs++;
      this.emit('job', job);
      this.updateRetarget(tpl.height - 1); // fire-and-forget, cached per epoch
    } finally {
      this.fetching = false;
      if (this.refetchWanted) {
        this.refetchWanted = false;
        this.fullRefresh(false).catch((e) => this.emit('log', `refetch error: ${e.message}`));
      }
    }
  }
}
