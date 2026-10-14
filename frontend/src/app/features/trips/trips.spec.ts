import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { getTranslocoTestingModule } from '../../../testing/transloco-testing';
import { ME } from '../../../testing/auth-fixtures';
import { AuthService } from '../../core/auth/auth.service';
import { MapView } from '../../shared/map/map-view';
import { DialogService } from '../../shared/ui/dialog.service';
import DriverTrips from './driver-trips';
import TripDetail from './trip-detail';
import {
  Trip,
  TripSummary,
  TripsApi,
  addDays,
  pamplonaDate,
  pamplonaInstant,
  pamplonaTime,
} from './trips.api';
import { Component, input } from '@angular/core';
import { of } from 'rxjs';

async function settle(): Promise<void> {
  for (let i = 0; i < 10; i++) await Promise.resolve();
}

@Component({ selector: 'cp-map-view', template: '' })
class MapViewStub {
  readonly route = input<unknown>(null);
  readonly markers = input<unknown>([]);
  readonly label = input('');
}

const SUMMARY: TripSummary = {
  id: 't1',
  status: 'scheduled',
  departs_at: '2026-10-06T12:00:00Z',
  arrives_at: '2026-10-06T12:10:00Z',
  seats_total: 3,
  price_per_seat: 2000,
  origin: 'Ciudad Universitaria',
  destination: 'Terminal',
  stop_count: 1,
  vehicle: {
    id: 'v1',
    type: 'car',
    brand: 'Chevrolet',
    model: 'Spark',
    color: 'Gris',
    has_photo: false,
    plate: 'ABC123',
  },
  editable: true,
  seats_available: 3,
  pending_requests: 0,
};

const TRIP: Trip = {
  ...SUMMARY,
  geometry: [
    [-72.6495, 7.387],
    [-72.6512, 7.3712],
  ],
  distance_m: 4000,
  est_duration_s: 600,
  stops: [
    {
      position: 0,
      kind: 'origin',
      place_id: 'a',
      name: 'Ciudad Universitaria',
      lat: 7.387,
      lon: -72.6495,
      eta: '2026-10-06T12:00:00Z',
    },
    {
      position: 1,
      kind: 'destination',
      place_id: 'b',
      name: 'Terminal',
      lat: 7.3712,
      lon: -72.6512,
      eta: '2026-10-06T12:10:00Z',
    },
  ],
  rules: [{ kind: 'pets', value: 'not_allowed' }],
  driver: { id: ME.id, full_name: ME.full_name },
  cancel_reason: null,
  cancelled_at: null,
  passengers: [],
  payment_note: null,
  my_booking: null,
  chat_id: null,
};

describe('fechas de Pamplona', () => {
  it('convierte instantes a fecha y hora locales (UTC-5)', () => {
    expect(pamplonaDate('2026-10-06T03:00:00Z')).toBe('2026-10-05');
    expect(pamplonaTime('2026-10-06T12:30:00Z')).toBe('07:30');
    expect(pamplonaInstant('2026-10-06', '07:30')).toBe('2026-10-06T07:30:00-05:00');
  });

  it('suma dias sin pasar por zonas horarias', () => {
    expect(addDays('2026-10-30', 3)).toBe('2026-11-02');
  });
});

describe('TripDetail', () => {
  let api: Record<string, ReturnType<typeof vi.fn>>;

  beforeEach(() => {
    api = {
      trip: vi.fn().mockResolvedValue(TRIP),
      cancelTrip: vi.fn().mockResolvedValue({
        ...TRIP,
        status: 'cancelled_by_driver',
        editable: false,
        cancel_reason: 'Se daño el carro',
      }),
    };
    TestBed.configureTestingModule({
      imports: [TripDetail, getTranslocoTestingModule()],
      providers: [
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: TripsApi, useValue: api },
      ],
    }).overrideComponent(TripDetail, {
      remove: { imports: [MapView] },
      add: { imports: [MapViewStub] },
    });
    TestBed.inject(AuthService).user.set({ ...ME, role: 'driver' });
  });

  async function create() {
    const fixture = TestBed.createComponent(TripDetail);
    fixture.componentRef.setInput('id', 't1');
    fixture.detectChanges();
    await settle();
    fixture.detectChanges();
    return fixture;
  }

  it('muestra paradas con hora, reglas, placa y acciones del conductor', async () => {
    const fixture = await create();
    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Programado');
    expect(text).toContain('Mascotas: No permitido');
    expect(text).toContain('ABC123');
    expect(text).toContain('7:00');
    expect(fixture.nativeElement.querySelector('a[href="/viajes/t1/editar"]')).not.toBeNull();
  });

  it('cancela con el motivo que escribe el conductor', async () => {
    const fixture = await create();
    vi.spyOn(TestBed.inject(DialogService), 'open').mockReturnValue({
      closed: of('Se daño el carro'),
    } as never);
    const cancel = Array.from(fixture.nativeElement.querySelectorAll('button')).find((b) =>
      (b as HTMLElement).textContent?.includes('Cancelar viaje'),
    ) as HTMLButtonElement;
    cancel.click();
    await settle();
    fixture.detectChanges();
    expect(api['cancelTrip']).toHaveBeenCalledWith('t1', 'Se daño el carro');
    expect(fixture.nativeElement.textContent).toContain('Se daño el carro');
    expect(fixture.nativeElement.querySelector('a[href="/viajes/t1/editar"]')).toBeNull();
  });

  it('muestra la recogida y bajada que llega desde la busqueda', async () => {
    const match = {
      trip_id: 't1',
      seats_available: 2,
      pickup: { kind: 'stop', name: 'Sede Casona', eta: '2026-10-06T12:04:00Z', walk_m: 80 },
      dropoff: { kind: 'route', name: null, eta: '2026-10-06T12:10:00Z', walk_m: 10 },
    };
    history.replaceState({ match }, '');
    try {
      const fixture = await create();
      const text = fixture.nativeElement.textContent as string;
      expect(text).toContain('Sede Casona');
      expect(text).toContain('A 80 m de tu punto');
      expect(text).toContain('Punto en la ruta');
    } finally {
      history.replaceState(null, '');
    }
  });

  it('otros usuarios no ven acciones de conductor', async () => {
    TestBed.inject(AuthService).user.set({ ...ME, id: 'otro' });
    api['trip'].mockResolvedValue({
      ...TRIP,
      vehicle: { ...TRIP.vehicle, plate: null },
      editable: false,
    });
    const fixture = await create();
    expect(fixture.nativeElement.textContent).not.toContain('Cancelar viaje');
    expect(fixture.nativeElement.textContent).not.toContain('ABC123');
  });
});

describe('DriverTrips', () => {
  it('lista los proximos viajes', async () => {
    const api = {
      myTrips: vi.fn().mockResolvedValue({ items: [SUMMARY], next_cursor: null }),
    };
    TestBed.configureTestingModule({
      imports: [DriverTrips, getTranslocoTestingModule()],
      providers: [
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: TripsApi, useValue: api },
      ],
    });
    const fixture = TestBed.createComponent(DriverTrips);
    fixture.detectChanges();
    await settle();
    fixture.detectChanges();
    expect(api.myTrips).toHaveBeenCalledWith('upcoming');
    expect(fixture.nativeElement.textContent).toContain('Ciudad Universitaria');
    expect(fixture.nativeElement.querySelector('a[href="/viajes/t1"]')).not.toBeNull();
  });
});
