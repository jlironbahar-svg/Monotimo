import type { Mood } from '../../../shared/protocol';
import type { Sfx } from './sounds';

export interface PetState {
  happiness: number;
  energy: number;
  fullness: number;
  xp: number;
  updatedAt: number;
}

export type PetAction = 'feed' | 'pet' | 'play' | 'nap';

export const DEFAULT_PET: PetState = { happiness: 80, energy: 85, fullness: 70, xp: 0, updatedAt: Date.now() };

/** Points lost per hour while you're away. */
const DECAY_PER_HOUR = { happiness: 6, energy: 4, fullness: 8 };

const clamp = (v: number) => Math.max(0, Math.min(100, Math.round(v * 10) / 10));

export function level(xp: number): number {
  return Math.floor(xp / 100) + 1;
}

export function levelProgress(xp: number): number {
  return (xp % 100) / 100;
}

export function decay(p: PetState, now = Date.now()): PetState {
  const hours = Math.max(0, (now - p.updatedAt) / 3_600_000);
  if (hours < 1 / 120) return p; // < 30 s
  return {
    ...p,
    happiness: clamp(p.happiness - DECAY_PER_HOUR.happiness * hours - (p.fullness < 20 ? 4 * hours : 0)),
    energy: clamp(p.energy - DECAY_PER_HOUR.energy * hours),
    fullness: clamp(p.fullness - DECAY_PER_HOUR.fullness * hours),
    updatedAt: now,
  };
}

export interface ActionOutcome {
  pet: PetState;
  ok: boolean;
  message: string;
  sfx: Sfx;
  emoji: string;
  mood: Mood;
  leveledUp: boolean;
}

export function applyAction(p: PetState, action: PetAction, name: string): ActionOutcome {
  const now = Date.now();
  const base = decay(p, now);
  const before = level(base.xp);
  const result = (changes: Partial<PetState>, rest: Omit<ActionOutcome, 'pet' | 'leveledUp'>): ActionOutcome => {
    const pet: PetState = {
      ...base,
      happiness: clamp(changes.happiness ?? base.happiness),
      energy: clamp(changes.energy ?? base.energy),
      fullness: clamp(changes.fullness ?? base.fullness),
      xp: changes.xp ?? base.xp,
      updatedAt: now,
    };
    return { ...rest, pet, leveledUp: level(pet.xp) > before };
  };

  switch (action) {
    case 'feed':
      if (base.fullness >= 95)
        return result({}, { ok: false, message: `${name} is too full! Maybe later 🥱`, sfx: 'boop', emoji: '😮‍💨', mood: 'happy' });
      return result(
        { fullness: base.fullness + 25, happiness: base.happiness + 5, xp: base.xp + 5 },
        { ok: true, message: 'Nom nom nom! Yummy bone!', sfx: 'chomp', emoji: '🦴', mood: 'excited' },
      );
    case 'pet':
      return result(
        { happiness: base.happiness + 8, xp: base.xp + 3 },
        { ok: true, message: pick(['Hehe, that tickles!', 'More pets please!', 'I love you!', 'Best human ever!']), sfx: 'boop', emoji: '💖', mood: 'excited' },
      );
    case 'play':
      if (base.energy < 12)
        return result({}, { ok: false, message: 'Too sleepy to play… nap first? 💤', sfx: 'boop', emoji: '😴', mood: 'sleepy' });
      return result(
        { happiness: base.happiness + 15, energy: base.energy - 12, fullness: base.fullness - 5, xp: base.xp + 8 },
        { ok: true, message: pick(['Again! Again!', 'I got the ball!', 'Wheee!']), sfx: 'squeak', emoji: '🎾', mood: 'excited' },
      );
    case 'nap':
      if (base.energy >= 95)
        return result({}, { ok: false, message: "I'm not sleepy! Let's play!", sfx: 'bark', emoji: '⚡', mood: 'excited' });
      return result(
        { energy: base.energy + 40, xp: base.xp + 4 },
        { ok: true, message: 'Zzz… sweet dreams of bones…', sfx: 'lullaby', emoji: '💤', mood: 'sleepy' },
      );
  }
}

export function petMood(p: PetState): Mood {
  if (p.energy < 20) return 'sleepy';
  if (p.fullness < 25 || p.happiness < 30) return 'sad';
  if (p.happiness > 85) return 'excited';
  return 'happy';
}

export function idleLine(p: PetState, name: string): string {
  if (p.fullness < 25) return "My tummy's rumbling… can I have a treat?";
  if (p.energy < 20) return "I'm sooo sleepy…";
  if (p.happiness < 30) return 'I missed you! Pet me?';
  return pick([
    `Hi! I'm ${name}! Tap me!`,
    'Wanna play fetch?',
    "I'm keeping an eye on your PC for you!",
    'Boop my nose!',
    'You look great today!',
  ]);
}

function pick<T>(items: T[]): T {
  return items[Math.floor(Math.random() * items.length)];
}
