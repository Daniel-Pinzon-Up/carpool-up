import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { TranslocoPipe } from '@jsverse/transloco';
import {
  LucideArrowRight,
  LucideCarFront,
  LucideMapPin,
  LucideRepeat,
  LucideUsers,
  LucideWallet,
} from '@icons';
import { LanguageService } from '../../core/i18n/language.service';
import { formatCop } from '../../shared/map/routing.api';
import { Avatar } from '../../shared/ui/avatar';
import { StatusBadge } from '../../shared/ui/status-badge';
import { formatDeparture, formatTime } from '../trips/trip-status';
import { BOOKING_PREFERENCE_KEYS, BOOKING_STATUS_TONE, Booking } from './bookings.api';

/**
 * Una reserva. Para el pasajero muestra conductor, vehiculo (placa al ser aceptado) y datos
 * de pago; para el conductor, el pasajero con su recogida y preferencias. Las acciones van
 * en el contenido proyectado.
 */
@Component({
  selector: 'cp-booking-card',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    RouterLink,
    TranslocoPipe,
    Avatar,
    StatusBadge,
    LucideArrowRight,
    LucideCarFront,
    LucideMapPin,
    LucideRepeat,
    LucideUsers,
    LucideWallet,
  ],
  host: { class: 'block' },
  template: `
    <article class="glass-1 !rounded-2xl flex flex-col gap-3 p-4">
      <div class="flex flex-wrap items-start justify-between gap-2">
        <div class="min-w-0">
          <a
            [routerLink]="['/viajes', b().trip.id]"
            class="font-semibold underline-offset-4 hover:underline"
          >
            {{ when() }}
          </a>
          <p class="flex min-w-0 items-center gap-2 text-sm">
            <span class="truncate">{{ b().trip.origin }}</span>
            <svg lucideArrowRight class="size-4 shrink-0 text-muted" aria-hidden="true"></svg>
            <span class="sr-only">{{ 'trips.to' | transloco }}</span>
            <span class="truncate">{{ b().trip.destination }}</span>
          </p>
        </div>
        <span class="flex flex-wrap gap-1.5">
          @if (b().trip.status === 'in_progress') {
            <cp-status-badge variant="pending">{{
              'trips.status.in_progress' | transloco
            }}</cp-status-badge>
          }
          <cp-status-badge [variant]="tone()">{{
            'bookings.status.' + b().status | transloco
          }}</cp-status-badge>
        </span>
      </div>

      @if (view() === 'driver') {
        <div class="flex items-center gap-3">
          <cp-avatar [name]="b().passenger.full_name" size="sm" />
          <div class="min-w-0">
            <p class="truncate font-semibold">{{ b().passenger.full_name }}</p>
            <p class="truncate text-xs text-muted">
              @if (b().passenger.program) {
                {{ b().passenger.program }} ·
              }
              @if (b().passenger.rating !== null) {
                {{ 'bookings.card.rating' | transloco: { rating: b().passenger.rating } }} ·
              }
              {{ 'bookings.card.trips' | transloco: { count: b().passenger.trips_as_passenger } }}
            </p>
          </div>
        </div>
      }

      <dl class="grid gap-2 text-sm sm:grid-cols-2">
        <div class="flex gap-2">
          <svg lucideMapPin class="mt-0.5 size-4 shrink-0 text-accent" aria-hidden="true"></svg>
          <div>
            <dt class="text-muted">{{ 'search.card.pickup' | transloco }}</dt>
            <dd class="font-medium">
              {{ b().pickup.name || ('search.card.onRoute' | transloco) }} ·
              {{ time(b().pickup.eta) }}
            </dd>
          </div>
        </div>
        <div class="flex gap-2">
          <svg lucideMapPin class="mt-0.5 size-4 shrink-0 text-danger" aria-hidden="true"></svg>
          <div>
            <dt class="text-muted">{{ 'search.card.dropoff' | transloco }}</dt>
            <dd class="font-medium">
              {{ b().dropoff.name || ('search.card.onRoute' | transloco) }} ·
              {{ time(b().dropoff.eta) }}
            </dd>
          </div>
        </div>
      </dl>

      <p class="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted">
        <span class="inline-flex items-center gap-1">
          <svg lucideUsers class="size-4" aria-hidden="true"></svg>
          {{ 'trips.seats' | transloco: { count: b().seats } }}
        </span>
        <span>{{ money() }}</span>
        @if (b().subscription_id) {
          <span class="inline-flex items-center gap-1">
            <svg lucideRepeat class="size-4" aria-hidden="true"></svg>
            {{ 'bookings.card.fromSubscription' | transloco }}
          </span>
        }
        @if (view() === 'passenger') {
          <span class="inline-flex items-center gap-1">
            <svg lucideCarFront class="size-4" aria-hidden="true"></svg>
            {{ b().trip.driver.full_name }} · {{ b().trip.vehicle.brand }}
            {{ b().trip.vehicle.model }}
            @if (b().trip.vehicle.plate) {
              · <span class="font-semibold text-text">{{ b().trip.vehicle.plate }}</span>
            }
          </span>
        }
      </p>

      @if (preferences().length) {
        <ul class="flex flex-wrap gap-1.5" [attr.aria-label]="'search.preferences' | transloco">
          @for (key of preferences(); track key) {
            <li class="rounded-full bg-glass px-2.5 py-1 text-xs font-medium">
              {{ 'search.prefs.' + key | transloco }}
            </li>
          }
        </ul>
      }
      @if (b().payment_note) {
        <p class="flex gap-2 rounded-xl bg-accent/10 p-3 text-sm">
          <svg lucideWallet class="size-4 shrink-0 text-accent" aria-hidden="true"></svg>
          <span>
            <span class="font-semibold">{{ 'bookings.card.paymentNote' | transloco }}:</span>
            {{ b().payment_note }}
          </span>
        </p>
      }
      @if (b().cancellation; as c) {
        @if (c.status === 'pending') {
          <p class="rounded-xl bg-warning/10 p-3 text-sm">
            <span class="font-semibold">{{ 'bookings.card.cancelReason' | transloco }}:</span>
            {{ c.reason }}
          </p>
        }
      }
      @if (b().cancel_reason && b().status !== 'cancel_requested') {
        <p class="text-sm text-muted">
          <span class="font-semibold">{{ 'trips.cancelReason' | transloco }}:</span>
          {{ b().cancel_reason }}
        </p>
      }
      @if (b().penalty_free && b().status === 'accepted' && view() === 'passenger') {
        <p class="text-sm text-muted">{{ 'bookings.card.tripChanged' | transloco }}</p>
      }
      <div class="flex flex-wrap gap-2 empty:hidden"><ng-content /></div>
    </article>
  `,
})
export class BookingCard {
  readonly booking = input.required<Booking>();
  readonly view = input<'passenger' | 'driver'>('passenger');
  private readonly language = inject(LanguageService);

  protected readonly b = this.booking;
  protected readonly tone = computed(() => BOOKING_STATUS_TONE[this.b().status]);
  protected readonly when = computed(() =>
    formatDeparture(this.b().pickup.eta, this.language.current()),
  );
  protected readonly money = computed(() => formatCop(this.b().amount, this.language.current()));
  protected readonly preferences = computed(() =>
    BOOKING_PREFERENCE_KEYS.filter((key) => this.b().preferences[key]),
  );

  protected time(iso: string): string {
    return formatTime(iso, this.language.current());
  }
}
