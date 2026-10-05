import { Component, input } from '@angular/core';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { getTranslocoTestingModule } from '../../../testing/transloco-testing';
import { ME } from '../../../testing/auth-fixtures';
import { AuthService } from '../../core/auth/auth.service';
import { MetaService } from '../../core/meta/meta.service';
import { MapView } from '../../shared/map/map-view';
import { PlaceValue } from '../../shared/map/places.api';
import { RoutingApi } from '../../shared/map/routing.api';
import { TripsApi, addDays, pamplonaDate } from '../trips/trips.api';
import { VehiclesApi } from '../vehicles/vehicles.api';
import PublishWizard from './publish-wizard';

@Component({ selector: 'cp-map-view', template: '' })
class MapViewStub {
  readonly route = input<unknown>(null);
  readonly markers = input<unknown>([]);
  readonly label = input('');
}

const CAMPUS: PlaceValue = {
  place_id: 'c1',
  name: 'Campus',
  kind: 'campus',
  lat: 7.387,
  lon: -72.6495,
};
const TERMINAL: PlaceValue = {
  place_id: 't1',
  name: 'Terminal',
  kind: 'landmark',
  lat: 7.371,
  lon: -72.651,
};
const PREVIEW = {
  geometry: [],
  distance_m: 3000,
  osrm_duration_s: 280,
  traffic_factor: 1,
  duration_s: 280,
  points: [],
  pricing_configured: true,
  suggested_price: 1200,
  max_price_per_seat: 5000,
};

interface Wizard {
  form: PublishWizard['form'];
  step: () => string;
  stepError: () => string | null;
  next: () => Promise<void>;
  submit: () => Promise<void>;
  toggleWeekday: (day: number, on: boolean) => void;
  seriesPlan: () => { date: string; blocked: boolean }[];
}

describe('PublishWizard', () => {
  let trips: Record<string, ReturnType<typeof vi.fn>>;
  const today = pamplonaDate(new Date());

  beforeEach(() => {
    trips = {
      currentSemester: vi.fn().mockResolvedValue({
        id: 's',
        name: '2026-2',
        starts_on: today,
        ends_on: addDays(today, 90),
      }),
      picoPlacaDates: vi.fn().mockResolvedValue([addDays(today, 3)]),
      publishTrip: vi.fn().mockResolvedValue({ id: 'trip-1' }),
      publishSeries: vi.fn().mockResolvedValue({ id: 'series-1' }),
    };
    TestBed.configureTestingModule({
      imports: [PublishWizard, getTranslocoTestingModule()],
      providers: [
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: TripsApi, useValue: trips },
        { provide: RoutingApi, useValue: { preview: vi.fn().mockResolvedValue(PREVIEW) } },
        {
          provide: VehiclesApi,
          useValue: {
            list: vi.fn().mockResolvedValue([
              {
                id: 'v1',
                type: 'car',
                capacity: 5,
                brand: 'Chevrolet',
                model: 'Spark',
                plate: 'ABC123',
                is_active: true,
              },
            ]),
          },
        },
      ],
    }).overrideComponent(PublishWizard, {
      remove: { imports: [MapView] },
      add: { imports: [MapViewStub] },
    });
    vi.spyOn(TestBed.inject(MetaService), 'load').mockResolvedValue({} as never);
    TestBed.inject(MetaService).settings.update((s) => ({ ...s, max_price_per_seat: 5000 }));
    TestBed.inject(AuthService).user.set({ ...ME, role: 'driver', sex: 'male' });
    vi.spyOn(TestBed.inject(Router), 'navigateByUrl').mockResolvedValue(true);
  });

  async function create() {
    const fixture = TestBed.createComponent(PublishWizard);
    fixture.detectChanges();
    for (let i = 0; i < 10; i++) await Promise.resolve();
    fixture.detectChanges();
    return { fixture, wizard: fixture.componentInstance as unknown as Wizard };
  }

  it('no avanza sin ruta y explica por que', async () => {
    const { fixture, wizard } = await create();
    await wizard.next(); // tipo
    await wizard.next(); // ruta vacia
    fixture.detectChanges();
    expect(wizard.step()).toBe('route');
    expect(fixture.nativeElement.querySelector('[role=alert]').textContent).toContain(
      'Elige el origen y el destino',
    );
  });

  it('publica un viaje puntual con el aporte sugerido y las reglas', async () => {
    const { wizard } = await create();
    wizard.form.patchValue({
      origin: CAMPUS,
      destination: TERMINAL,
      date: addDays(today, 1),
      time: '07:30',
      pets: 'not_allowed',
    });
    await wizard.next(); // tipo -> ruta
    await wizard.next(); // ruta -> cuando
    await wizard.next(); // cuando -> vehiculo
    await wizard.next(); // vehiculo -> precio (toma el sugerido)
    expect(wizard.form.controls.price.value).toBe('1200');
    await wizard.next(); // precio -> reglas
    await wizard.next(); // reglas -> resumen
    expect(wizard.step()).toBe('summary');
    await wizard.submit();
    expect(trips['publishTrip']).toHaveBeenCalledWith({
      place_ids: ['c1', 't1'],
      vehicle_id: 'v1',
      seats: 3,
      price_per_seat: 1200,
      rules: [{ kind: 'pets', value: 'not_allowed' }],
      departs_at: `${addDays(today, 1)}T07:30:00-05:00`,
    });
    expect(TestBed.inject(Router).navigateByUrl).toHaveBeenCalledWith('/viajes/trip-1');
  });

  it('bloquea un viaje puntual en fecha de pico y placa y respeta el tope de precio', async () => {
    const { wizard } = await create();
    wizard.form.patchValue({ origin: CAMPUS, destination: TERMINAL, date: addDays(today, 3) });
    await wizard.next();
    await wizard.next();
    await wizard.next();
    expect(wizard.step()).toBe('when');
    expect(wizard.stepError()).toContain('pico y placa');

    wizard.form.patchValue({ date: addDays(today, 2) });
    await wizard.next();
    await wizard.next();
    wizard.form.patchValue({ price: '6000' });
    await wizard.next();
    expect(wizard.step()).toBe('price');
    expect(wizard.stepError()).toContain('5000');
  });

  it('la serie marca las fechas de pico y placa y se publica con sus dias', async () => {
    const { wizard } = await create();
    wizard.form.patchValue({
      kind: 'series',
      origin: CAMPUS,
      destination: TERMINAL,
      start_date: today,
      window: '15',
    });
    wizard.toggleWeekday(0, false);
    wizard.toggleWeekday(2, false);
    wizard.toggleWeekday(4, false);
    for (let day = 0; day < 7; day++) wizard.toggleWeekday(day, true);
    const plan = wizard.seriesPlan();
    expect(plan).toHaveLength(15);
    expect(plan.filter((d) => d.blocked).map((d) => d.date)).toEqual([addDays(today, 3)]);

    for (let i = 0; i < 6; i++) await wizard.next();
    expect(wizard.step()).toBe('summary');
    await wizard.submit();
    expect(trips['publishSeries']).toHaveBeenCalledWith(
      expect.objectContaining({
        weekdays: [0, 1, 2, 3, 4, 5, 6],
        start_date: today,
        window: 15,
        departure_time: '07:00',
      }),
    );
  });

  it('solo las conductoras ven la opcion solo mujeres', async () => {
    const { fixture, wizard } = await create();
    wizard.form.patchValue({ origin: CAMPUS, destination: TERMINAL, women_only: true });
    for (let i = 0; i < 5; i++) await wizard.next();
    fixture.detectChanges();
    expect(wizard.step()).toBe('rules');
    expect(fixture.nativeElement.textContent).not.toContain('Solo mujeres');
    expect((wizard as unknown as { rules: () => unknown[] }).rules()).toEqual([]);
  });
});
