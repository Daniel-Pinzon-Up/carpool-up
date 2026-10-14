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
import { toSignal } from '@angular/core/rxjs-interop';
import { FormControl, FormGroup, ReactiveFormsModule } from '@angular/forms';
import { TranslocoPipe, TranslocoService } from '@jsverse/transloco';
import { LucideCircleAlert, LucideTicket } from '@icons';
import { AuthService } from '../../core/auth/auth.service';
import { apiErrorMessage } from '../../core/http/api-error-message';
import { LOCALE } from '../../core/i18n/locale';
import { PlaceValue } from '../../shared/map/places.api';
import { formatCop } from '../../shared/map/routing.api';
import { GlassButton } from '../../shared/ui/glass-button';
import { GlassCard } from '../../shared/ui/glass-card';
import { GlassChip } from '../../shared/ui/glass-chip';
import { GlassSelect, SelectOption } from '../../shared/ui/glass-select';
import { SeatPicker } from '../../shared/ui/seat-picker';
import { StatusBadge } from '../../shared/ui/status-badge';
import { ToastService } from '../../shared/ui/toast.service';
import { formatTime } from '../trips/trip-status';
import { Trip } from '../trips/trips.api';
import { BookingActions } from './booking-actions';
import {
  ACTIVE_BOOKING,
  BOOKING_PREFERENCE_KEYS,
  BOOKING_STATUS_TONE,
  BookingPreferences,
  BookingsApi,
  PointsRequest,
  noPreferences,
} from './bookings.api';

/** Lugares que el pasajero busco; llegan desde la busqueda en el estado de navegacion. */
export interface SearchedPlaces {
  pickup: PlaceValue;
  dropoff: PlaceValue;
}

/** Lo que el pasajero hace con un viaje: solicitar cupo o ver y cancelar su reserva. */
@Component({
  selector: 'cp-booking-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    ReactiveFormsModule,
    TranslocoPipe,
    GlassButton,
    GlassCard,
    GlassChip,
    GlassSelect,
    SeatPicker,
    StatusBadge,
    LucideCircleAlert,
    LucideTicket,
  ],
  host: { class: 'block' },
  template: `
    <cp-glass-card [level]="2">
      <h2 class="mb-3 flex items-center gap-2 text-lg font-bold">
        <svg lucideTicket class="size-5" aria-hidden="true"></svg>
        {{ 'bookings.panel.title' | transloco }}
      </h2>

      @if (booking(); as b) {
        <div class="flex flex-col gap-3">
          <cp-status-badge class="self-start" [variant]="tone()">{{
            'bookings.status.' + b.status | transloco
          }}</cp-status-badge>
          <p class="text-sm">{{ 'bookings.panel.hint.' + b.status | transloco }}</p>
          <dl class="grid grid-cols-2 gap-2 text-sm">
            <div>
              <dt class="text-muted">{{ 'search.card.pickup' | transloco }}</dt>
              <dd class="font-semibold">
                {{ b.pickup_name || ('search.card.onRoute' | transloco) }} ·
                {{ time(b.pickup_eta) }}
              </dd>
            </div>
            <div>
              <dt class="text-muted">{{ 'search.card.dropoff' | transloco }}</dt>
              <dd class="font-semibold">
                {{ b.dropoff_name || ('search.card.onRoute' | transloco) }} ·
                {{ time(b.dropoff_eta) }}
              </dd>
            </div>
          </dl>
          @if (b.status === 'requested' || b.status === 'accepted') {
            <button cp-button variant="danger" type="button" class="self-start" (click)="cancel()">
              {{ 'bookings.cancel.action' | transloco }}
            </button>
          }
        </div>
      } @else if (blockedReason(); as reason) {
        <p class="flex gap-2 text-sm text-muted">
          <svg lucideCircleAlert class="size-5 shrink-0" aria-hidden="true"></svg>
          {{ reason | transloco }}
        </p>
      } @else {
        <form [formGroup]="form" class="flex flex-col gap-4" (ngSubmit)="submit()" novalidate>
          <cp-glass-select
            formControlName="pickup"
            [label]="'search.card.pickup' | transloco"
            [options]="pickupOptions()"
          />
          <cp-glass-select
            formControlName="dropoff"
            [label]="'search.card.dropoff' | transloco"
            [options]="dropoffOptions()"
          />
          <cp-seat-picker
            formControlName="seats"
            [label]="'search.seats' | transloco"
            [min]="1"
            [max]="maxSeats()"
          />
          <fieldset>
            <legend class="mb-2 text-sm font-medium">{{ 'search.preferences' | transloco }}</legend>
            <div class="flex flex-wrap gap-2">
              @for (key of preferenceKeys; track key) {
                <cp-glass-chip [selected]="prefs()[key]" (selectedChange)="setPref(key, $event)">
                  {{ 'search.prefs.' + key | transloco }}
                </cp-glass-chip>
              }
            </div>
          </fieldset>
          <p class="text-sm">
            {{ 'bookings.panel.total' | transloco: { amount: total() } }}
            <span class="block text-xs text-muted">{{
              'bookings.panel.contribution' | transloco
            }}</span>
          </p>
          @if (error()) {
            <p role="alert" class="flex gap-2 text-sm text-danger">
              <svg lucideCircleAlert class="size-5 shrink-0" aria-hidden="true"></svg>
              {{ error() }}
            </p>
          }
          @if (full()) {
            <p class="text-sm text-muted">{{ 'bookings.panel.full' | transloco }}</p>
          } @else {
            <button cp-button type="submit" [disabled]="busy()">
              {{ 'bookings.panel.request' | transloco }}
            </button>
            <p class="text-xs text-muted">{{ 'bookings.panel.approvalHint' | transloco }}</p>
          }
        </form>
      }
    </cp-glass-card>
  `,
})
export class BookingPanel {
  readonly trip = input.required<Trip>();
  readonly searched = input<SearchedPlaces | null>(null);
  /** La reserva de quien consulta cambio: hay que recargar el viaje. */
  readonly changed = output<void>();

  private readonly api = inject(BookingsApi);
  private readonly actions = inject(BookingActions);
  private readonly auth = inject(AuthService);
  private readonly toast = inject(ToastService);
  private readonly transloco = inject(TranslocoService);

  protected readonly preferenceKeys = BOOKING_PREFERENCE_KEYS;
  protected readonly form = new FormGroup({
    pickup: new FormControl('', { nonNullable: true }),
    dropoff: new FormControl('', { nonNullable: true }),
    seats: new FormControl(1, { nonNullable: true }),
  });
  protected readonly prefs = signal<BookingPreferences>(noPreferences());
  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);
  private readonly seats = toSignal(this.form.controls.seats.valueChanges, { initialValue: 1 });

  protected readonly booking = computed(() => {
    const mine = this.trip().my_booking;
    return mine && ACTIVE_BOOKING.includes(mine.status) ? mine : null;
  });
  protected readonly tone = computed(
    () => BOOKING_STATUS_TONE[this.booking()?.status ?? 'requested'],
  );
  protected readonly maxSeats = computed(() => Math.max(1, Math.min(4, this.trip().seats_total)));
  protected readonly full = computed(() => this.trip().seats_available < this.seats());
  protected readonly total = computed(() =>
    formatCop(this.seats() * this.trip().price_per_seat, LOCALE),
  );

  /** Por que no se puede pedir cupo, si es el caso. */
  protected readonly blockedReason = computed(() => {
    const trip = this.trip();
    if (trip.status !== 'scheduled' || new Date(trip.departs_at) <= new Date()) {
      return 'bookings.panel.closed';
    }
    const womenOnly = trip.rules.some((rule) => rule.kind === 'women_only');
    if (womenOnly && this.auth.user()?.sex !== 'female') return 'bookings.panel.womenOnly';
    return null;
  });

  /** Paradas del viaje y, si llego desde la busqueda, los lugares que el pasajero eligio. */
  private readonly places = computed(() => {
    const stops = this.trip().stops.map((stop) => ({
      id: stop.place_id,
      label: stop.name,
      position: stop.position,
    }));
    const searched = this.searched();
    if (!searched) return { stops, pickup: [], dropoff: [] };
    const own = (place: PlaceValue) =>
      stops.some((stop) => stop.id === place.place_id)
        ? []
        : [
            {
              id: place.place_id,
              label: this.transloco.translate('bookings.panel.myPoint', { name: place.name }),
              position: -1,
            },
          ];
    return { stops, pickup: own(searched.pickup), dropoff: own(searched.dropoff) };
  });
  protected readonly pickupOptions = computed<SelectOption[]>(() => {
    const { stops, pickup } = this.places();
    return [...pickup, ...stops.slice(0, -1)].map((p) => ({ value: p.id, label: p.label }));
  });
  protected readonly dropoffOptions = computed<SelectOption[]>(() => {
    const { stops, dropoff } = this.places();
    return [...dropoff, ...stops.slice(1)].map((p) => ({ value: p.id, label: p.label }));
  });

  constructor() {
    effect(() => {
      const trip = this.trip();
      const searched = this.searched();
      untracked(() =>
        this.form.patchValue({
          pickup: searched?.pickup.place_id ?? trip.stops[0]?.place_id ?? '',
          dropoff: searched?.dropoff.place_id ?? trip.stops.at(-1)?.place_id ?? '',
        }),
      );
    });
  }

  protected time(iso: string): string {
    return iso ? formatTime(iso, LOCALE) : '';
  }

  protected setPref(key: keyof BookingPreferences, on: boolean): void {
    this.prefs.update((prefs) => ({ ...prefs, [key]: on }));
  }

  private request(): PointsRequest {
    const { pickup, dropoff, seats } = this.form.getRawValue();
    return {
      seats,
      pickup_place_id: pickup,
      dropoff_place_id: dropoff,
      preferences: this.prefs(),
    };
  }

  protected async submit(): Promise<void> {
    this.error.set(null);
    this.busy.set(true);
    try {
      await this.api.request(this.trip().id, this.request());
      this.toast.show(this.transloco.translate('bookings.panel.sent'), 'success');
      this.changed.emit();
    } catch (error) {
      this.error.set(apiErrorMessage(this.transloco, error));
    } finally {
      this.busy.set(false);
    }
  }

  protected async cancel(): Promise<void> {
    const booking = this.booking();
    if (!booking) return;
    if (await this.actions.cancel(booking.id)) this.changed.emit();
  }
}
