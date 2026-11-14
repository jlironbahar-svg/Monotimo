import { createAudioPlayer, type AudioPlayer } from 'expo-audio';
import * as Speech from 'expo-speech';

type Talking = (talking: boolean) => void;

let current: AudioPlayer | null = null;
let currentSub: { remove: () => void } | null = null;
let fallbackTimer: ReturnType<typeof setTimeout> | null = null;
let onTalkingRef: Talking | null = null;

function cleanup(): void {
  if (fallbackTimer) clearTimeout(fallbackTimer);
  fallbackTimer = null;
  currentSub?.remove();
  currentSub = null;
  if (current) {
    try {
      current.pause();
      current.remove();
    } catch {
      /* ignore */
    }
  }
  current = null;
}

export function stopVoice(): void {
  cleanup();
  void Speech.stop();
  onTalkingRef?.(false);
  onTalkingRef = null;
}

function speakOnDevice(text: string, onTalking: Talking): void {
  onTalking(true);
  Speech.speak(text, {
    pitch: 1.35, // a little higher, puppy-ish
    rate: 1.02,
    onDone: () => onTalking(false),
    onStopped: () => onTalking(false),
    onError: () => onTalking(false),
  });
}

function pretendTalk(text: string, onTalking: Talking): void {
  onTalking(true);
  fallbackTimer = setTimeout(() => onTalking(false), Math.min(6000, Math.max(900, text.length * 55)));
}

/**
 * Play the companion's reply: ElevenLabs audio from the PC when available, else the phone's own
 * text-to-speech (if enabled), else just a talking animation. `onTalking` drives the mouth animation.
 */
export function playReply(opts: { url: string | null; text: string; speakOnPhone: boolean; onTalking: Talking }): void {
  stopVoice();
  const { url, text, speakOnPhone, onTalking } = opts;
  onTalkingRef = onTalking;
  const fallback = () => (speakOnPhone ? speakOnDevice(text, onTalking) : pretendTalk(text, onTalking));

  if (!url) {
    fallback();
    return;
  }
  try {
    const p = createAudioPlayer({ uri: url });
    current = p;
    let started = false;
    onTalking(true);
    currentSub = p.addListener('playbackStatusUpdate', (s) => {
      if (s.playing) started = true;
      if (s.didJustFinish) {
        cleanup();
        onTalking(false);
      }
    });
    p.play();
    // If the clip never starts (network hiccup), fall back to the phone voice.
    fallbackTimer = setTimeout(() => {
      if (!started) {
        cleanup();
        fallback();
      }
    }, 7000);
  } catch {
    cleanup();
    fallback();
  }
}
