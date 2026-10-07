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
import {
  LucideBan,
  LucideCalendarCheck,
  LucideCircleAlert,
  LucideCircleCheck,
  LucideRepeat,
  LucideUsers,
} from '@icons';
import { AuthService } from '../../core/auth/auth.service';
import { apiErrorMessage } from '../../core/http/api-error-message';
import { LanguageService } from '../../core/i18n/language.service';
import { GlassButton } from '../../shared/ui/glass-button';
import { GlassCard } from '../../shared/ui/glass-card';
import { GlassChip } from '../../shared/ui/glass-chip';
import { GlassSelect, SelectOption } from '../../shared/ui/glass-select';
import { SeatPicker } from '../../shared/ui/seat-picker';
import { Skeleton } from '../../shared/ui/skeleton';
import { StatusBadge } from '../../shared/ui/status-badge';
import { ToastService } from '../../shared/ui/toast.service';
import { Series, addDays } from '../trips/trips.api';
import { BookingActions } from './booking-actions';
import {
  AvailabilityDay,
  BOOKING_PREFERENCE_KEYS,
  BookingPreferences,
  BookingsApi,
  SUBSCRIPTION_STATUS_TONE,
  SeriesAvailability,
  SubscriptionOption,
  noPreferences,
} from './bookings.api';

/** Ultima fecha que cubre una opcion de suscripcion, sin pasar del final de la serie. */
export function subscriptionEnd(
  start: string,
  option: SubscriptionOption,
  seriesEnd: string,
): string {
  if (option === 'series') return seriesEnd;
  const end = addDays(start, option - 1);
  return end < seriesEnd ? end : seriesEnd;
}

/**
 * Unirse a una serie por 8 dias, 15 dias o toda la serie. Muestra cada fecha del rango:
 * las de pico y placa aparecen bloqueadas y las llenas se omiten al aprobar.
 */
@Component({
  selector: 'cp-subscribe-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    ReactiveFormsModule,
    TranslocoPipe,
    GlassButton,
    GlassCard,
    GlassChip,
    GlassSelect,
    SeatPicker,
    Skeleton,
    StatusBadge,
    LucideBan,
    LucideCalendarCheck,
    LucideCircleAlert,
    LucideCircleCheck,
    LucideRepeat,
    LucideUsers,
  ],
  host: { class: 'block' },
  template: `
    <cp-glass-card [level]="2">
      <h2 class="mb-3 flex items-center gap-2 text-lg font-bold">
        <svg lucideRepeat class="size-5" aria-hidden="true"></svg>
        {{ 'bookings.subscription.title' | transloco }}
      </h2>

      @if (mine(); as sub) {
        <div class="flex flex-col gap-3">
          <cp-status-badge class="self-start" [variant]="subTone()">{{
            'bookings.subscriptionStatus.' + sub.status | transloco
          }}</cp-status-badge>
          <p class="text-sm">
            {{
              'bookings.subscription.range'
                | transloco: { start: date(sub.from_date), end: date(sub.to_date) }
            }}
          </p>
          <p class="text-sm text-muted">
            {{ 'bookings.subscription.hint.' + sub.status | transloco }}
          </p>
          <button cp-button variant="danger" type="button" class="self-start" (click)="cancel()">
            {{ 'bookings.subscription.cancel' | transloco }}
          </button>
        </div>
      } @else if (blocked(); as reason) {
        <p class="flex gap-2 text-sm text-muted">
          <svg lucideCircleAlert class="size-5 shrink-0" aria-hidden="true"></svg>
          {{ reason | transloco }}
        </p>
      } @else if (availability(); as a) {
        <form [formGroup]="form" class="flex flex-col gap-4" (ngSubmit)="submit()" novalidate>
          <div class="grid gap-4 sm:grid-cols-2">
            <cp-glass-select
              formControlName="option"
              [label]="'bookings.subscription.option' | transloco"
              [options]="optionChoices()"
            />
            <cp-glass-select
              formControlName="start"
              [label]="'bookings.subscription.start' | transloco"
              [options]="startChoices()"
            />
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
          </div>
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

          <section aria-labelledby="sub-days">
            <h3 id="sub-days" class="mb-2 text-sm font-medium">
              {{ 'bookings.subscription.days' | transloco }}
            </h3>
            <ul class="flex flex-wrap gap-2">
              @for (day of rangeDays(); track day.trip_id) {
                <li
                  class="inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium"
                  [class]="dayClass(day)"
                >
                  @if (day.status === 'cancelled_pico_placa') {
                    <svg lucideBan class="size-3.5" aria-hidden="true"></svg>
                  } @else if (day.bookable) {
                    <svg lucideCircleCheck class="size-3.5" aria-hidden="true"></svg>
                  } @else {
                    <svg lucideUsers class="size-3.5" aria-hidden="true"></svg>
                  }
                  {{ date(day.date) }}
                  <span class="sr-only">{{ dayState(day) | transloco }}</span>
                </li>
              } @empty {
                <li class="text-sm text-muted">{{ 'bookings.subscription.noDays' | transloco }}</li>
              }
            </ul>
            <p class="mt-2 text-xs text-muted">{{ 'bookings.subscription.legend' | transloco }}</p>
          </section>

          @if (error()) {
            <p role="alert" class="flex gap-2 text-sm text-danger">
              <svg lucideCircleAlert class="size-5 shrink-0" aria-hidden="true"></svg>
              {{ error() }}
            </p>
          }
          <button
            cp-button
            type="submit"
            class="self-start"
            [disabled]="busy() || !bookableCount()"
          >
            <svg lucideCalendarCheck class="size-4" aria-hidden="true"></svg>
            {{ 'bookings.subscription.submit' | transloco: { count: bookableCount() } }}
          </button>
          <p class="text-xs text-muted">{{ 'bookings.subscription.approvalHint' | transloco }}</p>
        </form>
      } @else {
        <cp-skeleton [lines]="4" />
      }
    </cp-glass-card>
  `,
})
export class SubscribePanel {
  readonly series = input.required<Series>();
  readonly changed = output<void>();

  private readonly api = inject(BookingsApi);
  private readonly actions = inject(BookingActions);
  private readonly auth = inject(AuthService);
  private readonly toast = inject(ToastService);
  private readonly transloco = inject(TranslocoService);
  private readonly language = inject(LanguageService);

  protected readonly preferenceKeys = BOOKING_PREFERENCE_KEYS;
  protected readonly form = new FormGroup({
    option: new FormControl('8', { nonNullable: true }),
    start: new FormControl('', { nonNullable: true }),
    pickup: new FormControl('', { nonNullable: true }),
    dropoff: new FormControl('', { nonNullable: true }),
    seats: new FormControl(1, { nonNullable: true }),
  });
  private readonly values = toSignal(this.form.valueChanges, {
    initialValue: this.form.getRawValue(),
  });
  /** Solo los puestos cambian la disponibilidad (computed evita recargar por otros campos). */
  private readonly seatCount = computed(() => this.values().seats ?? 1);
  protected readonly prefs = signal<BookingPreferences>(noPreferences());
  protected readonly availability = signal<SeriesAvailability | null>(null);
  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);

  protected readonly mine = computed(() => {
    const sub = this.series().my_subscription;
    return sub && (sub.status === 'requested' || sub.status === 'active') ? sub : null;
  });
  protected readonly subTone = computed(
    () => SUBSCRIPTION_STATUS_TONE[this.mine()?.status ?? 'requested'],
  );
  protected readonly blocked = computed(() => {
    const series = this.series();
    if (series.status !== 'active') return 'bookings.subscription.closed';
    const womenOnly = series.rules.some((rule) => rule.kind === 'women_only');
    if (womenOnly && this.auth.user()?.sex !== 'female') return 'bookings.panel.womenOnly';
    return null;
  });
  protected readonly maxSeats = computed(() => Math.max(1, Math.min(4, this.series().seats)));

  protected readonly optionChoices = computed<SelectOption[]>(() =>
    (this.availability()?.options ?? []).map((option) => ({
      value: String(option),
      label:
        option === 'series'
          ? this.transloco.translate('bookings.subscription.wholeSeries')
          : this.transloco.translate('bookings.subscription.days_count', { count: option }),
    })),
  );
  private readonly days = computed(() =>
    (this.availability()?.days ?? []).filter(
      (day) => day.status === 'scheduled' || day.status === 'cancelled_pico_placa',
    ),
  );
  protected readonly startChoices = computed<SelectOption[]>(() =>
    this.days()
      .filter((day) => day.status === 'scheduled')
      .map((day) => ({ value: day.date, label: this.date(day.date) })),
  );
  protected readonly rangeDays = computed(() => {
    const { option, start } = this.values();
    if (!start || !option) return [];
    const parsed: SubscriptionOption = option === 'series' ? 'series' : Number(option);
    const end = subscriptionEnd(start, parsed, this.series().window_end);
    return this.days().filter((day) => day.date >= start && day.date <= end);
  });
  protected readonly bookableCount = computed(
    () => this.rangeDays().filter((day) => day.bookable).length,
  );

  private readonly stops = computed(() =>
    this.series().stops.map((stop) => ({ value: stop.place_id, label: stop.name })),
  );
  protected readonly pickupOptions = computed(() => this.stops().slice(0, -1));
  protected readonly dropoffOptions = computed(() => this.stops().slice(1));

  constructor() {
    effect(() => {
      const series = this.series();
      const seats = this.seatCount();
      untracked(() => {
        if (this.blocked() || this.mine()) return;
        void this.loadAvailability(series.id, seats);
      });
    });
    effect(() => {
      const series = this.series();
      untracked(() =>
        this.form.patchValue(
          {
            pickup: series.stops[0]?.place_id ?? '',
            dropoff: series.stops.at(-1)?.place_id ?? '',
          },
          { emitEvent: false },
        ),
      );
    });
  }

  private async loadAvailability(seriesId: string, seats: number): Promise<void> {
    try {
      const availability = await this.api.availability(seriesId, seats);
      this.availability.set(availability);
      const first = availability.days.find((day) => day.status === 'scheduled');
      if (!this.form.controls.start.value && first) {
        this.form.controls.start.setValue(first.date);
      }
      const option = this.form.controls.option.value;
      if (!availability.options.map(String).includes(option)) {
        this.form.controls.option.setValue(String(availability.options[0] ?? 'series'));
      }
    } catch (error) {
      this.error.set(apiErrorMessage(this.transloco, error));
    }
  }

  protected setPref(key: keyof BookingPreferences, on: boolean): void {
    this.prefs.update((prefs) => ({ ...prefs, [key]: on }));
  }

  protected date(value: string): string {
    const [y, m, d] = value.split('-').map(Number);
    return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString(this.language.current(), {
      weekday: 'short',
      day: 'numeric',
      month: 'short',
      timeZone: 'UTC',
    });
  }

  protected dayState(day: AvailabilityDay): string {
    if (day.status === 'cancelled_pico_placa') return 'bookings.subscription.dayPicoPlaca';
    return day.bookable ? 'bookings.subscription.dayFree' : 'bookings.subscription.dayFull';
  }

  protected dayClass(day: AvailabilityDay): string {
    if (day.status === 'cancelled_pico_placa') return 'bg-warning/15 text-text line-through';
    return day.bookable ? 'bg-accent/15 text-text' : 'bg-muted/15 text-muted';
  }

  protected async submit(): Promise<void> {
    const { option, start, pickup, dropoff, seats } = this.form.getRawValue();
    this.error.set(null);
    this.busy.set(true);
    try {
      await this.api.subscribe(this.series().id, {
        option: option === 'series' ? 'series' : Number(option),
        start_date: start,
        seats,
        pickup_place_id: pickup,
        dropoff_place_id: dropoff,
        preferences: this.prefs(),
      });
      this.toast.show(this.transloco.translate('bookings.subscription.sent'), 'success');
      this.changed.emit();
    } catch (error) {
      this.error.set(apiErrorMessage(this.transloco, error));
    } finally {
      this.busy.set(false);
    }
  }

  protected async cancel(): Promise<void> {
    const sub = this.mine();
    if (sub && (await this.actions.cancelSubscription(sub.id))) this.changed.emit();
  }
}
