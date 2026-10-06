import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { TranslocoPipe } from '@jsverse/transloco';
import { LucideArrowRight, LucideReceipt, LucideStar, LucideUsers } from '@lucide/angular';
import { LanguageService } from '../../core/i18n/language.service';
import { formatCop } from '../../shared/map/routing.api';
import { GlassButton } from '../../shared/ui/glass-button';
import { StatusBadge } from '../../shared/ui/status-badge';
import { BOOKING_STATUS_TONE } from '../bookings/bookings.api';
import { TRIP_STATUS_TONE, formatDeparture } from '../trips/trip-status';
import { DriverHistoryEntry, PassengerHistoryEntry, RatingState } from './ratings.api';

/** Estado de la calificacion de un viaje pasado, con accion si aun se puede calificar. */
@Component({
  selector: 'cp-rating-state',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, TranslocoPipe, GlassButton, LucideStar],
  host: { class: 'contents' },
  template: `
    @if (state() === 'pending') {
      <a cp-button variant="secondary" [routerLink]="['/calificar', tripId()]">
        <svg lucideStar class="size-4" aria-hidden="true"></svg>
        {{ label() }}
      </a>
    } @else if (state() === 'done') {
      <span class="inline-flex items-center gap-1 text-sm text-muted">
        <svg lucideStar class="size-4 text-warning" aria-hidden="true"></svg>
        {{ 'ratings.state.done' | transloco }}
      </span>
    } @else if (state() === 'closed') {
      <span class="text-sm text-muted">{{ 'ratings.state.closed' | transloco }}</span>
    }
  `,
})
export class RatingStateAction {
  readonly state = input.required<RatingState>();
  readonly tripId = input.required<string>();
  readonly label = input.required<string>();
}

/** Viaje pasado del pasajero: estado, ticket y calificacion. */
@Component({
  selector: 'cp-passenger-history-item',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    RouterLink,
    TranslocoPipe,
    RatingStateAction,
    StatusBadge,
    LucideArrowRight,
    LucideReceipt,
  ],
  host: { class: 'block' },
  template: `
    <article class="glass-1 !rounded-2xl flex flex-col gap-2 p-4">
      <div class="flex flex-wrap items-start justify-between gap-2">
        <a
          [routerLink]="['/viajes', e().trip_id]"
          class="font-semibold underline-offset-4 hover:underline"
        >
          {{ when() }}
        </a>
        <cp-status-badge [variant]="tone()">{{
          'bookings.status.' + e().booking_status | transloco
        }}</cp-status-badge>
      </div>
      <p class="flex min-w-0 items-center gap-2 text-sm">
        <span class="truncate">{{ e().origin }}</span>
        <svg lucideArrowRight class="size-4 shrink-0 text-muted" aria-hidden="true"></svg>
        <span class="sr-only">{{ 'trips.to' | transloco }}</span>
        <span class="truncate">{{ e().destination }}</span>
        <span class="text-muted">· {{ e().driver_name }}</span>
      </p>
      @if (e().ticket_code) {
        <p class="flex items-center gap-2 text-sm">
          <svg lucideReceipt class="size-4 shrink-0 text-primary" aria-hidden="true"></svg>
          <span class="font-mono">{{ e().ticket_code }}</span> · {{ money() }} ·
          {{
            (e().paid_confirmed ? 'lifecycle.tickets.confirmed' : 'lifecycle.tickets.pending')
              | transloco
          }}
        </p>
      }
      <div class="flex flex-wrap gap-2 empty:hidden">
        <cp-rating-state
          [state]="e().rating"
          [tripId]="e().trip_id"
          [label]="'ratings.rateDriver' | transloco"
        />
      </div>
    </article>
  `,
})
export class PassengerHistoryItem {
  readonly entry = input.required<PassengerHistoryEntry>();
  private readonly language = inject(LanguageService);
  protected readonly e = this.entry;
  protected readonly tone = computed(() => BOOKING_STATUS_TONE[this.e().booking_status]);
  protected readonly when = computed(() =>
    formatDeparture(this.e().departs_at, this.language.current()),
  );
  protected readonly money = computed(() =>
    formatCop(this.e().amount ?? 0, this.language.current()),
  );
}

/** Viaje pasado del conductor: estado, pasajeros, aportes y calificaciones pendientes. */
@Component({
  selector: 'cp-driver-history-item',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    RouterLink,
    TranslocoPipe,
    RatingStateAction,
    StatusBadge,
    LucideArrowRight,
    LucideUsers,
  ],
  host: { class: 'block' },
  template: `
    <article class="glass-1 !rounded-2xl flex flex-col gap-2 p-4">
      <div class="flex flex-wrap items-start justify-between gap-2">
        <a
          [routerLink]="['/viajes', e().trip_id]"
          class="font-semibold underline-offset-4 hover:underline"
        >
          {{ when() }}
        </a>
        <cp-status-badge [variant]="tone()">{{
          'trips.status.' + e().trip_status | transloco
        }}</cp-status-badge>
      </div>
      <p class="flex min-w-0 items-center gap-2 text-sm">
        <span class="truncate">{{ e().origin }}</span>
        <svg lucideArrowRight class="size-4 shrink-0 text-muted" aria-hidden="true"></svg>
        <span class="sr-only">{{ 'trips.to' | transloco }}</span>
        <span class="truncate">{{ e().destination }}</span>
      </p>
      @if (e().trip_status === 'completed') {
        <p class="flex items-center gap-2 text-sm text-muted">
          <svg lucideUsers class="size-4 shrink-0" aria-hidden="true"></svg>
          {{
            'stats.historyLine'
              | transloco: { passengers: e().passengers, total: e().seats_total, amount: money() }
          }}
        </p>
      }
      <div class="flex flex-wrap gap-2 empty:hidden">
        <cp-rating-state
          [state]="e().rating"
          [tripId]="e().trip_id"
          [label]="'ratings.ratePassengers' | transloco: { count: e().to_rate }"
        />
      </div>
    </article>
  `,
})
export class DriverHistoryItem {
  readonly entry = input.required<DriverHistoryEntry>();
  private readonly language = inject(LanguageService);
  protected readonly e = this.entry;
  protected readonly tone = computed(() => TRIP_STATUS_TONE[this.e().trip_status]);
  protected readonly when = computed(() =>
    formatDeparture(this.e().departs_at, this.language.current()),
  );
  protected readonly money = computed(() =>
    formatCop(this.e().contributions, this.language.current()),
  );
}
