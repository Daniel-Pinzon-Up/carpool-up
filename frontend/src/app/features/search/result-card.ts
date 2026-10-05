import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { TranslocoPipe } from '@jsverse/transloco';
import {
  LucideBike,
  LucideCarFront,
  LucideFootprints,
  LucideRepeat,
  LucideStar,
  LucideUsers,
} from '@lucide/angular';
import { LanguageService } from '../../core/i18n/language.service';
import { formatCop } from '../../shared/map/routing.api';
import { Avatar } from '../../shared/ui/avatar';
import { formatTime } from '../trips/trip-status';
import { SearchedPlaces } from '../bookings/booking-panel';
import { SearchResult } from './search.api';

/** Resultado de busqueda: hora y lugar de recogida, conductor, vehiculo, aporte y cupos. */
@Component({
  selector: 'cp-result-card',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    RouterLink,
    TranslocoPipe,
    Avatar,
    LucideBike,
    LucideCarFront,
    LucideFootprints,
    LucideRepeat,
    LucideStar,
    LucideUsers,
  ],
  host: { class: 'block' },
  template: `
    <a
      [routerLink]="['/viajes', result().trip_id]"
      [state]="{ match: result(), places: places() }"
      class="glass-1 !rounded-2xl flex flex-col gap-3 p-4 transition hover:bg-glass-strong focus-visible:outline-2 focus-visible:outline-primary"
    >
      <div class="flex items-start justify-between gap-3">
        <div class="min-w-0">
          <p class="text-2xl font-bold">
            {{ time(result().pickup.eta) }}
            <span class="text-base font-medium text-muted">→ {{ time(result().dropoff.eta) }}</span>
          </p>
          <p class="truncate text-sm">
            <span class="text-muted">{{ 'search.card.pickup' | transloco }}:</span>
            {{ result().pickup.name || ('search.card.onRoute' | transloco) }}
          </p>
          <p class="flex items-center gap-1 text-xs text-muted">
            <svg lucideFootprints class="size-3.5" aria-hidden="true"></svg>
            {{ 'search.card.walk' | transloco: { meters: result().pickup.walk_m } }}
          </p>
        </div>
        <div class="shrink-0 text-right">
          <p class="text-xl font-bold">{{ money() }}</p>
          <p class="flex items-center justify-end gap-1 text-sm text-muted">
            <svg lucideUsers class="size-4" aria-hidden="true"></svg>
            {{ 'search.card.seats' | transloco: { count: result().seats_available } }}
          </p>
        </div>
      </div>

      <div
        class="flex flex-wrap items-center justify-between gap-3 border-t border-glass-border pt-3"
      >
        <div class="flex min-w-0 items-center gap-3">
          <cp-avatar [name]="result().driver.full_name" size="sm" />
          <div class="min-w-0">
            <p class="truncate font-semibold">{{ result().driver.full_name }}</p>
            <p class="flex items-center gap-1 text-xs text-muted">
              @if (result().driver.rating !== null) {
                <svg lucideStar class="size-3.5 text-warning" aria-hidden="true"></svg>
                {{ 'search.card.rating' | transloco: { rating: result().driver.rating } }} ·
              } @else {
                {{ 'search.card.newDriver' | transloco }} ·
              }
              {{ 'search.card.trips' | transloco: { count: result().driver.trips_as_driver } }}
            </p>
          </div>
        </div>
        <p class="flex items-center gap-1.5 text-sm text-muted">
          @if (result().vehicle.type === 'motorcycle') {
            <svg lucideBike class="size-4" aria-hidden="true"></svg>
          } @else {
            <svg lucideCarFront class="size-4" aria-hidden="true"></svg>
          }
          {{ result().vehicle.brand }} {{ result().vehicle.model }}, {{ result().vehicle.color }}
        </p>
      </div>

      @if (result().series_id || result().rules.length) {
        <ul class="flex flex-wrap gap-1.5" [attr.aria-label]="'publish.steps.rules' | transloco">
          @if (result().series_id) {
            <li
              class="inline-flex items-center gap-1 rounded-full bg-primary/15 px-2.5 py-1 text-xs font-medium text-primary"
            >
              <svg lucideRepeat class="size-3.5" aria-hidden="true"></svg>
              {{ 'search.card.series' | transloco }}
            </li>
          }
          @for (rule of result().rules; track rule.kind) {
            <li class="rounded-full bg-glass px-2.5 py-1 text-xs font-medium">
              @if (rule.kind === 'custom') {
                {{ rule.value }}
              } @else if (rule.kind === 'women_only') {
                {{ 'publish.rules.women_only' | transloco }}
              } @else {
                {{ 'publish.rules.' + rule.kind | transloco }}:
                {{ 'publish.rules.choice.' + rule.value | transloco }}
              }
            </li>
          }
        </ul>
      }
    </a>
  `,
})
export class ResultCard {
  readonly result = input.required<SearchResult>();
  /** Origen y destino que eligio el pasajero, para proponerlos al reservar. */
  readonly places = input<SearchedPlaces | null>(null);
  private readonly language = inject(LanguageService);

  protected readonly money = computed(() =>
    formatCop(this.result().price_per_seat, this.language.current()),
  );

  protected time(iso: string): string {
    return formatTime(iso, this.language.current());
  }
}
