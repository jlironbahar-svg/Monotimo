/**
 * Desktop Friend — phone <-> PC wire protocol.
 *
 * This file is the single source of truth for message shapes. The PC agent
 * mirrors the `type` names in `pc-agent/desktop_friend/protocol.py`, and a test
 * (`pc-agent/tests/test_protocol_sync.py`) fails if the two drift apart.
 *
 * Transport: one WebSocket at  ws://<pc-ip>:<port>/ws  carrying JSON text frames.
 * Voice replies are fetched over plain HTTP from the URL in `ReplyMsg.audioUrl`.
 */

export const PROTOCOL_VERSION = 1;
export const DEFAULT_PORT = 8765;

/** Scheme used in the pairing QR code: desktopfriend://pair?v=1&h=ip1,ip2&p=8765&t=TOKEN&n=PC-NAME */
export const PAIR_URL_SCHEME = 'desktopfriend';

export interface PairingInfo {
  version: number;
  /** Candidate LAN addresses of the PC, best guess first. */
  hosts: string[];
  port: number;
  /** One-time-ish pairing secret shown in the QR code. Exchanged for a long-lived device token. */
  pairToken: string;
  pcName: string;
}

// ---------------------------------------------------------------------------
// Phone -> PC
// ---------------------------------------------------------------------------

export type QuickAction =
  | 'point' // args: { target: string }
  | 'click' // args: { target: string, button?: 'left'|'right', double?: boolean }
  | 'scroll' // args: { direction: 'up'|'down', amount?: number }
  | 'type' // args: { text: string, enter?: boolean }
  | 'keys' // args: { keys: string[] }   e.g. ['mod','s']
  | 'shortcut' // args: { name: string }  OS-aware named shortcut, e.g. 'screenshot', 'lock', 'new_tab'
  | 'open_app' // args: { name: string }
  | 'open_url' // args: { url: string }
  | 'web_search' // args: { query: string }
  | 'describe_screen' // args: { question?: string }
  | 'cursor_home' // no args
  | 'toggle_cursor'; // no args

export interface HelloMsg {
  type: 'hello';
  protocol: number;
  deviceId: string;
  deviceName: string;
  /** Sent on first pairing (from the QR code). */
  pairToken?: string;
  /** Sent on every later connection. */
  deviceToken?: string;
}

export interface ChatMsg {
  type: 'chat';
  id: string;
  text: string;
  /** Ask the PC to synthesize an ElevenLabs voice reply (default true). */
  speak?: boolean;
}

export interface VoiceMsg {
  type: 'voice';
  id: string;
  /** Base64 encoded audio file (m4a/aac from the phone recorder). */
  audio: string;
  mime: string;
  speak?: boolean;
}

export interface ActionMsg {
  type: 'action';
  id: string;
  action: QuickAction;
  args?: Record<string, unknown>;
}

export interface ScreenshotRequestMsg {
  type: 'screenshot';
  id: string;
  maxWidth?: number;
}

/** Update settings on the PC. Only fields that are present are changed. Keys are stored in the PC's .env file. */
export interface ConfigUpdateMsg {
  type: 'config';
  id: string;
  groqApiKey?: string;
  elevenLabsApiKey?: string;
  elevenLabsVoiceId?: string;
  cursorVisible?: boolean;
  pcSounds?: boolean;
}

export interface PingMsg {
  type: 'ping';
  t: number;
}

/** Ask for the apps installed on the PC (Start menu / Applications / .desktop entries). */
export interface AppsRequestMsg {
  type: 'apps';
  id: string;
}

export type ClientMessage =
  | HelloMsg
  | ChatMsg
  | VoiceMsg
  | ActionMsg
  | ScreenshotRequestMsg
  | ConfigUpdateMsg
  | AppsRequestMsg
  | PingMsg;

// ---------------------------------------------------------------------------
// PC -> Phone
// ---------------------------------------------------------------------------

export type PcState = 'idle' | 'transcribing' | 'thinking' | 'acting' | 'speaking';

export type Mood = 'happy' | 'excited' | 'curious' | 'proud' | 'sad' | 'sleepy';

export interface PcConfigSummary {
  hasGroqKey: boolean;
  hasElevenLabsKey: boolean;
  elevenLabsVoiceId: string;
  cursorVisible: boolean;
  pcSounds: boolean;
  automationEnabled: boolean;
  models: {
    chat: string;
    vision: string;
    stt: string;
    tts: string;
  };
}

export interface ActionLogEntry {
  tool: string;
  ok: boolean;
  detail: string;
}

export interface WelcomeMsg {
  type: 'welcome';
  protocol: number;
  pcName: string;
  platform: string;
  /** Long-lived token the phone stores and sends in later HelloMsgs. */
  deviceToken: string;
  screen: { width: number; height: number };
  config: PcConfigSummary;
}

export interface StatusMsg {
  type: 'status';
  state: PcState;
  detail?: string;
  id?: string;
}

export interface TranscriptMsg {
  type: 'transcript';
  id: string;
  text: string;
}

export interface ReplyMsg {
  type: 'reply';
  id: string;
  text: string;
  /** Path on the PC's HTTP server, e.g. "/audio/abc123.mp3?t=…". Null when TTS is unavailable. */
  audioUrl: string | null;
  mood: Mood;
  actions: ActionLogEntry[];
}

export interface ActionResultMsg {
  type: 'action_result';
  id: string;
  action: QuickAction;
  ok: boolean;
  detail: string;
}

export interface ScreenshotMsg {
  type: 'screenshot';
  id: string;
  /** Base64 JPEG. */
  image: string;
  width: number;
  height: number;
}

export interface ConfigMsg {
  type: 'config';
  id?: string;
  config: PcConfigSummary;
}

export type ErrorCode =
  | 'auth_failed'
  | 'bad_request'
  | 'protocol_mismatch'
  | 'not_configured'
  | 'upstream_error'
  | 'internal';

export interface ErrorMsg {
  type: 'error';
  id?: string;
  code: ErrorCode;
  message: string;
}

export interface PongMsg {
  type: 'pong';
  t: number;
}

export interface AppsMsg {
  type: 'apps';
  id: string;
  /** Display names, sorted. Open one with ActionMsg { action: 'open_app', args: { name } }. */
  apps: string[];
}

export type ServerMessage =
  | WelcomeMsg
  | StatusMsg
  | TranscriptMsg
  | ReplyMsg
  | ActionResultMsg
  | ScreenshotMsg
  | ConfigMsg
  | ErrorMsg
  | AppsMsg
  | PongMsg;

// ---------------------------------------------------------------------------
// Helpers shared by the app
// ---------------------------------------------------------------------------

/** Parse a pairing QR payload. Accepts the desktopfriend:// URL form or a raw JSON object. */
export function parsePairingPayload(raw: string): PairingInfo | null {
  const text = raw.trim();
  try {
    if (text.startsWith('{')) {
      const o = JSON.parse(text);
      const hosts: string[] = Array.isArray(o.hosts) ? o.hosts : o.host ? [o.host] : [];
      if (!hosts.length || !o.port || !o.token) return null;
      return {
        version: Number(o.v ?? 1),
        hosts,
        port: Number(o.port),
        pairToken: String(o.token),
        pcName: String(o.name ?? 'My PC'),
      };
    }
    const prefix = `${PAIR_URL_SCHEME}://pair?`;
    if (!text.toLowerCase().startsWith(prefix)) return null;
    const params: Record<string, string> = {};
    for (const part of text.slice(prefix.length).split('&')) {
      const eq = part.indexOf('=');
      if (eq <= 0) continue;
      params[decodeURIComponent(part.slice(0, eq))] = decodeURIComponent(part.slice(eq + 1).replace(/\+/g, ' '));
    }
    const hosts = (params.h ?? '').split(',').map((h) => h.trim()).filter(Boolean);
    const port = Number(params.p);
    if (!hosts.length || !port || !params.t) return null;
    return {
      version: Number(params.v ?? 1),
      hosts,
      port,
      pairToken: params.t,
      pcName: params.n || 'My PC',
    };
  } catch {
    return null;
  }
}
