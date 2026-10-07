import { HttpClient } from '@angular/common/http';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { TranslocoPipe, TranslocoService } from '@jsverse/transloco';
import {
  LucideBell,
  LucideBellOff,
  LucideCalendarX,
  LucideCheckCheck,
  LucideCircleCheck,
  LucideCircleX,
  LucideHourglass,
  LucideFlagTriangleRight,
  LucideInbox,
  LucidePlay,
  LucideSiren,
  LucideStar,
  LucideUserX,
  LucideMessageCircle,
  LucideRoute,
  LucideTicket,
  LucideDynamicIcon,
  LucideIcon,
  LucideUserCog,
} from '@icons';
import { firstValueFrom } from 'rxjs';
import { apiErrorMessage } from '../../core/http/api-error-message';
import { EmptyState } from '../../shared/ui/empty-state';
import { ErrorState } from '../../shared/ui/error-state';
import { GlassButton } from '../../shared/ui/glass-button';
import { GlassCard } from '../../shared/ui/glass-card';
import { Skeleton } from '../../shared/ui/skeleton';
import { ToastService } from '../../shared/ui/toast.service';
import { AppNotification, NotificationsStore } from '../../core/notifications/notifications.store';

const ICONS: Record<string, LucideIcon> = {
  document_approved: LucideCircleCheck,
  license_approved: LucideCircleCheck,
  document_rejected: LucideCircleX,
  license_rejected: LucideCircleX,
  document_expired: LucideCalendarX,
  account_revalidation_required: LucideCalendarX,
  role_changed: LucideUserCog,
  booking_requested: LucideInbox,
  cancellation_requested: LucideInbox,
  subscription_requested: LucideInbox,
  booking_accepted: LucideTicket,
  subscription_accepted: LucideTicket,
  cancellation_accepted: LucideCircleCheck,
  booking_rejected: LucideCircleX,
  subscription_rejected: LucideCircleX,
  cancellation_rejected: LucideCircleX,
  booking_cancelled_by_driver: LucideCalendarX,
  booking_auto_cancelled_late: LucideCalendarX,
  booking_pico_placa_cancelled: LucideCalendarX,
  trip_pico_placa_cancelled: LucideCalendarX,
  trip_changed: LucideRoute,
  waitlist_offer: LucideHourglass,
  message_new: LucideMessageCircle,
  trip_reminder: LucideHourglass,
  trip_reminder_driver: LucideHourglass,
  trip_started: LucidePlay,
  trip_finished: LucideFlagTriangleRight,
  trip_not_held: LucideCalendarX,
  passenger_no_show: LucideUserX,
  booking_suspended: LucideUserX,
  emergency_alert: LucideSiren,
  account_suspended: LucideUserX,
  account_reinstated: LucideCircleCheck,
  booking_ban_lifted: LucideCircleCheck,
  trip_cancelled_by_admin: LucideCalendarX,
  rating_pending: LucideStar,
  rating_reminder: LucideStar,
  rating_received: LucideStar,
};

/** A donde lleva cada aviso al abrirlo. */
const LINKS: Record<string, string> = {
  document_rejected: '/perfil',
  document_expired: '/perfil',
  license_approved: '/licencia',
  license_rejected: '/licencia',
  role_changed: '/perfil',
  booking_requested: '/solicitudes',
  cancellation_requested: '/solicitudes',
  subscription_requested: '/solicitudes',
  waitlist_offer: '/mis-viajes',
  waitlist_offer_expired: '/mis-viajes',
  subscription_accepted: '/mis-viajes',
  subscription_rejected: '/mis-viajes',
  subscription_expired: '/mis-viajes',
  subscription_ended: '/mis-viajes',
  booking_suspended: '/mis-viajes',
  emergency_alert: '/admin/emergencias',
  account_suspended: '/perfil',
  account_reinstated: '/perfil',
  booking_ban_lifted: '/mis-viajes',
};

/** Bandeja de avisos; los nuevos llegan en vivo y se agregan arriba. */
@Component({
  selector: 'cp-notifications-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    RouterLink,
    TranslocoPipe,
    EmptyState,
    ErrorState,
    GlassButton,
    GlassCard,
    Skeleton,
    LucideDynamicIcon,
    LucideCheckCheck,
  ],
  template: `
    <div class="mx-auto flex max-w-3xl flex-col gap-5 py-2">
      <header class="flex flex-wrap items-center justify-between gap-3">
        <h1 class="text-2xl font-bold sm:text-3xl">{{ 'nav.notifications' | transloco }}</h1>
        <button
          cp-button
          variant="secondary"
          type="button"
          [disabled]="!hasUnread()"
          (click)="markAll()"
        >
          <svg lucideCheckCheck class="size-4" aria-hidden="true"></svg>
          {{ 'notifications.markAll' | transloco }}
        </button>
      </header>

      <cp-glass-card class="!p-2" [attr.aria-busy]="loading()">
        @if (loading()) {
          <div class="flex flex-col gap-4 p-4">
            @for (row of [1, 2, 3]; track row) {
              <cp-skeleton [lines]="2" />
            }
          </div>
        } @else if (loadError(); as message) {
          <cp-error-state [message]="message" (retry)="load()" />
        } @else if (items().length === 0) {
          <cp-empty-state
            [icon]="emptyIcon"
            [title]="'notifications.empty.title' | transloco"
            [description]="'notifications.empty.body' | transloco"
          />
        } @else {
          <ul class="flex flex-col">
            @for (item of items(); track item.id) {
              <li>
                <a
                  [routerLink]="link(item)"
                  (click)="markRead(item)"
                  class="flex gap-3 rounded-2xl p-4 transition hover:bg-glass-strong"
                >
                  <span
                    class="relative grid size-11 shrink-0 place-items-center rounded-xl bg-primary/15"
                  >
                    <svg
                      [lucideIcon]="icon(item)"
                      class="size-5 text-primary"
                      aria-hidden="true"
                    ></svg>
                    @if (!item.read_at) {
                      <span
                        class="absolute -top-0.5 -right-0.5 size-3 rounded-full bg-accent ring-2 ring-[var(--bg)]"
                      ></span>
                    }
                  </span>
                  <span class="min-w-0 flex-1">
                    <span class="block" [class.font-semibold]="!item.read_at">
                      {{ 'notifications.kinds.' + item.kind | transloco: item.payload }}
                    </span>
                    <span class="block text-sm text-muted">
                      {{ when(item.created_at) }}
                      @if (!item.read_at) {
                        <span class="sr-only">{{ 'notifications.unread' | transloco }}</span>
                      }
                    </span>
                  </span>
                </a>
              </li>
            }
          </ul>
        }
      </cp-glass-card>
    </div>
  `,
})
export default class NotificationsPage {
  private readonly http = inject(HttpClient);
  private readonly transloco = inject(TranslocoService);
  private readonly toasts = inject(ToastService);

  protected readonly emptyIcon = LucideBellOff;
  protected readonly items = signal<AppNotification[]>([]);
  protected readonly loading = signal(true);
  protected readonly loadError = signal<string | null>(null);
  protected hasUnread = () => this.items().some((item) => !item.read_at);

  constructor() {
    void this.load();
    inject(NotificationsStore)
      .incoming.pipe(takeUntilDestroyed())
      .subscribe((item) =>
        this.items.update((list) => (list.some((i) => i.id === item.id) ? list : [item, ...list])),
      );
  }

  protected async load(): Promise<void> {
    this.loading.set(true);
    this.loadError.set(null);
    try {
      const page = await firstValueFrom(
        this.http.get<{ items: AppNotification[] }>('/api/v1/notifications', {
          params: { limit: '50' },
        }),
      );
      this.items.set(page.items);
    } catch (error) {
      this.loadError.set(apiErrorMessage(this.transloco, error));
    } finally {
      this.loading.set(false);
    }
  }

  protected icon(item: AppNotification): LucideIcon {
    return ICONS[item.kind] ?? LucideBell;
  }

  /** Destino fijo del tipo o, si el aviso trae un viaje o una serie, su detalle. */
  protected link(item: AppNotification): string {
    const fixed = LINKS[item.kind];
    if (fixed) return fixed;
    const { trip_id: trip, series_id: series, conversation_id: chat } = item.payload;
    if (typeof chat === 'string') return `/mensajes/${chat}`;
    if (
      (item.kind === 'rating_pending' || item.kind === 'rating_reminder') &&
      typeof trip === 'string'
    ) {
      return `/calificar/${trip}`;
    }
    if (item.kind === 'rating_received') return '/perfil';
    if (typeof trip === 'string') return `/viajes/${trip}`;
    if (typeof series === 'string') return `/series/${series}`;
    return '/notificaciones';
  }

  protected when(iso: string): string {
    return new Date(iso).toLocaleString(this.transloco.getActiveLang(), {
      dateStyle: 'medium',
      timeStyle: 'short',
    });
  }

  protected markRead(item: AppNotification): void {
    if (item.read_at) return;
    this.items.update((list) =>
      list.map((i) => (i.id === item.id ? { ...i, read_at: new Date().toISOString() } : i)),
    );
    void firstValueFrom(this.http.post(`/api/v1/notifications/${item.id}/read`, {})).catch(() => {
      // Si falla, el aviso vuelve a aparecer como no leido la proxima vez.
    });
  }

  protected async markAll(): Promise<void> {
    try {
      await firstValueFrom(this.http.post('/api/v1/notifications/read-all', {}));
      const now = new Date().toISOString();
      this.items.update((list) => list.map((i) => ({ ...i, read_at: i.read_at ?? now })));
    } catch (error) {
      this.toasts.show(apiErrorMessage(this.transloco, error), 'danger');
    }
  }
}
