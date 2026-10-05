import { Component, input } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { getTranslocoTestingModule } from '../../../testing/transloco-testing';
import { MetaService } from '../../core/meta/meta.service';
import { MapView } from '../../shared/map/map-view';
import { PlaceValue } from '../../shared/map/places.api';
import { RoutingApi } from '../../shared/map/routing.api';
import { VehiclesApi } from '../vehicles/vehicles.api';
import RoutePlanner from './route-planner';

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
  pricing_configured: false,
  suggested_price: null,
  max_price_per_seat: null,
};

describe('RoutePlanner', () => {
  let routing: { preview: ReturnType<typeof vi.fn> };

  beforeEach(() => {
    vi.useFakeTimers();
    routing = { preview: vi.fn().mockResolvedValue(PREVIEW) };
    TestBed.configureTestingModule({
      imports: [RoutePlanner, getTranslocoTestingModule()],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: RoutingApi, useValue: routing },
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
    }).overrideComponent(RoutePlanner, {
      remove: { imports: [MapView] },
      add: { imports: [MapViewStub] },
    });
    vi.spyOn(TestBed.inject(MetaService), 'load').mockResolvedValue({} as never);
  });

  afterEach(() => vi.useRealTimers());

  async function create() {
    const fixture = TestBed.createComponent(RoutePlanner);
    fixture.detectChanges();
    await vi.advanceTimersByTimeAsync(0);
    fixture.detectChanges();
    const form = (fixture.componentInstance as unknown as { form: RoutePlanner['form'] }).form;
    return { fixture, form };
  }

  it('no calcula hasta tener origen y destino, y luego envia vehiculo y cupos', async () => {
    const { fixture, form } = await create();
    form.controls.origin.setValue(CAMPUS);
    await vi.advanceTimersByTimeAsync(500);
    expect(routing.preview).not.toHaveBeenCalled();

    form.controls.destination.setValue(TERMINAL);
    await vi.advanceTimersByTimeAsync(500);
    fixture.detectChanges();
    expect(routing.preview).toHaveBeenCalledTimes(1);
    expect(routing.preview).toHaveBeenCalledWith(
      expect.objectContaining({
        points: [{ place_id: 'c1' }, { place_id: 't1' }],
        vehicle_type: 'car',
        seats: 3,
      }),
    );
    expect(fixture.nativeElement.textContent).toContain('3 km');
  });

  it('limita las paradas segun el parametro max_trip_stops', async () => {
    TestBed.inject(MetaService).settings.update((s) => ({ ...s, max_trip_stops: 1 }));
    const { fixture } = await create();
    const add = Array.from(fixture.nativeElement.querySelectorAll('button')).find((b) =>
      (b as HTMLElement).textContent?.includes('Agregar parada'),
    ) as HTMLButtonElement;
    add.click();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Parada 1');
    expect(add.disabled).toBe(true);
  });

  it('muestra el error del servicio de rutas con un mensaje claro', async () => {
    // El interceptor ya convierte la respuesta en ApiError.
    routing.preview.mockRejectedValue({ code: 'ROUTING_UNAVAILABLE', message: 'x', details: {} });
    const { fixture, form } = await create();
    form.patchValue({ origin: CAMPUS, destination: TERMINAL });
    await vi.advanceTimersByTimeAsync(500);
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('[role=alert]').textContent).toContain(
      'servicio de rutas no está disponible',
    );
  });
});
