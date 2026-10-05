import { HttpClient } from '@angular/common/http';
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
  LucideDynamicIcon,
  LucideIcon,
  LucideUserCog,
} from '@lucide/angular';
import { firstValueFrom } from 'rxjs';
import { apiErrorMessage } from '../../core/http/api-error-message';
import { EmptyState } from '../../shared/ui/empty-state';
import { GlassButton } from '../../shared/ui/glass-button';
import { GlassCard } from '../../shared/ui/glass-card';
import { Skeleton } from '../../shared/ui/skeleton';
import { ToastService } from '../../shared/ui/toast.service';

interface AppNotification {
  id: string;
  kind: string;
  payload: Record<string, unknown>;
  read_at: string | null;
  created_at: string;
}

const ICONS: Record<string, LucideIcon> = {
  document_approved: LucideCircleCheck,
  license_approved: LucideCircleCheck,
  document_rejected: LucideCircleX,
  license_rejected: LucideCircleX,
  document_expired: LucideCalendarX,
  account_revalidation_required: LucideCalendarX,
  role_changed: LucideUserCog,
};

/** A donde lleva cada aviso al abrirlo. */
const LINKS: Record<string, string> = {
  document_rejected: '/perfil',
  document_expired: '/perfil',
  license_approved: '/licencia',
  license_rejected: '/licencia',
  role_changed: '/perfil',
};

/** Bandeja de avisos. El paso 9 agrega la llegada en vivo. */
@Component({
  selector: 'cp-notifications-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    RouterLink,
    TranslocoPipe,
    EmptyState,
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
  protected hasUnread = () => this.items().some((item) => !item.read_at);

  constructor() {
    void this.load();
  }

  private async load(): Promise<void> {
    try {
      const page = await firstValueFrom(
        this.http.get<{ items: AppNotification[] }>('/api/v1/notifications', {
          params: { limit: '50' },
        }),
      );
      this.items.set(page.items);
    } catch (error) {
      this.toasts.show(apiErrorMessage(this.transloco, error), 'danger');
    } finally {
      this.loading.set(false);
    }
  }

  protected icon(item: AppNotification): LucideIcon {
    return ICONS[item.kind] ?? LucideBell;
  }

  protected link(item: AppNotification): string {
    return LINKS[item.kind] ?? '/notificaciones';
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
