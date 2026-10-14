import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { TranslocoPipe } from '@jsverse/transloco';
import { LucideArrowRight, LucideBellDot, LucideUsers } from '@icons';
import { LOCALE } from '../../core/i18n/locale';
import { formatCop } from '../../shared/map/routing.api';
import { StatusBadge } from '../../shared/ui/status-badge';
import { TRIP_STATUS_TONE, formatDeparture } from './trip-status';
import { TripSummary } from './trips.api';

/** Tarjeta enlazada de un viaje: fecha, trayecto, estado, puestos y aporte. */
@Component({
  selector: 'cp-trip-card',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, TranslocoPipe, StatusBadge, LucideArrowRight, LucideBellDot, LucideUsers],
  host: { class: 'block' },
  template: `
    <a
      [routerLink]="['/viajes', trip().id]"
      class="glass-1 !rounded-2xl flex flex-col gap-2 p-4 transition hover:bg-glass-strong focus-visible:outline-2 focus-visible:outline-primary"
    >
      <div class="flex flex-wrap items-center justify-between gap-2">
        <span class="font-semibold">{{ when() }}</span>
        <cp-status-badge [variant]="tone()">{{
          'trips.status.' + trip().status | transloco
        }}</cp-status-badge>
      </div>
      <p class="flex min-w-0 items-center gap-2">
        <span class="truncate">{{ trip().origin }}</span>
        <svg lucideArrowRight class="size-4 shrink-0 text-muted" aria-hidden="true"></svg>
        <span class="sr-only">{{ 'trips.to' | transloco }}</span>
        <span class="truncate">{{ trip().destination }}</span>
      </p>
      <p class="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted">
        <span class="inline-flex items-center gap-1">
          <svg lucideUsers class="size-4" aria-hidden="true"></svg>
          {{
            'trips.seatsLeft'
              | transloco: { free: trip().seats_available, total: trip().seats_total }
          }}
        </span>
        <span>{{ money() }}</span>
        @if (trip().stop_count) {
          <span>{{ 'trips.stops' | transloco: { count: trip().stop_count } }}</span>
        }
        @if (trip().pending_requests) {
          <span class="inline-flex items-center gap-1 font-semibold text-accent">
            <svg lucideBellDot class="size-4" aria-hidden="true"></svg>
            {{ 'trips.pendingRequests' | transloco: { count: trip().pending_requests } }}
          </span>
        }
      </p>
    </a>
  `,
})
export class TripCard {
  readonly trip = input.required<TripSummary>();

  protected readonly tone = computed(() => TRIP_STATUS_TONE[this.trip().status]);
  protected readonly when = computed(() => formatDeparture(this.trip().departs_at, LOCALE));
  protected readonly money = computed(() => formatCop(this.trip().price_per_seat, LOCALE));
}
