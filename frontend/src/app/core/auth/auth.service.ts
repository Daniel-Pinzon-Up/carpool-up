import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import {
  AuthResult,
  ChallengePurpose,
  DocKind,
  DocumentSummary,
  Me,
  PURPOSE_BY_RESULT,
  PendingChallenge,
  SessionInfo,
} from './auth.models';

const API = '/api/v1';
const CHALLENGE_KEY = 'cp.challenge';

const VERIFY_ENDPOINT: Record<ChallengePurpose, string> = {
  email_verification: `${API}/auth/verify-email`,
  two_factor: `${API}/auth/2fa/verify`,
  password_reset: `${API}/auth/password/reset`,
};

/** Esperas entre reintentos al recuperar la sesion (ms); despues se rinde. */
export const RESTORE_RETRIES = [1000, 2000, 4000];
const MAX_RETRY_AFTER_MS = 10_000;

/** El servidor dijo que la sesion no sirve (no es un fallo pasajero). */
export function isSessionRejected(error: unknown): boolean {
  return error instanceof HttpErrorResponse && (error.status === 401 || error.status === 403);
}

/** Respeta Retry-After (429) si viene, con un tope; si no, la espera por defecto. */
function retryDelay(error: unknown, fallback: number): number {
  const header = error instanceof HttpErrorResponse ? error.headers?.get('Retry-After') : null;
  const seconds = header ? Number(header) : NaN;
  return Number.isFinite(seconds) && seconds > 0
    ? Math.min(seconds * 1000, MAX_RETRY_AFTER_MS)
    : fallback;
}

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function readChallenge(): PendingChallenge | null {
  try {
    const raw = sessionStorage.getItem(CHALLENGE_KEY);
    return raw ? (JSON.parse(raw) as PendingChallenge) : null;
  } catch {
    return null;
  }
}

function writeChallenge(challenge: PendingChallenge | null): void {
  try {
    if (challenge) sessionStorage.setItem(CHALLENGE_KEY, JSON.stringify(challenge));
    else sessionStorage.removeItem(CHALLENGE_KEY);
  } catch {
    // Sin sessionStorage el desafio vive solo en memoria.
  }
}

/**
 * Sesion del usuario. El token de acceso vive solo en memoria (nunca en localStorage);
 * el refresh token es una cookie HttpOnly que el navegador envia a /api/v1/auth.
 */
@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private token: string | null = null;
  private refreshing: Promise<void> | null = null;

  readonly user = signal<Me | null>(null);
  readonly challenge = signal<PendingChallenge | null>(readChallenge());
  readonly isAuthenticated = computed(() => this.user() !== null);
  readonly isActive = computed(() => this.user()?.status === 'active');

  accessToken(): string | null {
    return this.token;
  }

  /**
   * Intenta recuperar la sesion con la cookie al abrir la app. Nunca falla.
   * Un 401 o 403 significa que no hay sesion. Un error pasajero (sin red, 429, 5xx) no:
   * se reintenta unas veces antes de rendirse, para no mandar a /ingresar a alguien con
   * una sesion valida solo porque el servidor tardo o limito las peticiones.
   */
  async restore(): Promise<void> {
    for (let attempt = 0; ; attempt++) {
      try {
        await this.refresh();
        return;
      } catch (error) {
        if (isSessionRejected(error) || attempt >= RESTORE_RETRIES.length) {
          this.clearSession();
          return;
        }
        await wait(retryDelay(error, RESTORE_RETRIES[attempt]));
      }
    }
  }

  /** Renueva el token de acceso. Peticiones simultaneas comparten la misma renovacion. */
  refresh(): Promise<void> {
    this.refreshing ??= firstValueFrom(this.http.post<AuthResult>(`${API}/auth/refresh`, {}))
      .then((result) => this.apply(result))
      .finally(() => (this.refreshing = null));
    return this.refreshing;
  }

  async login(email: string, password: string): Promise<AuthResult> {
    const result = await firstValueFrom(
      this.http.post<AuthResult>(`${API}/auth/login`, { email, password }),
    );
    this.handle(result);
    return result;
  }

  async register(data: FormData): Promise<AuthResult> {
    const result = await firstValueFrom(this.http.post<AuthResult>(`${API}/auth/register`, data));
    this.handle(result);
    return result;
  }

  /** Verifica el codigo del desafio en curso (correo o segundo factor). */
  async verifyCode(code: string): Promise<AuthResult> {
    const challenge = this.requireChallenge();
    const result = await firstValueFrom(
      this.http.post<AuthResult>(VERIFY_ENDPOINT[challenge.purpose], {
        challenge_id: challenge.id,
        code,
      }),
    );
    this.handle(result);
    return result;
  }

  async resendCode(): Promise<void> {
    const challenge = this.requireChallenge();
    const { resend_after_seconds } = await firstValueFrom(
      this.http.post<{ resend_after_seconds: number }>(`${API}/auth/codes/resend`, {
        challenge_id: challenge.id,
      }),
    );
    this.setChallenge({ ...challenge, resendAt: Date.now() + resend_after_seconds * 1000 });
  }

  async forgotPassword(email: string): Promise<void> {
    const result = await firstValueFrom(
      this.http.post<AuthResult>(`${API}/auth/password/forgot`, { email }),
    );
    this.handle(result);
  }

  async resetPassword(code: string, newPassword: string): Promise<void> {
    const challenge = this.requireChallenge();
    await firstValueFrom(
      this.http.post<void>(VERIFY_ENDPOINT.password_reset, {
        challenge_id: challenge.id,
        code,
        new_password: newPassword,
      }),
    );
    this.setChallenge(null);
  }

  /** Elimina la cuenta propia (no se puede deshacer) y cierra la sesion local. */
  async deleteAccount(password: string): Promise<void> {
    await firstValueFrom(this.http.post<void>(`${API}/users/me/delete`, { password }));
    this.clearSession();
  }

  async logout(): Promise<void> {
    try {
      await firstValueFrom(this.http.post<void>(`${API}/auth/logout`, {}));
    } finally {
      this.clearSession();
    }
  }

  async logoutOthers(): Promise<number> {
    const { revoked } = await firstValueFrom(
      this.http.post<{ revoked: number }>(`${API}/auth/logout-others`, {}),
    );
    return revoked;
  }

  sessions(): Promise<SessionInfo[]> {
    return firstValueFrom(this.http.get<SessionInfo[]>(`${API}/auth/sessions`));
  }

  async reloadMe(): Promise<Me> {
    const me = await firstValueFrom(this.http.get<Me>(`${API}/users/me`));
    this.user.set(me);
    return me;
  }

  async updateMe(changes: Partial<Pick<Me, 'program' | 'payment_note'>>): Promise<Me> {
    const me = await firstValueFrom(this.http.patch<Me>(`${API}/users/me`, changes));
    this.user.set(me);
    return me;
  }

  async uploadDocument(kind: DocKind, file: File): Promise<DocumentSummary> {
    const data = new FormData();
    data.append('kind', kind);
    data.append('document', file);
    const document = await firstValueFrom(
      this.http.post<DocumentSummary>(`${API}/users/me/documents`, data),
    );
    await this.reloadMe();
    return document;
  }

  clearSession(): void {
    this.token = null;
    this.user.set(null);
  }

  private handle(result: AuthResult): void {
    if (result.result === 'authenticated') {
      this.apply(result);
      return;
    }
    const purpose = PURPOSE_BY_RESULT[result.result];
    if (purpose && result.challenge_id) {
      this.setChallenge({
        id: result.challenge_id,
        purpose,
        emailHint: result.email_hint ?? '',
        resendAt: Date.now() + (result.resend_after_seconds ?? 60) * 1000,
      });
    }
  }

  private apply(result: AuthResult): void {
    if (result.result !== 'authenticated' || !result.access_token || !result.user) {
      throw new Error('Respuesta de autenticacion incompleta');
    }
    this.token = result.access_token;
    this.user.set(result.user);
    this.setChallenge(null);
  }

  private setChallenge(challenge: PendingChallenge | null): void {
    this.challenge.set(challenge);
    writeChallenge(challenge);
  }

  private requireChallenge(): PendingChallenge {
    const challenge = this.challenge();
    if (!challenge) throw { code: 'CHALLENGE_EXPIRED', message: '', details: {} };
    return challenge;
  }
}
