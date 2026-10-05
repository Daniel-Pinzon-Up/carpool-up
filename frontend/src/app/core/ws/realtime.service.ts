import { DestroyRef, Injectable, effect, inject, signal, untracked } from '@angular/core';
import { Observable, Subject, filter } from 'rxjs';
import { AuthService } from '../auth/auth.service';

/** Evento del servidor; type dice que trae (notification, message, typing, ...). */
export interface LiveEvent {
  type: string;
  [key: string]: unknown;
}

export type LiveStatus = 'idle' | 'connecting' | 'open' | 'reconnecting';

const PING_MS = 25_000;
const MAX_BACKOFF_MS = 30_000;
/** Cierres del servidor: token vencido (renovar y volver) o rechazado. */
const CLOSE_TOKEN_EXPIRED = 4001;
const CLOSE_UNAUTHORIZED = 4401;

/**
 * Canal en tiempo real (WebSocket /ws). Se conecta solo mientras hay sesion, se autentica
 * con el primer mensaje y se reconecta con retroceso exponencial (1 s, 2 s, 4 s... hasta
 * 30 s), al volver la red o al volver a la pestana. Tras reconectar emite "reconnected"
 * para que las vistas pidan por HTTP lo que se perdieron.
 */
@Injectable({ providedIn: 'root' })
export class RealtimeService {
  private readonly auth = inject(AuthService);

  private socket: WebSocket | null = null;
  private attempts = 0;
  private everOpened = false;
  private retryTimer: ReturnType<typeof setTimeout> | null = null;
  private pingTimer: ReturnType<typeof setInterval> | null = null;
  private readonly events$ = new Subject<LiveEvent>();

  readonly status = signal<LiveStatus>('idle');

  constructor() {
    effect(() => {
      const signedIn = this.auth.isAuthenticated();
      untracked(() => (signedIn ? this.connect() : this.disconnect()));
    });
    const wake = () => {
      if (this.auth.isAuthenticated() && this.status() === 'reconnecting') this.connectNow();
    };
    const onVisible = () => {
      if (document.visibilityState === 'visible') wake();
    };
    globalThis.addEventListener?.('online', wake);
    document.addEventListener('visibilitychange', onVisible);
    inject(DestroyRef).onDestroy(() => {
      globalThis.removeEventListener?.('online', wake);
      document.removeEventListener('visibilitychange', onVisible);
      this.disconnect();
    });
  }

  /** Eventos de un tipo (o de varios). */
  on<T extends LiveEvent = LiveEvent>(...types: string[]): Observable<T> {
    return this.events$.pipe(filter((event): event is T => types.includes(event.type)));
  }

  /** Envia si hay conexion; si no, devuelve false para usar el respaldo HTTP. */
  send(message: Record<string, unknown>): boolean {
    if (this.socket?.readyState !== WebSocket.OPEN || this.status() !== 'open') return false;
    this.socket.send(JSON.stringify(message));
    return true;
  }

  private connect(): void {
    if (this.socket || this.status() === 'connecting') return;
    this.connectNow();
  }

  private connectNow(): void {
    this.clearTimers();
    this.socket?.close();
    const token = this.auth.accessToken();
    if (!token) {
      // Sin token en memoria (recien cargada la pagina): se renueva y se intenta de nuevo.
      void this.auth.refresh().then(
        () => this.connectNow(),
        () => this.scheduleRetry(),
      );
      return;
    }
    this.status.set(this.everOpened ? 'reconnecting' : 'connecting');
    const protocol = location.protocol === 'https:' ? 'wss' : 'ws';
    const socket = new WebSocket(`${protocol}://${location.host}/ws`);
    this.socket = socket;
    socket.onopen = () => socket.send(JSON.stringify({ type: 'auth', token }));
    socket.onmessage = (message) => this.receive(message.data);
    socket.onclose = (event) => {
      if (this.socket !== socket) return; // Una conexion vieja ya reemplazada.
      this.socket = null;
      this.clearTimers();
      if (!this.auth.isAuthenticated()) {
        this.status.set('idle');
        return;
      }
      this.status.set('reconnecting');
      if (event.code === CLOSE_TOKEN_EXPIRED || event.code === CLOSE_UNAUTHORIZED) {
        void this.auth.refresh().then(
          () => this.connectNow(),
          () => this.scheduleRetry(),
        );
        return;
      }
      this.scheduleRetry();
    };
  }

  private receive(data: unknown): void {
    let event: LiveEvent;
    try {
      event = JSON.parse(String(data)) as LiveEvent;
    } catch {
      return;
    }
    if (event.type === 'ready') {
      const reconnected = this.everOpened;
      this.everOpened = true;
      this.attempts = 0;
      this.status.set('open');
      this.pingTimer = setInterval(() => this.send({ type: 'ping' }), PING_MS);
      if (reconnected) this.events$.next({ type: 'reconnected' });
      return;
    }
    if (event.type !== 'pong') this.events$.next(event);
  }

  private scheduleRetry(): void {
    const base = Math.min(MAX_BACKOFF_MS, 1000 * 2 ** this.attempts);
    this.attempts++;
    const delay = base / 2 + Math.random() * (base / 2);
    this.retryTimer = setTimeout(() => this.connectNow(), delay);
  }

  private clearTimers(): void {
    if (this.retryTimer) clearTimeout(this.retryTimer);
    if (this.pingTimer) clearInterval(this.pingTimer);
    this.retryTimer = this.pingTimer = null;
  }

  private disconnect(): void {
    this.clearTimers();
    const socket = this.socket;
    this.socket = null;
    socket?.close(1000);
    this.attempts = 0;
    this.everOpened = false;
    this.status.set('idle');
  }
}
