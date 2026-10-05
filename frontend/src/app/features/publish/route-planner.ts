import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  computed,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { FormArray, FormBuilder, FormControl, ReactiveFormsModule } from '@angular/forms';
import { TranslocoPipe, TranslocoService } from '@jsverse/transloco';
import { LucideCircleAlert, LucidePlus, LucideTrash2 } from '@lucide/angular';
import { debounceTime, merge } from 'rxjs';
import { apiErrorMessage } from '../../core/http/api-error-message';
import { MetaService } from '../../core/meta/meta.service';
import { MapMarker, MapView } from '../../shared/map/map-view';
import { PlacePicker } from '../../shared/map/place-picker';
import { PlaceValue } from '../../shared/map/places.api';
import { RouteSummary } from '../../shared/map/route-summary';
import { RoutePreview, RoutingApi } from '../../shared/map/routing.api';
import { GlassButton } from '../../shared/ui/glass-button';
import { GlassCard } from '../../shared/ui/glass-card';
import { GlassInput } from '../../shared/ui/glass-input';
import { GlassSelect, SelectOption } from '../../shared/ui/glass-select';
import { SeatPicker } from '../../shared/ui/seat-picker';
import { Vehicle, VehiclesApi } from '../vehicles/vehicles.api';

/**
 * Ruta del viaje: origen, paradas y destino con mapa, distancia, ETA y precio sugerido.
 * Es el primer paso del asistente de publicacion (el paso 6 agrega fecha, reglas y envio).
 */
@Component({
  selector: 'cp-route-planner',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    ReactiveFormsModule,
    TranslocoPipe,
    GlassButton,
    GlassCard,
    GlassInput,
    GlassSelect,
    MapView,
    PlacePicker,
    RouteSummary,
    SeatPicker,
    LucidePlus,
    LucideTrash2,
    LucideCircleAlert,
  ],
  templateUrl: './route-planner.html',
})
export default class RoutePlanner {
  private readonly routing = inject(RoutingApi);
  private readonly vehiclesApi = inject(VehiclesApi);
  private readonly transloco = inject(TranslocoService);
  private readonly fb = inject(FormBuilder);
  protected readonly meta = inject(MetaService);

  protected readonly form = this.fb.group({
    origin: new FormControl<PlaceValue | null>(null),
    stops: this.fb.array<FormControl<PlaceValue | null>>([]),
    destination: new FormControl<PlaceValue | null>(null),
    vehicle_id: new FormControl<string>('', { nonNullable: true }),
    seats: new FormControl<number>(3, { nonNullable: true }),
    departs_at: new FormControl<string>('', { nonNullable: true }),
  });
  protected get stops(): FormArray<FormControl<PlaceValue | null>> {
    return this.form.controls.stops;
  }

  protected readonly vehicles = signal<Vehicle[]>([]);
  protected readonly preview = signal<RoutePreview | null>(null);
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);
  private readonly maxStops = computed(() => Number(this.meta.settings()['max_trip_stops'] ?? 5));
  private readonly stopCount = signal(0);
  protected readonly canAddStop = computed(() => this.stopCount() < this.maxStops());

  private readonly vehicleId = toSignal(this.form.controls.vehicle_id.valueChanges, {
    initialValue: '',
  });
  protected readonly vehicle = computed(
    () => this.vehicles().find((v) => v.id === this.vehicleId()) ?? null,
  );
  protected readonly seatRange = computed<[number, number]>(() => {
    const vehicle = this.vehicle();
    return vehicle ? [1, Math.max(1, vehicle.capacity - 1)] : [1, 4];
  });
  protected readonly vehicleOptions = computed<SelectOption[]>(() =>
    this.vehicles().map((v) => ({
      value: v.id,
      label: `${v.brand} ${v.model} (${v.plate})`,
    })),
  );
  protected readonly markers = computed<MapMarker[]>(() => {
    const route = this.preview();
    if (!route) return [];
    return route.points.map((p, i, all) => ({
      lat: p.lat,
      lon: p.lon,
      kind: i === 0 ? 'origin' : i === all.length - 1 ? 'destination' : 'stop',
      label: p.name ?? this.transloco.translate('routeSummary.pin'),
    }));
  });

  constructor() {
    void this.meta.load();
    void this.loadVehicles();
    // Se recalcula la ruta poco despues de cada cambio, no en cada tecla.
    merge(this.form.valueChanges)
      .pipe(debounceTime(400), takeUntilDestroyed(inject(DestroyRef)))
      .subscribe(() => void this.refresh());
  }

  private async loadVehicles(): Promise<void> {
    try {
      const active = (await this.vehiclesApi.list()).filter((v) => v.is_active);
      this.vehicles.set(active);
      if (active.length) this.form.controls.vehicle_id.setValue(active[0].id);
    } catch {
      // Sin vehiculos se puede ver la ruta, pero no el precio.
    }
  }

  protected addStop(): void {
    if (!this.canAddStop()) return;
    this.stops.push(new FormControl<PlaceValue | null>(null));
    this.stopCount.set(this.stops.length);
  }

  protected removeStop(index: number): void {
    this.stops.removeAt(index);
    this.stopCount.set(this.stops.length);
  }

  private async refresh(): Promise<void> {
    const { origin, destination, stops, seats, departs_at } = this.form.getRawValue();
    if (!origin || !destination) {
      this.preview.set(null);
      return;
    }
    const vehicle = this.vehicle();
    const seatLimit = this.seatRange()[1];
    if (seats > seatLimit) {
      this.form.controls.seats.setValue(seatLimit, { emitEvent: false });
    }
    this.loading.set(true);
    this.error.set(null);
    try {
      const points = [origin, ...stops.filter((s): s is PlaceValue => s !== null), destination];
      this.preview.set(
        await this.routing.preview({
          points: points.map((p) => ({ place_id: p.place_id })),
          departs_at: departs_at ? new Date(departs_at).toISOString() : undefined,
          vehicle_type: vehicle?.type,
          seats: vehicle ? Math.min(seats, seatLimit) : undefined,
        }),
      );
    } catch (error) {
      this.preview.set(null);
      this.error.set(apiErrorMessage(this.transloco, error));
    } finally {
      this.loading.set(false);
    }
  }
}
