import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { TranslocoPipe, TranslocoService } from '@jsverse/transloco';
import { LucideInbox, LucideRefreshCw } from '@icons';
import { apiErrorMessage } from '../../core/http/api-error-message';
import { NotificationsStore } from '../../core/notifications/notifications.store';
import { EmptyState } from '../../shared/ui/empty-state';
import { GlassButton } from '../../shared/ui/glass-button';
import { GlassCard } from '../../shared/ui/glass-card';
import { ErrorState } from '../../shared/ui/error-state';
import { Skeleton } from '../../shared/ui/skeleton';
import { BookingActions } from './booking-actions';
import { BookingCard } from './booking-card';
import { Booking, BookingsApi, Inbox } from './bookings.api';

/** Avisos que cambian lo que hay por decidir. */
const INBOX_KINDS = new Set(['booking_requested', 'booking_withdrawn', 'cancellation_requested']);

/**
 * Solicitudes del conductor: reservas y cancelaciones tardias que esperan su decision,
 * de la salida mas proxima a la mas lejana.
 */
@Component({
  selector: 'cp-driver-inbox',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    TranslocoPipe,
    BookingCard,
    EmptyState,
    ErrorState,
    GlassButton,
    GlassCard,
    Skeleton,
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
                @if (b.cancellation) {
                  <button cp-button type="button" (click)="resolve(b.id, true)">
                    {{ 'bookings.inbox.acceptCancellation' | transloco }}
                  </button>
                  <button
                    cp-button
                    variant="secondary"
                    type="button"
                    (click)="resolve(b.id, false)"
                  >
                    {{ 'bookings.inbox.rejectCancellation' | transloco }}
                  </button>
                }
              </cp-booking-card>
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

  protected readonly emptyIcon = LucideInbox;
  protected readonly inbox = signal<Inbox | null>(null);
  protected readonly error = signal<string | null>(null);
  protected readonly total = computed(() => {
    const box = this.inbox();
    return box ? box.bookings.length + box.cancellations.length : 0;
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

  protected async resolve(bookingId: string, accept: boolean): Promise<void> {
    await this.after(await this.actions.resolveCancellation(bookingId, accept));
  }
}
