import * as Haptics from 'expo-haptics';
import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { AppState, Linking, Platform } from 'react-native';

import {
  parsePairingPayload,
  type ActionLogEntry,
  type ClientMessage,
  type ConfigUpdateMsg,
  type Mood,
  type PairingInfo,
  type PcConfigSummary,
  type PcState,
  type QuickAction,
  type ServerMessage,
} from '../../../shared/protocol';
import { DesktopConnection, pairingFromInfo, type ConnStatus, type StoredPairing } from '../lib/connection';
import { applyAction, decay, DEFAULT_PET, type PetAction, type PetState } from '../lib/pet';
import { initAudio, playSfx, preloadSfx, setSoundEffectsEnabled, type Sfx } from '../lib/sounds';
import { load, loadRaw, randomId, save } from '../lib/storage';
import { playReply, stopVoice } from '../lib/voice';

export interface Settings {
  petName: string;
  soundEffects: boolean;
  haptics: boolean;
  /** Use the phone's own TTS when the PC has no ElevenLabs key. */
  speakOnPhone: boolean;
  /** Ask the PC for ElevenLabs voice replies. */
  voiceReplies: boolean;
  avatarUri: string | null;
}

export interface ChatEntry {
  id: string;
  from: 'me' | 'friend' | 'system';
  text: string;
  actions?: ActionLogEntry[];
  pending?: boolean;
  ts: number;
}

export interface Shortcut {
  id: string;
  label: string;
  emoji: string;
  kind: 'app' | 'url';
  target: string;
}

export interface Screenshot {
  image: string;
  width: number;
  height: number;
  at: number;
}

const DEFAULT_SETTINGS: Settings = {
  petName: 'Biscuit',
  soundEffects: true,
  haptics: true,
  speakOnPhone: true,
  voiceReplies: true,
  avatarUri: null,
};

interface AppContextValue {
  ready: boolean;
  pairing: StoredPairing | null;
  status: ConnStatus;
  statusDetail: string;
  pcConfig: PcConfigSummary | null;
  pcState: { state: PcState; detail: string };
  messages: ChatEntry[];
  /** Short-lived reaction (after a reply / pet action); screens fall back to their own default mood. */
  reactionMood: Mood | null;
  talking: boolean;
  settings: Settings;
  pet: PetState;
  shortcuts: Shortcut[];
  screenshot: Screenshot | null;
  /** Apps installed on the PC (null until requested). */
  pcApps: string[] | null;
  toast: { text: string; tone: 'info' | 'error' | 'success'; key: number } | null;
  /** Bumps every time the friend wants to celebrate (hearts, etc.). */
  burst: { emoji: string; key: number } | null;

  pairWith: (info: PairingInfo) => void;
  pairWithText: (raw: string) => boolean;
  forgetPc: () => void;
  reconnect: () => void;
  setManualHost: (host: string, port: number) => void;

  sendChat: (text: string) => void;
  sendVoice: (base64: string, mime: string) => void;
  runAction: (action: QuickAction, args?: Record<string, unknown>, label?: string) => void;
  requestScreenshot: () => void;
  clearScreenshot: () => void;
  requestApps: () => void;
  updatePcConfig: (changes: Omit<ConfigUpdateMsg, 'type' | 'id'>) => boolean;

  updateSettings: (changes: Partial<Settings>) => void;
  petAction: (action: PetAction) => { message: string; ok: boolean };
  addShortcut: (s: Omit<Shortcut, 'id'>) => void;
  removeShortcut: (id: string) => void;

  sfx: (name: Sfx) => void;
  tap: () => void;
  showToast: (text: string, tone?: 'info' | 'error' | 'success') => void;
  setMoodFor: (mood: Mood, ms?: number) => void;
}

const Ctx = createContext<AppContextValue | null>(null);

export function useApp(): AppContextValue {
  const v = useContext(Ctx);
  if (!v) throw new Error('useApp must be used inside <AppProvider>');
  return v;
}

function deviceName(): string {
  const c = (Platform.constants ?? {}) as { Model?: string; Brand?: string };
  if (c.Model) return c.Brand && !c.Model.toLowerCase().startsWith(c.Brand.toLowerCase()) ? `${c.Brand} ${c.Model}` : c.Model;
  return Platform.OS === 'ios' ? 'iPhone' : Platform.OS === 'web' ? 'Browser' : 'Android phone';
}

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false);
  const [pairing, setPairing] = useState<StoredPairing | null>(null);
  const [status, setStatus] = useState<ConnStatus>('idle');
  const [statusDetail, setStatusDetail] = useState('');
  const [pcConfig, setPcConfig] = useState<PcConfigSummary | null>(null);
  const [pcState, setPcState] = useState<{ state: PcState; detail: string }>({ state: 'idle', detail: '' });
  const [messages, setMessages] = useState<ChatEntry[]>([]);
  const [talking, setTalking] = useState(false);
  const [tempMood, setTempMood] = useState<Mood | null>(null);
  const [settings, setSettings] = useState<Settings>(DEFAULT_SETTINGS);
  const [pet, setPet] = useState<PetState>(DEFAULT_PET);
  const [shortcuts, setShortcuts] = useState<Shortcut[]>([]);
  const [screenshot, setScreenshot] = useState<Screenshot | null>(null);
  const [pcApps, setPcApps] = useState<string[] | null>(null);
  const [toast, setToast] = useState<AppContextValue['toast']>(null);
  const [burst, setBurst] = useState<AppContextValue['burst']>(null);

  const connRef = useRef<DesktopConnection | null>(null);
  const settingsRef = useRef(settings);
  useEffect(() => {
    settingsRef.current = settings;
  }, [settings]);
  const moodTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ---------------------------------------------------------------- helpers
  const sfx = useCallback((name: Sfx) => playSfx(name), []);
  const tap = useCallback(() => {
    if (settingsRef.current.haptics) void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light).catch(() => undefined);
  }, []);
  const showToast = useCallback((text: string, tone: 'info' | 'error' | 'success' = 'info') => {
    setToast({ text, tone, key: Date.now() });
  }, []);
  const setMoodFor = useCallback((mood: Mood, ms = 4000) => {
    setTempMood(mood);
    if (moodTimer.current) clearTimeout(moodTimer.current);
    moodTimer.current = setTimeout(() => setTempMood(null), ms);
  }, []);
  const pushMessage = useCallback((entry: Omit<ChatEntry, 'ts'>) => {
    setMessages((prev) => [...prev.filter((m) => m.id !== entry.id), { ...entry, ts: Date.now() }].slice(-60));
  }, []);

  // ---------------------------------------------------------------- server messages
  const handleMessage = useCallback(
    (msg: ServerMessage) => {
      const conn = connRef.current;
      switch (msg.type) {
        case 'status':
          setPcState({ state: msg.state, detail: msg.detail ?? '' });
          break;
        case 'transcript':
          pushMessage({ id: msg.id, from: 'me', text: msg.text || '(silence)' });
          break;
        case 'reply': {
          setMessages((prev) => prev.map((m) => (m.id === msg.id && m.from === 'me' ? { ...m, pending: false } : m)));
          pushMessage({ id: `${msg.id}:r`, from: 'friend', text: msg.text, actions: msg.actions });
          setMoodFor(msg.mood, 6000);
          if (msg.actions.some((a) => a.ok)) setBurst({ emoji: msg.mood === 'curious' ? '🔍' : '⭐', key: Date.now() });
          playSfx(msg.mood === 'sad' ? 'error' : 'chime');
          const base = conn?.baseUrl();
          playReply({
            url: msg.audioUrl && base ? base + msg.audioUrl : null,
            text: msg.text,
            speakOnPhone: settingsRef.current.speakOnPhone,
            onTalking: setTalking,
          });
          break;
        }
        case 'action_result':
          pushMessage({ id: `${msg.id}:r`, from: 'friend', text: msg.detail, actions: [{ tool: msg.action, ok: msg.ok, detail: msg.detail }] });
          setMoodFor(msg.ok ? 'proud' : 'sad', 3500);
          playSfx(msg.ok ? 'chime' : 'error');
          if (msg.ok && (msg.action === 'point' || msg.action === 'click')) setBurst({ emoji: '👉', key: Date.now() });
          break;
        case 'screenshot':
          setScreenshot({ image: msg.image, width: msg.width, height: msg.height, at: Date.now() });
          playSfx('pop');
          break;
        case 'config':
          setPcConfig(msg.config);
          break;
        case 'apps':
          setPcApps(msg.apps);
          break;
        case 'error':
          // An older PC agent doesn't know the "apps" request: just show no list instead of an error.
          if (msg.code === 'bad_request' && msg.message.includes("'apps'")) {
            setPcApps([]);
          } else if (msg.code !== 'auth_failed' && msg.code !== 'protocol_mismatch') {
            showToast(msg.message, 'error');
            playSfx('error');
            if (msg.id) setMessages((prev) => prev.map((m) => (m.id === msg.id ? { ...m, pending: false } : m)));
          }
          break;
        default:
          break;
      }
    },
    [pushMessage, setMoodFor, showToast],
  );

  // ---------------------------------------------------------------- boot
  useEffect(() => {
    let alive = true;
    (async () => {
      const [savedSettings, savedPairing, savedPet, savedShortcuts, savedDeviceId] = await Promise.all([
        load<Settings>('settings', DEFAULT_SETTINGS),
        loadRaw<StoredPairing | null>('pairing', null),
        load<PetState>('pet', DEFAULT_PET),
        loadRaw<Shortcut[]>('shortcuts', []),
        loadRaw<string | null>('deviceId', null),
      ]);
      const deviceId = savedDeviceId ?? randomId(20);
      if (!savedDeviceId) void save('deviceId', deviceId);
      if (!alive) return;

      setSoundEffectsEnabled(savedSettings.soundEffects);
      await initAudio();
      preloadSfx();

      const conn = new DesktopConnection(deviceId, deviceName());
      connRef.current = conn;
      conn.onStatus((s, detail) => {
        setStatus(s);
        setStatusDetail(detail);
        if (s !== 'connected') setPcState({ state: 'idle', detail: '' });
      });
      conn.onMessage(handleMessage);
      conn.onWelcome((welcome, updated) => {
        setPcConfig(welcome.config);
        setPairing(updated);
        void save('pairing', updated);
        playSfx('chime');
      });

      setSettings(savedSettings);
      setPet(decay(savedPet));
      setShortcuts(savedShortcuts);
      setPairing(savedPairing);
      if (savedPairing) conn.start(savedPairing);
      setReady(true);
    })();
    return () => {
      alive = false;
      connRef.current?.stop();
      stopVoice();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // reconnect when the app comes back to the foreground
  useEffect(() => {
    const sub = AppState.addEventListener('change', (state) => {
      if (state === 'active') {
        connRef.current?.retryNow();
        setPet((p) => decay(p));
      }
    });
    return () => sub.remove();
  }, []);

  // pet stats tick once a minute
  useEffect(() => {
    const t = setInterval(() => setPet((p) => decay(p)), 60_000);
    return () => clearInterval(t);
  }, []);
  useEffect(() => {
    if (ready) void save('pet', pet);
  }, [pet, ready]);

  // ---------------------------------------------------------------- pairing
  const pairWith = useCallback((info: PairingInfo) => {
    const p = pairingFromInfo(info);
    setPairing(p);
    setPcConfig(null);
    void save('pairing', p);
    connRef.current?.start(p);
  }, []);

  // deep links: scanning the QR with the system camera opens desktopfriend://pair?...
  useEffect(() => {
    if (!ready) return;
    const handleUrl = (url: string | null | undefined) => {
      if (!url) return;
      const info = parsePairingPayload(url);
      if (info) pairWith(info);
    };
    void Linking.getInitialURL().then(handleUrl).catch(() => undefined);
    const sub = Linking.addEventListener('url', (e) => handleUrl(e.url));
    return () => sub.remove();
  }, [ready, pairWith]);

  const pairWithText = useCallback(
    (raw: string) => {
      const info = parsePairingPayload(raw);
      if (!info) return false;
      pairWith(info);
      return true;
    },
    [pairWith],
  );

  const forgetPc = useCallback(() => {
    connRef.current?.stop();
    setPairing(null);
    setPcConfig(null);
    setMessages([]);
    void save('pairing', null);
  }, []);

  const reconnect = useCallback(() => {
    const conn = connRef.current;
    if (!conn) return;
    if (conn.getStatus() === 'rejected' || conn.getStatus() === 'idle') {
      if (pairing) conn.start(pairing);
    } else conn.retryNow();
  }, [pairing]);

  const setManualHost = useCallback(
    (host: string, port: number) => {
      if (!pairing) return;
      const p: StoredPairing = { ...pairing, hosts: [host, ...pairing.hosts.filter((h) => h !== host)], lastHost: host, port };
      setPairing(p);
      void save('pairing', p);
      connRef.current?.start(p);
    },
    [pairing],
  );

  // ---------------------------------------------------------------- sending
  const send = useCallback(
    (msg: ClientMessage): boolean => {
      const ok = connRef.current?.send(msg) ?? false;
      if (!ok) {
        showToast('Not connected to your PC yet. Is Desktop Friend running?', 'error');
        playSfx('error');
      }
      return ok;
    },
    [showToast],
  );

  const sendChat = useCallback(
    (text: string) => {
      const trimmed = text.trim();
      if (!trimmed) return;
      const id = randomId(10);
      if (send({ type: 'chat', id, text: trimmed, speak: settingsRef.current.voiceReplies })) {
        pushMessage({ id, from: 'me', text: trimmed, pending: true });
        playSfx('send');
      }
    },
    [send, pushMessage],
  );

  const sendVoice = useCallback(
    (base64: string, mime: string) => {
      const id = randomId(10);
      if (send({ type: 'voice', id, audio: base64, mime, speak: settingsRef.current.voiceReplies })) {
        pushMessage({ id, from: 'me', text: '🎤 …', pending: true });
        playSfx('send');
      }
    },
    [send, pushMessage],
  );

  const runAction = useCallback(
    (action: QuickAction, args?: Record<string, unknown>, label?: string) => {
      const id = randomId(10);
      if (send({ type: 'action', id, action, args })) {
        pushMessage({ id, from: 'me', text: label ?? action.replace(/_/g, ' '), pending: true });
        playSfx('send');
      }
    },
    [send, pushMessage],
  );

  const requestScreenshot = useCallback(() => {
    send({ type: 'screenshot', id: randomId(8), maxWidth: 1000 });
  }, [send]);
  const clearScreenshot = useCallback(() => setScreenshot(null), []);
  const requestApps = useCallback(() => {
    connRef.current?.send({ type: 'apps', id: randomId(8) });
  }, []);

  const updatePcConfig = useCallback(
    (changes: Omit<ConfigUpdateMsg, 'type' | 'id'>) => send({ type: 'config', id: randomId(8), ...changes }),
    [send],
  );

  // ---------------------------------------------------------------- local state
  const updateSettings = useCallback((changes: Partial<Settings>) => {
    setSettings((prev) => {
      const next = { ...prev, ...changes };
      void save('settings', next);
      if (changes.soundEffects !== undefined) setSoundEffectsEnabled(changes.soundEffects);
      return next;
    });
  }, []);

  const petAction = useCallback(
    (action: PetAction) => {
      const outcome = applyAction(pet, action, settingsRef.current.petName);
      setPet(outcome.pet);
      playSfx(outcome.leveledUp ? 'levelup' : outcome.sfx);
      setMoodFor(outcome.mood, action === 'nap' && outcome.ok ? 5000 : 3000);
      if (outcome.ok) setBurst({ emoji: outcome.emoji, key: Date.now() });
      if (outcome.leveledUp) showToast(`Level up! ${settingsRef.current.petName} is growing up 🎉`, 'success');
      return { message: outcome.message, ok: outcome.ok };
    },
    [pet, setMoodFor, showToast],
  );

  const addShortcut = useCallback((s: Omit<Shortcut, 'id'>) => {
    setShortcuts((prev) => {
      const next = [...prev, { ...s, id: randomId(8) }];
      void save('shortcuts', next);
      return next;
    });
  }, []);
  const removeShortcut = useCallback((id: string) => {
    setShortcuts((prev) => {
      const next = prev.filter((s) => s.id !== id);
      void save('shortcuts', next);
      return next;
    });
  }, []);

  const value = useMemo<AppContextValue>(
    () => ({
      ready,
      pairing,
      status,
      statusDetail,
      pcConfig,
      pcState,
      messages,
      reactionMood: tempMood,
      talking,
      settings,
      pet,
      shortcuts,
      screenshot,
      pcApps,
      toast,
      burst,
      pairWith,
      pairWithText,
      forgetPc,
      reconnect,
      setManualHost,
      sendChat,
      sendVoice,
      runAction,
      requestScreenshot,
      clearScreenshot,
      requestApps,
      updatePcConfig,
      updateSettings,
      petAction,
      addShortcut,
      removeShortcut,
      sfx,
      tap,
      showToast,
      setMoodFor,
    }),
    [
      ready, pairing, status, statusDetail, pcConfig, pcState, messages, tempMood, talking, settings, pet, shortcuts,
      screenshot, pcApps, toast, burst, pairWith, pairWithText, forgetPc, reconnect, setManualHost, sendChat, sendVoice,
      runAction, requestScreenshot, clearScreenshot, requestApps, updatePcConfig, updateSettings, petAction, addShortcut,
      removeShortcut, sfx, tap, showToast, setMoodFor,
    ],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
