import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { getTranslocoTestingModule } from '../../../testing/transloco-testing';
import { ME } from '../../../testing/auth-fixtures';
import { AuthService } from '../../core/auth/auth.service';
import { PlaceValue } from '../../shared/map/places.api';
import { ResultCard } from './result-card';
import SearchPage, { nextHalfHour } from './search-page';
import { SearchApi, SearchResult } from './search.api';

async function settle(): Promise<void> {
  for (let i = 0; i < 10; i++) await Promise.resolve();
}

const CAMPUS: PlaceValue = {
  place_id: 'p1',
  name: 'Ciudad Universitaria',
  kind: 'campus',
  lat: 7.387,
  lon: -72.6495,
};
const TERMINAL: PlaceValue = {
  place_id: 'p2',
  name: 'Terminal',
  kind: 'landmark',
  lat: 7.3712,
  lon: -72.6512,
};

const RESULT: SearchResult = {
  trip_id: 't1',
  status: 'scheduled',
  departs_at: '2026-10-06T12:00:00Z',
  arrives_at: '2026-10-06T12:10:00Z',
  origin: 'Ciudad Universitaria',
  destination: 'Terminal',
  price_per_seat: 2000,
  seats_available: 3,
  pickup: {
    kind: 'stop',
    name: 'Sede Casona',
    lat: 7.3762,
    lon: -72.6468,
    eta: '2026-10-06T12:04:00Z',
    walk_m: 120,
  },
  dropoff: {
    kind: 'route',
    name: null,
    lat: 7.3712,
    lon: -72.6512,
    eta: '2026-10-06T12:10:00Z',
    walk_m: 30,
  },
  minutes_from_requested: 4,
  driver: { id: 'd1', full_name: 'Laura Gomez', rating: null, trips_as_driver: 2 },
  vehicle: {
    vehicle_id: 'v1',
    type: 'car',
    brand: 'Chevrolet',
    model: 'Spark',
    color: 'Gris',
    has_photo: false,
  },
  rules: [{ kind: 'pets', value: 'not_allowed' }],
};

describe('nextHalfHour', () => {
  it('redondea a la siguiente media hora en Pamplona', () => {
    expect(nextHalfHour(new Date('2026-10-06T12:10:00Z'))).toBe('07:30');
    expect(nextHalfHour(new Date('2026-10-06T12:30:00Z'))).toBe('08:00');
    expect(nextHalfHour(new Date('2026-10-07T04:45:00Z'))).toBe('00:00');
  });
});

describe('SearchPage', () => {
  let api: { search: ReturnType<typeof vi.fn> };

  beforeEach(() => {
    localStorage.clear();
    api = { search: vi.fn().mockResolvedValue([RESULT]) };
    TestBed.configureTestingModule({
      imports: [SearchPage, getTranslocoTestingModule()],
      providers: [
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: SearchApi, useValue: api },
      ],
    });
  });

  afterEach(() => localStorage.clear());

  async function create() {
    const fixture = TestBed.createComponent(SearchPage);
    fixture.detectChanges();
    await settle();
    fixture.detectChanges();
    return fixture;
  }

  function chips(fixture: { nativeElement: HTMLElement }): string[] {
    return Array.from(fixture.nativeElement.querySelectorAll('cp-glass-chip')).map(
      (chip) => (chip as HTMLElement).textContent?.trim() ?? '',
    );
  }

  it('ofrece "Solo mujeres" solo a pasajeras', async () => {
    const auth = TestBed.inject(AuthService);
    auth.user.set({ ...ME, sex: 'female' });
    expect(chips(await create())).toContain('Solo mujeres');
    auth.user.set({ ...ME, sex: 'male' });
    expect(chips(await create())).not.toContain('Solo mujeres');
  });

  it('pide origen y destino antes de buscar', async () => {
    TestBed.inject(AuthService).user.set(ME);
    const fixture = await create();
    (fixture.nativeElement.querySelector('button[type=submit]') as HTMLButtonElement).click();
    await settle();
    fixture.detectChanges();
    expect(api.search).not.toHaveBeenCalled();
    expect(fixture.nativeElement.querySelector('[role=alert]')).not.toBeNull();
  });

  it('repite la ultima busqueda guardada y muestra los resultados', async () => {
    TestBed.inject(AuthService).user.set({ ...ME, sex: 'male' });
    localStorage.setItem(
      'cp.lastSearch',
      JSON.stringify({
        origin: CAMPUS,
        destination: TERMINAL,
        date: '2020-01-01',
        time: '07:00',
        seats: 2,
        pets: true,
        luggage: false,
        no_smoking: false,
        music: false,
        women_only: true,
      }),
    );
    const fixture = await create();
    const request = api.search.mock.calls[0][0];
    expect(request).toMatchObject({
      origin_place_id: 'p1',
      destination_place_id: 'p2',
      time: '07:00',
      seats: 2,
      pets: true,
      // Una busqueda guardada no puede filtrar solo mujeres para un pasajero.
      women_only: false,
    });
    // Una fecha vencida se sustituye por hoy.
    expect(request.date > '2020-01-01').toBe(true);

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Viajes encontrados: 1');
    expect(text).toContain('Sede Casona');
    expect(text).toContain('Laura Gomez');
    expect(text).not.toContain('ABC123');
    expect(fixture.nativeElement.querySelector('a[href="/viajes/t1"]')).not.toBeNull();
  });

  it('muestra un estado vacio cuando no hay viajes', async () => {
    TestBed.inject(AuthService).user.set(ME);
    api.search.mockResolvedValue([]);
    localStorage.setItem(
      'cp.lastSearch',
      JSON.stringify({
        origin: CAMPUS,
        destination: TERMINAL,
        date: '2099-01-01',
        time: '07:00',
        seats: 1,
      }),
    );
    const fixture = await create();
    expect(fixture.nativeElement.textContent).toContain('No encontramos viajes');
  });
});

describe('ResultCard', () => {
  it('muestra recogida, distancia a pie, conductor nuevo, serie y reglas', () => {
    TestBed.configureTestingModule({
      imports: [ResultCard, getTranslocoTestingModule()],
      providers: [provideRouter([])],
    });
    const fixture = TestBed.createComponent(ResultCard);
    fixture.componentRef.setInput('result', RESULT);
    fixture.detectChanges();
    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('A 120 m de tu punto');
    expect(text).toContain('Cupos: 3');
    expect(text).toContain('Conductor nuevo');
    expect(text).toContain('Mascotas: No permitido');
    expect(text).toContain('Spark');
  });
});
