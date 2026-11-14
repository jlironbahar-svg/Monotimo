import {
  PROTOCOL_VERSION,
  type ClientMessage,
  type PairingInfo,
  type ServerMessage,
  type WelcomeMsg,
} from '../../../shared/protocol';

/** What the phone remembers about the PC it is paired with. */
export interface StoredPairing {
  hosts: string[];
  port: number;
  pcName: string;
  /** From the QR code. Dropped once a device token has been issued. */
  pairToken?: string;
  /** Long-lived token issued by the PC on first pairing. */
  deviceToken?: string;
  /** Address that worked last time; tried first. */
  lastHost?: string;
}

export type ConnStatus =
  | 'idle'
  | 'connecting'
  | 'connected'
  | 'reconnecting'
  | 'unreachable' // several rounds failed; still retrying slowly in the background
  | 'rejected'; // auth failed / protocol mismatch: user action needed (re-scan QR, update app)

export function pairingFromInfo(info: PairingInfo): StoredPairing {
  return { hosts: info.hosts, port: info.port, pcName: info.pcName, pairToken: info.pairToken };
}

type Listener<T extends unknown[]> = (...args: T) => void;

const OPEN_TIMEOUT_MS = 4000;
const PING_EVERY_MS = 15000;
const PONG_TIMEOUT_MS = 10000;

/**
 * WebSocket client with host fail-over, exponential back-off reconnects and keep-alive pings.
 * UI code subscribes with `on('status' | 'message' | 'welcome', fn)`.
 */
export class DesktopConnection {
  private ws: WebSocket | null = null;
  private pairing: StoredPairing | null = null;
  private status: ConnStatus = 'idle';
  private statusDetail = '';
  private manualClose = true;
  private failedRounds = 0;
  private activeHost: string | null = null;
  private retryTimer: ReturnType<typeof setTimeout> | null = null;
  private pingTimer: ReturnType<typeof setInterval> | null = null;
  private lastPong = 0;
  private statusListeners = new Set<Listener<[ConnStatus, string]>>();
  private messageListeners = new Set<Listener<[ServerMessage]>>();
  private welcomeListeners = new Set<Listener<[WelcomeMsg, StoredPairing]>>();

  constructor(
    private readonly deviceId: string,
    private readonly deviceName: string,
  ) {}

  // -- subscriptions -------------------------------------------------------
  onStatus(fn: Listener<[ConnStatus, string]>): () => void {
    this.statusListeners.add(fn);
    return () => this.statusListeners.delete(fn);
  }
  onMessage(fn: Listener<[ServerMessage]>): () => void {
    this.messageListeners.add(fn);
    return () => this.messageListeners.delete(fn);
  }
  onWelcome(fn: Listener<[WelcomeMsg, StoredPairing]>): () => void {
    this.welcomeListeners.add(fn);
    return () => this.welcomeListeners.delete(fn);
  }

  // -- state ---------------------------------------------------------------
  getStatus(): ConnStatus {
    return this.status;
  }

  /** http://host:port of the PC we're connected to (for audio downloads). */
  baseUrl(): string | null {
    const host = this.activeHost ?? this.pairing?.lastHost ?? this.pairing?.hosts[0];
    return host && this.pairing ? `http://${host}:${this.pairing.port}` : null;
  }

  // -- lifecycle -------------------------------------------------------------
  start(pairing: StoredPairing): void {
    this.stop();
    this.pairing = { ...pairing };
    this.manualClose = false;
    this.failedRounds = 0;
    this.connectRound();
  }

  stop(): void {
    this.manualClose = true;
    this.clearTimers();
    const ws = this.ws;
    this.ws = null;
    if (ws) {
      try {
        ws.close();
      } catch {
        /* already closed */
      }
    }
    this.setStatus('idle');
  }

  /** Reconnect immediately (e.g. app returned to the foreground or user tapped Retry). */
  retryNow(): void {
    if (!this.pairing || this.status === 'connected') return;
    this.manualClose = false;
    this.clearTimers();
    this.failedRounds = 0;
    this.connectRound();
  }

  send(msg: ClientMessage): boolean {
    if (this.ws && this.ws.readyState === WebSocket.OPEN && this.status === 'connected') {
      this.ws.send(JSON.stringify(msg));
      return true;
    }
    return false;
  }

  // -- internals -------------------------------------------------------------
  private setStatus(status: ConnStatus, detail = ''): void {
    if (status === this.status && detail === this.statusDetail) return;
    this.status = status;
    this.statusDetail = detail;
    this.statusListeners.forEach((fn) => fn(status, detail));
  }

  private clearTimers(): void {
    if (this.retryTimer) clearTimeout(this.retryTimer);
    if (this.pingTimer) clearInterval(this.pingTimer);
    this.retryTimer = null;
    this.pingTimer = null;
  }

  private hostsInOrder(): string[] {
    if (!this.pairing) return [];
    const { hosts, lastHost } = this.pairing;
    return lastHost ? [lastHost, ...hosts.filter((h) => h !== lastHost)] : [...hosts];
  }

  private connectRound(): void {
    if (this.manualClose || !this.pairing) return;
    if (this.status !== 'unreachable') this.setStatus(this.failedRounds === 0 ? 'connecting' : 'reconnecting');
    this.tryHost(this.hostsInOrder(), 0);
  }

  private scheduleRetry(): void {
    if (this.manualClose || this.status === 'rejected') return;
    this.failedRounds += 1;
    if (this.failedRounds >= 3) this.setStatus('unreachable', 'Is Desktop Friend running on your PC, on the same Wi-Fi?');
    const delay = Math.min(15000, 1000 * 2 ** (this.failedRounds - 1));
    this.retryTimer = setTimeout(() => this.connectRound(), delay);
  }

  private tryHost(hosts: string[], index: number): void {
    if (this.manualClose || !this.pairing) return;
    if (index >= hosts.length) {
      this.scheduleRetry();
      return;
    }
    const host = hosts[index];
    let opened = false;
    let advanced = false;
    const next = () => {
      if (advanced) return;
      advanced = true;
      this.tryHost(hosts, index + 1);
    };

    let ws: WebSocket;
    try {
      ws = new WebSocket(`ws://${host}:${this.pairing.port}/ws`);
    } catch {
      next();
      return;
    }
    this.ws = ws;
    const openTimer = setTimeout(() => {
      if (!opened) {
        try {
          ws.close();
        } catch {
          /* ignore */
        }
        next();
      }
    }, OPEN_TIMEOUT_MS);

    ws.onopen = () => {
      opened = true;
      clearTimeout(openTimer);
      const p = this.pairing!;
      ws.send(
        JSON.stringify({
          type: 'hello',
          protocol: PROTOCOL_VERSION,
          deviceId: this.deviceId,
          deviceName: this.deviceName,
          ...(p.deviceToken ? { deviceToken: p.deviceToken } : { pairToken: p.pairToken }),
        } satisfies ClientMessage),
      );
    };
    ws.onmessage = (event) => this.handle(String(event.data), host);
    ws.onerror = () => {
      /* onclose follows */
    };
    ws.onclose = () => {
      clearTimeout(openTimer);
      if (this.ws !== ws) return; // superseded by a newer socket
      if (!opened) {
        next();
        return;
      }
      this.ws = null;
      if (this.pingTimer) clearInterval(this.pingTimer);
      this.pingTimer = null;
      if (this.manualClose || this.status === 'rejected') return;
      this.setStatus('reconnecting');
      this.failedRounds = 0;
      this.retryTimer = setTimeout(() => this.connectRound(), 800);
    };
  }

  private handle(data: string, host: string): void {
    let msg: ServerMessage;
    try {
      msg = JSON.parse(data);
    } catch {
      return;
    }
    if (msg.type === 'welcome') {
      const updated: StoredPairing = {
        ...this.pairing!,
        deviceToken: msg.deviceToken,
        lastHost: host,
        pcName: msg.pcName || this.pairing!.pcName,
      };
      delete updated.pairToken;
      this.pairing = updated;
      this.activeHost = host;
      this.failedRounds = 0;
      this.lastPong = Date.now();
      this.startPing();
      this.setStatus('connected');
      this.welcomeListeners.forEach((fn) => fn(msg as WelcomeMsg, updated));
    } else if (msg.type === 'pong') {
      this.lastPong = Date.now();
    } else if (msg.type === 'error' && (msg.code === 'auth_failed' || msg.code === 'protocol_mismatch')) {
      this.setStatus('rejected', msg.message);
      this.manualClose = true;
    }
    this.messageListeners.forEach((fn) => fn(msg));
  }

  private startPing(): void {
    if (this.pingTimer) clearInterval(this.pingTimer);
    this.pingTimer = setInterval(() => {
      if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
      if (Date.now() - this.lastPong > PING_EVERY_MS + PONG_TIMEOUT_MS) {
        this.ws.close(); // dead connection: onclose schedules a reconnect
        return;
      }
      this.ws.send(JSON.stringify({ type: 'ping', t: Date.now() } satisfies ClientMessage));
    }, PING_EVERY_MS);
  }
}
