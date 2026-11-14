// Synthesizes the app's cute sound effects into assets/sounds/*.wav.
// No third-party audio: everything is generated from math, so it is license-free and reproducible.
//   node scripts/generate-sounds.mjs
import { Buffer } from 'node:buffer';
import { writeFileSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const RATE = 22050;
const OUT = join(dirname(fileURLToPath(import.meta.url)), '..', 'assets', 'sounds');

let seed = 42;
const rand = () => ((seed = (seed * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff) * 2 - 1;

const silence = (sec) => new Float32Array(Math.round(sec * RATE));

function env(i, n, attack = 0.005, release = 0.08) {
  const t = i / RATE, dur = n / RATE;
  return Math.max(0, Math.min(attack ? t / attack : 1, release ? (dur - t) / release : 1, 1));
}

/** Tone whose frequency follows freqAt(t01); harmonic amplitudes in `harm`. */
function tone(dur, freqAt, { vol = 0.5, harm = [1, 0.3, 0.12], attack = 0.005, release, vibrato = 0 } = {}) {
  const n = Math.round(dur * RATE);
  const out = new Float32Array(n);
  let phase = 0;
  for (let i = 0; i < n; i++) {
    const t01 = i / n;
    const f = freqAt(t01) * (1 + vibrato * Math.sin((2 * Math.PI * 28 * i) / RATE));
    phase += (2 * Math.PI * f) / RATE;
    let s = 0;
    harm.forEach((h, k) => (s += h * Math.sin(phase * (k + 1))));
    out[i] = s * vol * env(i, n, attack, release ?? Math.min(0.12, dur / 2));
  }
  return out;
}

const expo = (a, b) => (t) => a * Math.pow(b / a, t);

/** Simple resonant band-pass (biquad) to give barks a "mouth" formant. */
function bandpass(x, f0, q) {
  const w = (2 * Math.PI * f0) / RATE, alpha = Math.sin(w) / (2 * q);
  const b0 = alpha, b2 = -alpha, a0 = 1 + alpha, a1 = -2 * Math.cos(w), a2 = 1 - alpha;
  const y = new Float32Array(x.length);
  let x1 = 0, x2 = 0, y1 = 0, y2 = 0;
  for (let i = 0; i < x.length; i++) {
    const v = (b0 * x[i] + b2 * x2 - a1 * y1 - a2 * y2) / a0;
    x2 = x1; x1 = x[i]; y2 = y1; y1 = v; y[i] = v;
  }
  return y;
}

function bark(dur, f0, f1) {
  const n = Math.round(dur * RATE);
  const raw = new Float32Array(n);
  let phase = 0;
  for (let i = 0; i < n; i++) {
    const t01 = i / n;
    // quick rise then fall, like "arf"
    const f = t01 < 0.15 ? f0 + (f1 * 1.25 - f0) * (t01 / 0.15) : f1 * 1.25 + (f1 * 0.7 - f1 * 1.25) * ((t01 - 0.15) / 0.85);
    phase += (2 * Math.PI * f) / RATE;
    let s = 0;
    for (let k = 1; k <= 10; k++) s += Math.sin(phase * k) / k; // sawtooth-ish
    s += rand() * 0.35;
    const e = Math.min(1, i / (0.006 * RATE)) * Math.exp(-3.2 * t01);
    raw[i] = s * e;
  }
  const a = bandpass(raw, 1100, 1.4), b = bandpass(raw, 2600, 2.5);
  const out = new Float32Array(n);
  for (let i = 0; i < n; i++) out[i] = (a[i] * 1.1 + b[i] * 0.5) * 0.9;
  return out;
}

function noiseBurst(dur, { vol = 0.4, f0 = 1800, q = 1.2 } = {}) {
  const n = Math.round(dur * RATE);
  const raw = new Float32Array(n);
  for (let i = 0; i < n; i++) raw[i] = rand() * env(i, n, 0.002, dur * 0.7);
  const y = bandpass(raw, f0, q);
  for (let i = 0; i < n; i++) y[i] *= vol * 3;
  return y;
}

function concat(...parts) {
  const len = parts.reduce((s, p) => s + p.length, 0);
  const out = new Float32Array(len);
  let o = 0;
  for (const p of parts) {
    out.set(p, o);
    o += p.length;
  }
  return out;
}

function mix(...tracks) {
  // tracks: [offsetSec, samples]
  const len = Math.max(...tracks.map(([off, s]) => Math.round(off * RATE) + s.length));
  const out = new Float32Array(len);
  for (const [off, s] of tracks) {
    const o = Math.round(off * RATE);
    for (let i = 0; i < s.length; i++) out[o + i] += s[i];
  }
  return out;
}

function normalize(x, peak = 0.85) {
  let m = 0;
  for (const v of x) m = Math.max(m, Math.abs(v));
  if (m > 0) for (let i = 0; i < x.length; i++) x[i] = (x[i] / m) * peak;
  return x;
}

function wav(samples) {
  const data = Buffer.alloc(samples.length * 2);
  samples.forEach((s, i) => data.writeInt16LE(Math.round(Math.max(-1, Math.min(1, s)) * 32000), i * 2));
  const h = Buffer.alloc(44);
  h.write('RIFF', 0); h.writeUInt32LE(36 + data.length, 4); h.write('WAVE', 8);
  h.write('fmt ', 12); h.writeUInt32LE(16, 16); h.writeUInt16LE(1, 20); h.writeUInt16LE(1, 22);
  h.writeUInt32LE(RATE, 24); h.writeUInt32LE(RATE * 2, 28); h.writeUInt16LE(2, 32); h.writeUInt16LE(16, 34);
  h.write('data', 36); h.writeUInt32LE(data.length, 40);
  return Buffer.concat([h, data]);
}

const note = (f, d, o = {}) => tone(d, () => f, o);

const sounds = {
  // "arf arf!" — two small barks
  bark: normalize(concat(bark(0.16, 380, 560), silence(0.07), bark(0.14, 420, 640))),
  // soft nose boop
  boop: normalize(tone(0.13, expo(980, 520), { harm: [1, 0.15], release: 0.08 }), 0.7),
  // happy two-note chime (connected / new reply)
  chime: normalize(mix([0, note(1046.5, 0.22, { harm: [1, 0.2, 0.08, 0.04] })], [0.09, note(1568, 0.32, { harm: [1, 0.2, 0.08] })]), 0.7),
  // crunchy munching
  chomp: normalize(concat(noiseBurst(0.07, { f0: 1400 }), silence(0.05), noiseBurst(0.06, { f0: 1100 }), silence(0.06), noiseBurst(0.08, { f0: 1300 })), 0.75),
  // button pop
  pop: normalize(tone(0.06, expo(500, 1400), { harm: [1, 0.3], release: 0.03 }), 0.6),
  // squeaky toy
  squeak: normalize(tone(0.28, (t) => 1300 + 650 * Math.sin(Math.PI * t), { harm: [1, 0.5, 0.2], vibrato: 0.03 }), 0.6),
  // sleepy lullaby (nap)
  lullaby: normalize(concat(note(784, 0.22), note(659.25, 0.22), note(523.25, 0.42, { release: 0.3 })), 0.55),
  // level up arpeggio
  levelup: normalize(mix(...[523.25, 659.25, 783.99, 1046.5, 1318.5].map((f, i) => [i * 0.07, note(f, 0.18, { harm: [1, 0.25] })])), 0.7),
  // whoosh when a command is sent
  send: normalize(mix([0, noiseBurst(0.2, { f0: 2400, q: 0.8, vol: 0.25 })], [0, tone(0.18, expo(600, 1500), { vol: 0.25, harm: [1] })]), 0.55),
  // gentle "uh-oh"
  error: normalize(concat(note(523.25, 0.14), note(392, 0.24)), 0.6),
  // recording start / stop blips
  recStart: normalize(note(880, 0.08, { harm: [1, 0.2] }), 0.5),
  recStop: normalize(note(660, 0.08, { harm: [1, 0.2] }), 0.5),
};

mkdirSync(OUT, { recursive: true });
for (const [name, samples] of Object.entries(sounds)) {
  writeFileSync(join(OUT, `${name}.wav`), wav(samples));
  console.log(`${name}.wav  ${(samples.length / RATE).toFixed(2)}s`);
}
