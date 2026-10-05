import { HttpClient } from '@angular/common/http';
import { Injectable, effect, inject, signal, untracked } from '@angular/core';
import { Router } from '@angular/router';
import { TranslocoService } from '@jsverse/transloco';
import { Observable, Subject, firstValueFrom } from 'rxjs';
import { ToastService } from '../../shared/ui/toast.service';
import { AuthService } from '../auth/auth.service';
import { LiveEvent, RealtimeService } from '../ws/realtime.service';

export interface AppNotification {
  id: string;
  kind: string;
  payload: Record<string, unknown>;
  read_at: string | null;
  created_at: string;
}

interface NotificationEvent extends LiveEvent {
  notification: AppNotification;
}

/** Avisos que no se muestran como toast: el chat ya tiene su propio contador. */
const QUIET_KINDS = new Set(['message_new']);

/**
 * Contador de avisos sin leer y llegada en vivo. Lo carga al iniciar sesion, lo ajusta con
 * los eventos del WebSocket (tambien las lecturas hechas en otra pestana) y lo vuelve a
 * pedir al reconectar, por si se perdio algo.
 */
@Injectable({ providedIn: 'root' })
export class NotificationsStore {
  private readonly http = inject(HttpClient);
  private readonly auth = inject(AuthService);
  private readonly realtime = inject(RealtimeService);
  private readonly toast = inject(ToastService);
  private readonly transloco = inject(TranslocoService);
  private readonly router = inject(Router);
  private readonly incoming$ = new Subject<AppNotification>();

  readonly unread = signal(0);
  /** Avisos que llegan en vivo (la bandeja los agrega arriba). */
  readonly incoming: Observable<AppNotification> = this.incoming$.asObservable();

  constructor() {
    effect(() => {
      const signedIn = this.auth.isAuthenticated();
      untracked(() => (signedIn ? void this.reload() : this.unread.set(0)));
    });
    this.realtime.on<NotificationEvent>('notification').subscribe(({ notification }) => {
      this.unread.update((count) => count + 1);
      this.incoming$.next(notification);
      if (!QUIET_KINDS.has(notification.kind) && this.router.url !== '/notificaciones') {
        this.toast.show(
          this.transloco.translate(
            `notifications.kinds.${notification.kind}`,
            notification.payload,
          ),
          'info',
        );
      }
    });
    this.realtime
      .on('notification.read')
      .subscribe(() => this.unread.update((count) => Math.max(0, count - 1)));
    this.realtime.on('notification.read_all').subscribe(() => this.unread.set(0));
    this.realtime.on('reconnected').subscribe(() => void this.reload());
  }

  async reload(): Promise<void> {
    try {
      const { unread } = await firstValueFrom(
        this.http.get<{ unread: number }>('/api/v1/notifications/unread-count'),
      );
      this.unread.set(unread);
    } catch {
      // El contador es informativo: si falla, se intenta en la proxima reconexion.
    }
  }
}
