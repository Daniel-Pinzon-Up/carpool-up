import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  computed,
  effect,
  inject,
  input,
  signal,
  untracked,
} from '@angular/core';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { FormArray, FormBuilder, FormControl, ReactiveFormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { TranslocoPipe, TranslocoService } from '@jsverse/transloco';
import {
  LucideArrowLeft,
  LucideArrowRight,
  LucideCircleAlert,
  LucideHandCoins,
  LucidePlus,
  LucideTrash2,
  LucideTriangleAlert,
} from '@icons';
import { debounceTime } from 'rxjs';
import { AuthService } from '../../core/auth/auth.service';
import { apiErrorMessage } from '../../core/http/api-error-message';
import { LOCALE } from '../../core/i18n/locale';
import { MetaService } from '../../core/meta/meta.service';
import { MapMarker, MapView } from '../../shared/map/map-view';
import { PlacePicker } from '../../shared/map/place-picker';
import { PlaceValue } from '../../shared/map/places.api';
import { RouteSummary } from '../../shared/map/route-summary';
import { RoutePreview, RoutingApi, formatCop } from '../../shared/map/routing.api';
import { GlassButton } from '../../shared/ui/glass-button';
import { GlassCard } from '../../shared/ui/glass-card';
import { GlassInput } from '../../shared/ui/glass-input';
import { GlassSelect, SelectOption } from '../../shared/ui/glass-select';
import { GlassTextarea } from '../../shared/ui/glass-textarea';
import { SeatPicker } from '../../shared/ui/seat-picker';
import { Stepper } from '../../shared/ui/stepper';
import { ToastService } from '../../shared/ui/toast.service';
import {
  RuleKind,
  Trip,
  TripRule,
  TripStop,
  TripsApi,
  addDays,
  pamplonaDate,
  pamplonaInstant,
  pamplonaTime,
} from '../trips/trips.api';
import { Vehicle, VehiclesApi } from '../vehicles/vehicles.api';

export type WizardMode = 'create' | 'edit-trip';
type Step = 'route' | 'when' | 'vehicle' | 'price' | 'rules' | 'summary';
type RuleChoice = '' | 'allowed' | 'not_allowed';

export const TOGGLE_RULES = ['pets', 'luggage', 'smoking', 'music'] as const;

function toPlace(stop: TripStop): PlaceValue {
  return {
    place_id: stop.place_id,
    name: stop.name,
    kind: 'landmark',
    lat: stop.lat,
    lon: stop.lon,
  };
}

/**
 * Asistente para publicar un viaje: ruta con mapa, fecha y hora, vehiculo y puestos,
 * aporte sugerido con tope, reglas y resumen. Tambien edita un viaje existente.
 */
@Component({
  selector: 'cp-publish-wizard',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    ReactiveFormsModule,
    TranslocoPipe,
    GlassButton,
    GlassCard,
    GlassInput,
    GlassSelect,
    GlassTextarea,
    MapView,
    PlacePicker,
    RouteSummary,
    SeatPicker,
    Stepper,
    LucideArrowLeft,
    LucideArrowRight,
    LucideCircleAlert,
    LucideHandCoins,
    LucidePlus,
    LucideTrash2,
    LucideTriangleAlert,
  ],
  templateUrl: './publish-wizard.html',
})
export default class PublishWizard {
  /** Desde la ruta: modo (data) e id del viaje a editar (parametro). */
  readonly mode = input<WizardMode>('create');
  readonly id = input<string | null>(null);

  private readonly routing = inject(RoutingApi);
  private readonly trips = inject(TripsApi);
  private readonly vehiclesApi = inject(VehiclesApi);
  private readonly transloco = inject(TranslocoService);
  private readonly toast = inject(ToastService);
  private readonly router = inject(Router);
  private readonly auth = inject(AuthService);
  private readonly fb = inject(FormBuilder);
  protected readonly meta = inject(MetaService);

  protected readonly toggleRules = TOGGLE_RULES;

  protected readonly form = this.fb.nonNullable.group({
    origin: new FormControl<PlaceValue | null>(null),
    stops: this.fb.array<FormControl<PlaceValue | null>>([]),
    destination: new FormControl<PlaceValue | null>(null),
    date: '',
    time: '07:00',
    vehicle_id: '',
    seats: 3,
    price: '',
    women_only: false,
    pets: this.fb.nonNullable.control<RuleChoice>(''),
    luggage: this.fb.nonNullable.control<RuleChoice>(''),
    smoking: this.fb.nonNullable.control<RuleChoice>(''),
    music: this.fb.nonNullable.control<RuleChoice>(''),
    custom: '',
  });
  protected get stops(): FormArray<FormControl<PlaceValue | null>> {
    return this.form.controls.stops;
  }
  private readonly value = toSignal(this.form.valueChanges, {
    initialValue: this.form.getRawValue(),
  });

  protected readonly vehicles = signal<Vehicle[]>([]);
  protected readonly preview = signal<RoutePreview | null>(null);
  protected readonly loadingRoute = signal(false);
  protected readonly routeError = signal<string | null>(null);
  protected readonly stepError = signal<string | null>(null);
  protected readonly submitting = signal(false);
  protected readonly loaded = signal(false);
  protected readonly picoPlaca = signal<Set<string>>(new Set());
  private readonly stopCount = signal(0);

  protected readonly steps = signal<Step[]>([
    'route',
    'when',
    'vehicle',
    'price',
    'rules',
    'summary',
  ]);
  protected readonly stepIndex = signal(0);
  protected readonly step = computed(() => this.steps()[this.stepIndex()]);
  protected readonly stepLabels = computed(() =>
    this.steps().map((s) => this.transloco.translate(`publish.steps.${s}`)),
  );

  protected readonly isFemale = computed(() => this.auth.user()?.sex === 'female');
  private readonly maxStops = computed(() => Number(this.meta.settings()['max_trip_stops'] ?? 5));
  protected readonly canAddStop = computed(() => this.stopCount() < this.maxStops());
  protected readonly maxPrice = computed(() => {
    const value = this.meta.settings()['max_price_per_seat'];
    return typeof value === 'number' ? value : null;
  });
  protected readonly vehicle = computed(
    () => this.vehicles().find((v) => v.id === this.value().vehicle_id) ?? null,
  );
  protected readonly seatMax = computed(() => Math.max(1, (this.vehicle()?.capacity ?? 5) - 1));
  protected readonly vehicleOptions = computed<SelectOption[]>(() =>
    this.vehicles().map((v) => ({ value: v.id, label: `${v.brand} ${v.model} (${v.plate})` })),
  );
  protected readonly today = computed(() => pamplonaDate(new Date()));
  protected readonly maxSingleDate = computed(() =>
    addDays(this.today(), Number(this.meta.settings()['trip_max_days_ahead'] ?? 60)),
  );

  protected readonly singleBlocked = computed(() => {
    const date = this.value().date;
    return !!date && this.picoPlaca().has(date);
  });

  /** Fecha y hora de salida, para la ETA y el precio de la vista previa. */
  private readonly firstDeparture = computed(() => {
    const v = this.value();
    return v.date && v.time ? pamplonaInstant(v.date, v.time) : null;
  });

  protected readonly markers = computed<MapMarker[]>(() =>
    (this.preview()?.points ?? []).map((p, i, all) => ({
      lat: p.lat,
      lon: p.lon,
      kind: i === 0 ? 'origin' : i === all.length - 1 ? 'destination' : 'stop',
      label: p.name ?? this.transloco.translate('routeSummary.pin'),
    })),
  );

  constructor() {
    void this.meta.load();
    const destroyRef = inject(DestroyRef);
    this.form.valueChanges
      .pipe(debounceTime(400), takeUntilDestroyed(destroyRef))
      .subscribe(() => void this.refreshPreview());

    // Al cambiar de vehiculo se piden sus fechas de pico y placa y se ajustan los puestos.
    effect(() => {
      const vehicle = this.vehicle();
      if (!vehicle) return;
      untracked(() => {
        const seats = this.form.controls.seats;
        if (seats.value > this.seatMax()) seats.setValue(this.seatMax());
        void this.loadPicoPlaca(vehicle.id);
      });
    });

    // Modo y datos de la ruta llegan como entradas: se cargan una vez.
    effect(() => {
      const mode = this.mode();
      const id = this.id();
      untracked(() => void this.init(mode, id));
    });
  }

  private async init(mode: WizardMode, id: string | null): Promise<void> {
    const tomorrow = addDays(this.today(), 1);
    this.form.patchValue({ date: tomorrow }, { emitEvent: false });
    try {
      const vehicles = await this.vehiclesApi.list();
      this.vehicles.set(vehicles.filter((v) => v.is_active));
      if (mode === 'edit-trip' && id) {
        this.fillFromTrip(await this.trips.trip(id));
      } else if (this.vehicles().length) {
        this.form.controls.vehicle_id.setValue(this.vehicles()[0].id);
      }
    } catch (error) {
      this.stepError.set(apiErrorMessage(this.transloco, error));
    } finally {
      this.loaded.set(true);
    }
  }

  private async loadPicoPlaca(vehicleId: string): Promise<void> {
    try {
      const dates = await this.trips.picoPlacaDates(vehicleId, this.today(), this.maxSingleDate());
      this.picoPlaca.set(new Set(dates));
    } catch {
      this.picoPlaca.set(new Set());
    }
  }

  private fillRoute(stops: TripStop[]): void {
    this.stops.clear({ emitEvent: false });
    for (const stop of stops.slice(1, -1)) {
      this.stops.push(new FormControl<PlaceValue | null>(toPlace(stop)), { emitEvent: false });
    }
    this.stopCount.set(this.stops.length);
    this.form.patchValue(
      { origin: toPlace(stops[0]), destination: toPlace(stops[stops.length - 1]) },
      { emitEvent: false },
    );
  }

  private fillRules(rules: TripRule[]): void {
    const patch: Record<string, unknown> = { women_only: false, custom: '' };
    for (const kind of TOGGLE_RULES) patch[kind] = '';
    for (const rule of rules) {
      if (rule.kind === 'women_only') patch['women_only'] = rule.value === 'allowed';
      else patch[rule.kind] = rule.value;
    }
    this.form.patchValue(patch, { emitEvent: false });
  }

  private fillFromTrip(trip: Trip): void {
    this.fillRoute(trip.stops);
    this.fillRules(trip.rules);
    this.form.patchValue({
      date: pamplonaDate(trip.departs_at),
      time: pamplonaTime(trip.departs_at),
      vehicle_id: trip.vehicle.id,
      seats: trip.seats_total,
      price: String(trip.price_per_seat),
    });
  }

  // --- Paradas ------------------------------------------------------------------------

  protected addStop(): void {
    if (!this.canAddStop()) return;
    this.stops.push(new FormControl<PlaceValue | null>(null));
    this.stopCount.set(this.stops.length);
  }

  protected removeStop(index: number): void {
    this.stops.removeAt(index);
    this.stopCount.set(this.stops.length);
  }

  protected formatDate(date: string): string {
    const [y, m, d] = date.split('-').map(Number);
    return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString(LOCALE, {
      weekday: 'short',
      day: 'numeric',
      month: 'short',
      timeZone: 'UTC',
    });
  }

  protected money(value: number): string {
    return formatCop(value, LOCALE);
  }

  // --- Vista previa -------------------------------------------------------------------

  private placeIds(): string[] {
    const { origin, stops, destination } = this.form.getRawValue();
    return [origin, ...stops, destination]
      .filter((p): p is PlaceValue => p !== null)
      .map((p) => p.place_id);
  }

  private async refreshPreview(): Promise<void> {
    const { origin, destination, seats } = this.form.getRawValue();
    if (!origin || !destination) {
      this.preview.set(null);
      return;
    }
    const vehicle = this.vehicle();
    this.loadingRoute.set(true);
    this.routeError.set(null);
    try {
      this.preview.set(
        await this.routing.preview({
          points: this.placeIds().map((place_id) => ({ place_id })),
          departs_at: this.firstDeparture() ?? undefined,
          vehicle_type: vehicle?.type,
          seats: vehicle ? Math.min(seats, this.seatMax()) : undefined,
        }),
      );
    } catch (error) {
      this.preview.set(null);
      this.routeError.set(apiErrorMessage(this.transloco, error));
    } finally {
      this.loadingRoute.set(false);
    }
  }

  protected useSuggestedPrice(): void {
    const suggested = this.preview()?.suggested_price;
    if (suggested !== null && suggested !== undefined)
      this.form.controls.price.setValue(String(suggested));
  }

  // --- Navegacion ---------------------------------------------------------------------

  /** Valida el paso actual; devuelve la clave del error o null. */
  protected stepProblem(step: Step): string | null {
    const v = this.form.getRawValue();
    switch (step) {
      case 'route':
        if (!v.origin || !v.destination) return 'publish.errors.route';
        if (this.routeError()) return 'publish.errors.routeFailed';
        return null;
      case 'when':
        if (!v.time) return 'publish.errors.time';
        if (!v.date || v.date < this.today() || v.date > this.maxSingleDate())
          return 'publish.errors.date';
        if (new Date(pamplonaInstant(v.date, v.time)).getTime() <= Date.now())
          return 'publish.errors.past';
        if (this.singleBlocked()) return 'publish.errors.picoPlaca';
        return null;
      case 'vehicle':
        if (!this.vehicle()) return 'publish.errors.vehicle';
        if (v.seats < 1 || v.seats > this.seatMax()) return 'publish.errors.seats';
        return null;
      case 'price': {
        const max = this.maxPrice();
        const price = Number(v.price);
        if (v.price.trim() === '' || !Number.isInteger(price) || price < 0)
          return 'publish.errors.price';
        if (max !== null && price > max) return 'publish.errors.priceMax';
        return null;
      }
      case 'rules':
        return v.custom.length > 200 ? 'publish.errors.custom' : null;
      default:
        return null;
    }
  }

  protected async next(): Promise<void> {
    const step = this.step();
    const problem = this.stepProblem(step);
    if (problem) {
      this.stepError.set(
        this.transloco.translate(problem, { max: this.maxPrice() ?? 0, seats: this.seatMax() }),
      );
      return;
    }
    this.stepError.set(null);
    this.stepIndex.update((i) => Math.min(i + 1, this.steps().length - 1));
    this.focusHeading();
    if (step === 'vehicle') {
      // El aporte sugerido depende del vehiculo y los puestos elegidos.
      await this.refreshPreview();
      if (this.form.controls.price.value === '') this.useSuggestedPrice();
    }
  }

  protected back(): void {
    this.stepError.set(null);
    this.stepIndex.update((i) => Math.max(0, i - 1));
    this.focusHeading();
  }

  private focusHeading(): void {
    queueMicrotask(() => document.getElementById('publish-step-title')?.focus());
  }

  // --- Envio --------------------------------------------------------------------------

  protected rules(): TripRule[] {
    const v = this.form.getRawValue();
    const rules: TripRule[] = [];
    if (v.women_only && this.isFemale()) rules.push({ kind: 'women_only', value: 'allowed' });
    for (const kind of TOGGLE_RULES) {
      if (v[kind]) rules.push({ kind: kind as RuleKind, value: v[kind] });
    }
    if (v.custom.trim()) rules.push({ kind: 'custom', value: v.custom.trim() });
    return rules;
  }

  protected async submit(): Promise<void> {
    for (const step of this.steps()) {
      const problem = this.stepProblem(step);
      if (problem) {
        this.stepIndex.set(this.steps().indexOf(step));
        this.stepError.set(this.transloco.translate(problem, { max: this.maxPrice() ?? 0 }));
        return;
      }
    }
    const v = this.form.getRawValue();
    const body = {
      place_ids: this.placeIds(),
      departs_at: pamplonaInstant(v.date, v.time),
      vehicle_id: v.vehicle_id,
      seats: v.seats,
      price_per_seat: Number(v.price),
      rules: this.rules(),
    };
    this.submitting.set(true);
    this.stepError.set(null);
    try {
      const id = this.id();
      const trip =
        this.mode() === 'edit-trip' && id
          ? await this.trips.updateTrip(id, body)
          : await this.trips.publishTrip(body);
      const target = `/viajes/${trip.id}`;
      this.toast.show(
        this.transloco.translate(this.mode() === 'create' ? 'publish.published' : 'publish.saved'),
        'success',
      );
      await this.router.navigateByUrl(target);
    } catch (error) {
      this.stepError.set(apiErrorMessage(this.transloco, error));
    } finally {
      this.submitting.set(false);
    }
  }
}
