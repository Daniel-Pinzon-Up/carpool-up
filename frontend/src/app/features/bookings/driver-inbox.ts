import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { TranslocoPipe, TranslocoService } from '@jsverse/transloco';
import { LucideArrowRight, LucideInbox, LucideRefreshCw } from '@icons';
import { apiErrorMessage } from '../../core/http/api-error-message';
import { NotificationsStore } from '../../core/notifications/notifications.store';
import { LanguageService } from '../../core/i18n/language.service';
import { Avatar } from '../../shared/ui/avatar';
import { EmptyState } from '../../shared/ui/empty-state';
import { GlassButton } from '../../shared/ui/glass-button';
import { GlassCard } from '../../shared/ui/glass-card';
import { ErrorState } from '../../shared/ui/error-state';
import { Skeleton } from '../../shared/ui/skeleton';
import { BookingActions } from './booking-actions';
import { BookingCard } from './booking-card';
import { BOOKING_PREFERENCE_KEYS, Booking, BookingsApi, Inbox, Subscription } from './bookings.api';

/** Avisos que cambian lo que hay por decidir. */
const INBOX_KINDS = new Set([
  'booking_requested',
  'booking_withdrawn',
  'cancellation_requested',
  'subscription_requested',
  'subscription_cancelled',
]);

/**
 * Solicitudes del conductor: reservas, cancelaciones tardias y suscripciones a series que
 * esperan su decision, de la salida mas proxima a la mas lejana.
 */
@Component({
  selector: 'cp-driver-inbox',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    RouterLink,
    TranslocoPipe,
    Avatar,
    BookingCard,
    EmptyState,
    ErrorState,
    GlassButton,
    GlassCard,
    Skeleton,
    LucideArrowRight,
    LucideRefreshCw,
  ],
  template: `
    <div class="mx-auto flex max-w-4xl flex-col gap-6 py-2">
      <header class="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 class="text-2xl font-bold sm:text-3xl">{{ 'bookings.inbox.title' | transloco }}</h1>
          <p class="text-muted">{{ 'bookings.inbox.subtitle' | transloco }}</p>
        </div>
        <button cp-button variant="secondary" type="button" (click)="load()">
          <svg lucideRefreshCw class="size-4" aria-hidden="true"></svg>
          {{ 'bookings.inbox.refresh' | transloco }}
        </button>
      </header>

      @if (inbox(); as box) {
        @if (total() === 0) {
          <cp-empty-state
            [icon]="emptyIcon"
            [title]="'bookings.inbox.empty' | transloco"
            [description]="'bookings.inbox.emptyHint' | transloco"
          />
        }
        @if (box.bookings.length) {
          <section aria-labelledby="inbox-bookings" class="flex flex-col gap-3">
            <h2 id="inbox-bookings" class="text-xl font-bold">
              {{ 'bookings.inbox.requests' | transloco: { count: box.bookings.length } }}
            </h2>
            @for (b of box.bookings; track b.id) {
              <cp-booking-card [booking]="b" view="driver">
                <button cp-button type="button" (click)="accept(b)">
                  {{ 'bookings.inbox.accept' | transloco }}
                </button>
                <button cp-button variant="secondary" type="button" (click)="reject(b)">
                  {{ 'bookings.inbox.reject' | transloco }}
                </button>
              </cp-booking-card>
            }
          </section>
        }
        @if (box.cancellations.length) {
          <section aria-labelledby="inbox-cancellations" class="flex flex-col gap-3">
            <h2 id="inbox-cancellations" class="text-xl font-bold">
              {{ 'bookings.inbox.cancellations' | transloco: { count: box.cancellations.length } }}
            </h2>
            <p class="text-sm text-muted">{{ 'bookings.inbox.cancellationsHint' | transloco }}</p>
            @for (b of box.cancellations; track b.id) {
              <cp-booking-card [booking]="b" view="driver">
                @if (b.cancellation; as c) {
                  <button cp-button type="button" (click)="resolve(c.id, true)">
                    {{ 'bookings.inbox.acceptCancellation' | transloco }}
                  </button>
                  <button
                    cp-button
                    variant="secondary"
                    type="button"
                    (click)="resolve(c.id, false)"
                  >
                    {{ 'bookings.inbox.rejectCancellation' | transloco }}
                  </button>
                }
              </cp-booking-card>
            }
          </section>
        }
        @if (box.subscriptions.length) {
          <section aria-labelledby="inbox-subscriptions" class="flex flex-col gap-3">
            <h2 id="inbox-subscriptions" class="text-xl font-bold">
              {{ 'bookings.inbox.subscriptions' | transloco: { count: box.subscriptions.length } }}
            </h2>
            @for (sub of box.subscriptions; track sub.id) {
              <article class="glass-1 !rounded-2xl flex flex-col gap-3 p-4">
                <a
                  [routerLink]="['/series', sub.series.id]"
                  class="flex min-w-0 items-center gap-2 font-semibold underline-offset-4 hover:underline"
                >
                  <span class="truncate">{{ sub.series.origin }}</span>
                  <svg lucideArrowRight class="size-4 shrink-0 text-muted" aria-hidden="true"></svg>
                  <span class="sr-only">{{ 'trips.to' | transloco }}</span>
                  <span class="truncate">{{ sub.series.destination }}</span>
                  · {{ sub.series.departure_time.slice(0, 5) }}
                </a>
                <div class="flex items-center gap-3">
                  <cp-avatar [name]="sub.passenger.full_name" size="sm" />
                  <div class="min-w-0">
                    <p class="truncate font-semibold">{{ sub.passenger.full_name }}</p>
                    <p class="truncate text-xs text-muted">
                      @if (sub.passenger.program) {
                        {{ sub.passenger.program }} ·
                      }
                      {{
                        'bookings.card.trips'
                          | transloco: { count: sub.passenger.trips_as_passenger }
                      }}
                    </p>
                  </div>
                </div>
                <p class="text-sm">
                  {{
                    'bookings.subscription.range'
                      | transloco: { start: date(sub.from_date), end: date(sub.to_date) }
                  }}
                  · {{ 'trips.seats' | transloco: { count: sub.seats } }}
                </p>
                <p class="text-sm text-muted">
                  {{ sub.pickup_place }} → {{ sub.dropoff_place }}
                  @for (key of prefs(sub); track key) {
                    · {{ 'search.prefs.' + key | transloco }}
                  }
                </p>
                <div class="flex flex-wrap gap-2">
                  <button cp-button type="button" (click)="acceptSubscription(sub)">
                    {{ 'bookings.inbox.accept' | transloco }}
                  </button>
                  <button
                    cp-button
                    variant="secondary"
                    type="button"
                    (click)="rejectSubscription(sub)"
                  >
                    {{ 'bookings.inbox.reject' | transloco }}
                  </button>
                </div>
              </article>
            }
          </section>
        }
      } @else if (error()) {
        <cp-glass-card><cp-error-state [message]="error()" (retry)="load()" /></cp-glass-card>
      } @else {
        @for (row of [1, 2]; track row) {
          <cp-glass-card><cp-skeleton [lines]="3" /></cp-glass-card>
        }
      }
    </div>
  `,
})
export default class DriverInbox {
  private readonly api = inject(BookingsApi);
  private readonly actions = inject(BookingActions);
  private readonly transloco = inject(TranslocoService);
  private readonly language = inject(LanguageService);

  protected readonly emptyIcon = LucideInbox;
  protected readonly inbox = signal<Inbox | null>(null);
  protected readonly error = signal<string | null>(null);
  protected readonly total = computed(() => {
    const box = this.inbox();
    return box ? box.bookings.length + box.cancellations.length + box.subscriptions.length : 0;
  });

  constructor() {
    void this.load();
    inject(NotificationsStore)
      .incoming.pipe(takeUntilDestroyed())
      .subscribe((item) => {
        if (INBOX_KINDS.has(item.kind)) void this.load();
      });
  }

  protected async load(): Promise<void> {
    this.error.set(null);
    try {
      this.inbox.set(await this.api.inbox());
    } catch (error) {
      this.error.set(apiErrorMessage(this.transloco, error));
    }
  }

  private async after(result: unknown): Promise<void> {
    if (result) await this.load();
  }

  protected async accept(booking: Booking): Promise<void> {
    await this.after(await this.actions.accept(booking.id));
  }

  protected async reject(booking: Booking): Promise<void> {
    await this.after(await this.actions.reject(booking.id));
  }

  protected async resolve(requestId: string, accept: boolean): Promise<void> {
    await this.after(await this.actions.resolveCancellation(requestId, accept));
  }

  protected async acceptSubscription(sub: Subscription): Promise<void> {
    await this.after(await this.actions.acceptSubscription(sub.id));
  }

  protected async rejectSubscription(sub: Subscription): Promise<void> {
    await this.after(await this.actions.rejectSubscription(sub.id));
  }

  protected prefs(sub: Subscription): string[] {
    return BOOKING_PREFERENCE_KEYS.filter((key) => sub.preferences[key]);
  }

  protected date(value: string): string {
    const [y, m, d] = value.split('-').map(Number);
    return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString(this.language.current(), {
      day: 'numeric',
      month: 'short',
      timeZone: 'UTC',
    });
  }
}
