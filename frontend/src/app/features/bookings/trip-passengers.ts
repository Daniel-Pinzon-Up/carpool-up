import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  input,
  output,
  signal,
  untracked,
} from '@angular/core';
import { TranslocoPipe, TranslocoService } from '@jsverse/transloco';
import { LucideCircleCheck, LucideUsers } from '@lucide/angular';
import { DialogService } from '../../shared/ui/dialog.service';
import { ToastService } from '../../shared/ui/toast.service';
import { LifecycleApi } from '../trips/lifecycle.api';
import { TripStatus } from '../trips/trips.api';
import { apiErrorMessage } from '../../core/http/api-error-message';
import { GlassButton } from '../../shared/ui/glass-button';
import { Skeleton } from '../../shared/ui/skeleton';
import { BookingActions } from './booking-actions';
import { BookingCard } from './booking-card';
import { Booking, BookingsApi } from './bookings.api';

/** Pasajeros de un viaje propio: solicitudes por decidir, confirmados y el resto. */
@Component({
  selector: 'cp-trip-passengers',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [TranslocoPipe, BookingCard, GlassButton, Skeleton, LucideCircleCheck, LucideUsers],
  host: { class: 'block' },
  template: `
    <section aria-labelledby="passengers-title" class="flex flex-col gap-3">
      <h2 id="passengers-title" class="flex items-center gap-2 text-xl font-bold">
        <svg lucideUsers class="size-5" aria-hidden="true"></svg>
        {{ 'bookings.passengers.title' | transloco }}
      </h2>
      @if (error()) {
        <p role="alert" class="text-danger">{{ error() }}</p>
      } @else if (bookings() === null) {
        <cp-skeleton [lines]="3" />
      } @else {
        @if (pending().length) {
          <h3 class="font-semibold">{{ 'bookings.passengers.pending' | transloco }}</h3>
          @for (b of pending(); track b.id) {
            <cp-booking-card [booking]="b" view="driver">
              @if (b.status === 'requested') {
                <button cp-button type="button" (click)="accept(b)">
                  {{ 'bookings.inbox.accept' | transloco }}
                </button>
                <button cp-button variant="secondary" type="button" (click)="reject(b)">
                  {{ 'bookings.inbox.reject' | transloco }}
                </button>
              } @else if (b.cancellation; as c) {
                <button cp-button type="button" (click)="resolve(c.id, true)">
                  {{ 'bookings.inbox.acceptCancellation' | transloco }}
                </button>
                <button cp-button variant="secondary" type="button" (click)="resolve(c.id, false)">
                  {{ 'bookings.inbox.rejectCancellation' | transloco }}
                </button>
              }
            </cp-booking-card>
          }
        }
        <h3 class="font-semibold">{{ 'bookings.passengers.confirmed' | transloco }}</h3>
        @for (b of confirmed(); track b.id) {
          <cp-booking-card [booking]="b" view="driver">
            @if (b.boarded_at) {
              <span class="inline-flex items-center gap-1 text-sm font-semibold text-success">
                <svg lucideCircleCheck class="size-4" aria-hidden="true"></svg>
                {{ 'lifecycle.boarding.boarded' | transloco }}
              </span>
            } @else if (status() === 'in_progress' && b.status === 'accepted') {
              <button cp-button type="button" (click)="board(b)">
                {{ 'lifecycle.boarding.board' | transloco }}
              </button>
              <button cp-button variant="secondary" type="button" (click)="noShow(b)">
                {{ 'lifecycle.boarding.noShow' | transloco }}
              </button>
            }
          </cp-booking-card>
        } @empty {
          <p class="text-sm text-muted">{{ 'bookings.passengers.none' | transloco }}</p>
        }
        @if (others().length) {
          <details class="glass-1 !rounded-2xl p-4">
            <summary class="cursor-pointer font-semibold">
              {{ 'bookings.passengers.others' | transloco: { count: others().length } }}
            </summary>
            <div class="mt-3 flex flex-col gap-3">
              @for (b of others(); track b.id) {
                <cp-booking-card [booking]="b" view="driver" />
              }
            </div>
          </details>
        }
      }
    </section>
  `,
})
export class TripPassengers {
  readonly tripId = input.required<string>();
  /** En curso se marca el abordaje de cada pasajero. */
  readonly status = input<TripStatus>('scheduled');
  readonly changed = output<void>();

  private readonly api = inject(BookingsApi);
  private readonly actions = inject(BookingActions);
  private readonly transloco = inject(TranslocoService);
  private readonly lifecycle = inject(LifecycleApi);
  private readonly dialogs = inject(DialogService);
  private readonly toast = inject(ToastService);

  protected readonly bookings = signal<Booking[] | null>(null);
  protected readonly error = signal<string | null>(null);
  protected readonly pending = computed(() =>
    (this.bookings() ?? []).filter(
      (b) => b.status === 'requested' || b.status === 'cancel_requested',
    ),
  );
  protected readonly confirmed = computed(() =>
    (this.bookings() ?? []).filter((b) => b.status === 'accepted' || b.status === 'completed'),
  );
  protected readonly others = computed(() =>
    (this.bookings() ?? []).filter(
      (b) => !['requested', 'cancel_requested', 'accepted', 'completed'].includes(b.status),
    ),
  );

  constructor() {
    effect(() => {
      const id = this.tripId();
      untracked(() => void this.load(id));
    });
  }

  private async load(id: string): Promise<void> {
    try {
      this.bookings.set(await this.api.forTrip(id));
    } catch (error) {
      this.error.set(apiErrorMessage(this.transloco, error));
    }
  }

  private async after(result: unknown): Promise<void> {
    if (!result) return;
    await this.load(this.tripId());
    this.changed.emit();
  }

  protected async accept(booking: Booking): Promise<void> {
    await this.after(await this.actions.accept(booking.id));
  }

  protected async reject(booking: Booking): Promise<void> {
    await this.after(await this.actions.reject(booking.id));
  }

  protected async board(booking: Booking): Promise<void> {
    await this.boarding(() => this.lifecycle.boarded(booking.id), 'lifecycle.boarding.boardedDone');
  }

  protected async noShow(booking: Booking): Promise<void> {
    const ok = await this.dialogs.confirm({
      title: this.transloco.translate('lifecycle.boarding.noShowTitle'),
      message: this.transloco.translate('lifecycle.boarding.noShowMessage', {
        name: booking.passenger.full_name,
      }),
      confirmLabel: this.transloco.translate('lifecycle.boarding.noShow'),
      cancelLabel: this.transloco.translate('common.cancel'),
      danger: true,
    });
    if (ok)
      await this.boarding(() => this.lifecycle.noShow(booking.id), 'lifecycle.boarding.noShowDone');
  }

  private async boarding(action: () => Promise<unknown>, done: string): Promise<void> {
    try {
      await action();
      this.toast.show(this.transloco.translate(done), 'success');
      await this.after(true);
    } catch (error) {
      this.toast.show(apiErrorMessage(this.transloco, error), 'danger');
    }
  }

  protected async resolve(requestId: string, accept: boolean): Promise<void> {
    await this.after(await this.actions.resolveCancellation(requestId, accept));
  }
}
