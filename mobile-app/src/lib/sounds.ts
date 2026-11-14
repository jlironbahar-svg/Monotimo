import { createAudioPlayer, setAudioModeAsync, type AudioPlayer } from 'expo-audio';

/** Synthesized effects (see scripts/generate-sounds.mjs). */
const SOURCES = {
  bark: require('../../assets/sounds/bark.wav'),
  boop: require('../../assets/sounds/boop.wav'),
  chime: require('../../assets/sounds/chime.wav'),
  chomp: require('../../assets/sounds/chomp.wav'),
  pop: require('../../assets/sounds/pop.wav'),
  squeak: require('../../assets/sounds/squeak.wav'),
  lullaby: require('../../assets/sounds/lullaby.wav'),
  levelup: require('../../assets/sounds/levelup.wav'),
  send: require('../../assets/sounds/send.wav'),
  error: require('../../assets/sounds/error.wav'),
  recStart: require('../../assets/sounds/recStart.wav'),
  recStop: require('../../assets/sounds/recStop.wav'),
} as const;

export type Sfx = keyof typeof SOURCES;

const VOLUME: Partial<Record<Sfx, number>> = { pop: 0.5, send: 0.6, recStart: 0.6, recStop: 0.6 };

let enabled = true;
const players: Partial<Record<Sfx, AudioPlayer>> = {};

export function setSoundEffectsEnabled(value: boolean): void {
  enabled = value;
}

export async function initAudio(): Promise<void> {
  try {
    await setAudioModeAsync({
      playsInSilentMode: true,
      allowsRecording: false,
      interruptionMode: 'mixWithOthers',
      shouldPlayInBackground: false,
    });
  } catch {
    /* web / unsupported */
  }
}

function player(name: Sfx): AudioPlayer | null {
  try {
    let p = players[name];
    if (!p) {
      p = createAudioPlayer(SOURCES[name]);
      p.volume = VOLUME[name] ?? 0.9;
      players[name] = p;
    }
    return p;
  } catch {
    return null;
  }
}

/** Fire-and-forget sound effect. Never throws. */
export function playSfx(name: Sfx): void {
  if (!enabled) return;
  const p = player(name);
  if (!p) return;
  try {
    void p.seekTo(0).catch(() => undefined);
    p.play();
  } catch {
    /* ignore */
  }
}

/** Warm up the players so the first tap has no delay. */
export function preloadSfx(): void {
  (Object.keys(SOURCES) as Sfx[]).forEach((k) => player(k));
}
