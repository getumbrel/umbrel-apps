// SINGULARITY util.js — byte plumbing, hashing, encodings. Zero deps.
import { createHash } from 'node:crypto';

export const sha256 = (b) => createHash('sha256').update(b).digest();
export const sha256d = (b) => sha256(sha256(b));

export const hexToBuf = (h) => Buffer.from(h, 'hex');
export const bufToHex = (b) => b.toString('hex');
export const revBuf = (b) => Buffer.from(b).reverse();
// display(big-endian) hex <-> internal(little-endian) bytes
export const hexBE2bufLE = (h) => revBuf(hexToBuf(h));
export const bufLE2hexBE = (b) => bufToHex(revBuf(b));

// Reverse byte order within each 4-byte word (stratum prevhash convention)
export function swap32(buf) {
  const out = Buffer.alloc(buf.length);
  for (let i = 0; i < buf.length; i += 4) {
    out[i] = buf[i + 3]; out[i + 1] = buf[i + 2];
    out[i + 2] = buf[i + 1]; out[i + 3] = buf[i];
  }
  return out;
}

export function varint(n) {
  if (n < 0xfd) return Buffer.from([n]);
  if (n <= 0xffff) { const b = Buffer.alloc(3); b[0] = 0xfd; b.writeUInt16LE(n, 1); return b; }
  if (n <= 0xffffffff) { const b = Buffer.alloc(5); b[0] = 0xfe; b.writeUInt32LE(n, 1); return b; }
  const b = Buffer.alloc(9); b[0] = 0xff; b.writeBigUInt64LE(BigInt(n), 1); return b;
}

export const u32LE = (n) => { const b = Buffer.alloc(4); b.writeUInt32LE(n >>> 0, 0); return b; };
export const u64LE = (n) => { const b = Buffer.alloc(8); b.writeBigUInt64LE(BigInt(n), 0); return b; };

// BIP34 height push (minimal CScriptNum push)
export function bip34Push(height) {
  const bytes = [];
  let n = height;
  while (n > 0) { bytes.push(n & 0xff); n >>= 8; }
  if (bytes.length && (bytes[bytes.length - 1] & 0x80)) bytes.push(0x00);
  return Buffer.concat([Buffer.from([bytes.length]), Buffer.from(bytes)]);
}

// ---------- difficulty / target math (BigInt, exact) ----------
export const TRUEDIFFONE = BigInt('0x00000000ffff0000000000000000000000000000000000000000000000000000');

export function nbitsToTarget(nbitsHex) {
  const nbits = parseInt(nbitsHex, 16) >>> 0;
  const exp = nbits >>> 24;
  const mant = BigInt(nbits & 0x007fffff);
  return exp <= 3 ? mant >> (8n * BigInt(3 - exp)) : mant << (8n * BigInt(exp - 3));
}

export const targetToDiff = (target) => target > 0n ? Number(TRUEDIFFONE * 1000000n / target) / 1000000 : 0;

// hash buffer (internal LE, as produced by sha256d of header) -> BE BigInt
export const hashToBig = (hashLE) => BigInt('0x' + bufLE2hexBE(hashLE));

// share difficulty achieved by a header hash
export function hashToShareDiff(hashLE) {
  const v = hashToBig(hashLE);
  if (v === 0n) return Number.POSITIVE_INFINITY;
  // keep 6 decimals of precision
  return Number(TRUEDIFFONE * 1000000n / v) / 1000000;
}

// difficulty -> 256-bit share target (for documentation/tests)
export const diffToTarget = (diff) => TRUEDIFFONE / BigInt(Math.max(1, Math.round(diff)));

// ---------- address -> scriptPubKey (bech32/bech32m + base58check) ----------
const B32 = 'qpzry9x8gf2tvdw0s3jn54khce6mua7l';
function bech32Polymod(values) {
  const GEN = [0x3b6a57b2, 0x26508e6d, 0x1ea119fa, 0x3d4233dd, 0x2a1462b3];
  let chk = 1;
  for (const v of values) {
    const top = chk >>> 25;
    chk = ((chk & 0x1ffffff) << 5) ^ v;
    for (let i = 0; i < 5; i++) if ((top >>> i) & 1) chk ^= GEN[i];
  }
  return chk >>> 0;
}
function bech32HrpExpand(hrp) {
  const out = [];
  for (const c of hrp) out.push(c.charCodeAt(0) >>> 5);
  out.push(0);
  for (const c of hrp) out.push(c.charCodeAt(0) & 31);
  return out;
}
function bech32Decode(addr) {
  const lower = addr.toLowerCase();
  if (lower !== addr && addr.toUpperCase() !== addr) return null;
  const pos = lower.lastIndexOf('1');
  if (pos < 1 || pos + 7 > lower.length) return null;
  const hrp = lower.slice(0, pos);
  const data = [];
  for (const c of lower.slice(pos + 1)) {
    const d = B32.indexOf(c);
    if (d === -1) return null;
    data.push(d);
  }
  const pm = bech32Polymod(bech32HrpExpand(hrp).concat(data));
  let enc = null;
  if (pm === 1) enc = 'bech32';
  else if (pm === 0x2bc830a3) enc = 'bech32m';
  else return null;
  return { hrp, data: data.slice(0, -6), enc };
}
function fromBits5(data) {
  let acc = 0, bits = 0; const out = [];
  for (const v of data) {
    acc = (acc << 5) | v; bits += 5;
    while (bits >= 8) { bits -= 8; out.push((acc >>> bits) & 0xff); }
  }
  if (bits >= 5 || ((acc << (8 - bits)) & 0xff)) return null;
  return Buffer.from(out);
}
const B58 = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz';
function base58Decode(s) {
  let n = 0n;
  for (const c of s) {
    const d = B58.indexOf(c);
    if (d === -1) return null;
    n = n * 58n + BigInt(d);
  }
  let hex = n.toString(16);
  if (hex.length % 2) hex = '0' + hex;
  let buf = hexToBuf(hex);
  let zeros = 0;
  for (const c of s) { if (c === '1') zeros++; else break; }
  return Buffer.concat([Buffer.alloc(zeros, 0), buf]);
}

export function addressToScript(addr, network = 'mainnet') {
  const hrpWant = network === 'mainnet' ? 'bc' : (network === 'regtest' ? 'bcrt' : 'tb');
  const b = bech32Decode(addr);
  if (b) {
    if (b.hrp !== hrpWant) throw new Error(`address hrp ${b.hrp} != ${hrpWant}`);
    const ver = b.data[0];
    const prog = fromBits5(b.data.slice(1));
    if (!prog || prog.length < 2 || prog.length > 40) throw new Error('bad witness program');
    if (ver === 0 && b.enc !== 'bech32') throw new Error('v0 must be bech32');
    if (ver > 0 && b.enc !== 'bech32m') throw new Error('v1+ must be bech32m');
    if (ver === 0 && prog.length !== 20 && prog.length !== 32) throw new Error('bad v0 length');
    const op = ver === 0 ? 0x00 : 0x50 + ver;
    return Buffer.concat([Buffer.from([op, prog.length]), prog]);
  }
  const raw = base58Decode(addr);
  if (raw && raw.length === 25) {
    const payload = raw.subarray(0, 21);
    const check = raw.subarray(21);
    if (!sha256d(payload).subarray(0, 4).equals(check)) throw new Error('bad base58 checksum');
    const v = payload[0], h = payload.subarray(1);
    const isMain = network === 'mainnet';
    if (v === (isMain ? 0x00 : 0x6f)) // P2PKH
      return Buffer.concat([Buffer.from([0x76, 0xa9, 0x14]), h, Buffer.from([0x88, 0xac])]);
    if (v === (isMain ? 0x05 : 0xc4)) // P2SH
      return Buffer.concat([Buffer.from([0xa9, 0x14]), h, Buffer.from([0x87])]);
    throw new Error('unknown base58 version');
  }
  throw new Error('unrecognized address');
}

// block subsidy in sats at given height (mainnet schedule)
export function subsidyAt(height) {
  const halvings = Math.floor(height / 210000);
  if (halvings >= 64) return 0n;
  return 5000000000n >> BigInt(halvings);
}

export const nowMs = () => Date.now();

// Same K/M/G/T/P/E scaling as dashboard fmtN() — used by widget + logs.
const SCALE_UNITS = ['', 'K', 'M', 'G', 'T', 'P', 'E'];
export function fmtScaled(v) {
  if (!v || v <= 0) return '0';
  let u = 0;
  let n = v;
  while (n >= 1000 && u < SCALE_UNITS.length - 1) { n /= 1000; u++; }
  return n.toFixed(n >= 100 ? 0 : 2) + SCALE_UNITS[u];
}

export const fmtDiff = fmtScaled;
