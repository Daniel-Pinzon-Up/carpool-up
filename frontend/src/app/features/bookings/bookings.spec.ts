import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of } from 'rxjs';
import { getTranslocoTestingModule } from '../../../testing/transloco-testing';
import { ME } from '../../../testing/auth-fixtures';
import { AuthService } from '../../core/auth/auth.service';
import { DialogService } from '../../shared/ui/dialog.service';
import { Trip } from '../trips/trips.api';
import { BookingActions } from './booking-actions';
import { BookingPanel } from './booking-panel';
import { Booking, BookingsApi, Inbox } from './bookings.api';
import DriverInbox from './driver-inbox';
import PassengerTrips from './passenger-trips';
import { subscriptionEnd } from './subscribe-panel';

async function settle(): Promise<void> {
  for (let i = 0; i < 10; i++) await Promise.resolve();
}

const VEHICLE = {
  id: 'v1',
  type: 'car' as const,
  brand: 'Chevrolet',
  model: 'Spark',
  color: 'Gris',
  has_photo: false,
  plate: null,
};

const TRIP: Trip = {
  id: 't1',
  series_id: null,
  status: 'scheduled',
  departs_at: '2099-10-06T12:00:00Z',
  arrives_at: '2099-10-06T12:10:00Z',
  seats_total: 3,
  price_per_seat: 2000,
  origin: 'Ciudad Universitaria',
  destination: 'Terminal',
  stop_count: 0,
  vehicle: VEHICLE,
  editable: false,
  seats_available: 3,
  pending_requests: 0,
  geometry: [],
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
      eta: '2099-10-06T12:00:00Z',
    },
    {
      position: 1,
      kind: 'destination',
      place_id: 'b',
      name: 'Terminal',
      lat: 7.3712,
      lon: -72.6512,
      eta: '2099-10-06T12:10:00Z',
    },
  ],
  rules: [],
  driver: { id: 'd1', full_name: 'Carlos Ruiz' },
  cancel_reason: null,
  cancelled_at: null,
  passengers: [],
  payment_note: null,
  my_booking: null,
  my_waitlist: null,
  chat_id: null,
};

const BOOKING: Booking = {
  id: 'b1',
  trip: {
    id: 't1',
    series_id: null,
    status: 'scheduled',
    departs_at: TRIP.departs_at,
    arrives_at: TRIP.arrives_at,
    origin: TRIP.origin,
    destination: TRIP.destination,
    price_per_seat: 2000,
    driver: TRIP.driver,
    vehicle: { ...VEHICLE, plate: 'ABC123' },
  },
  passenger: {
    id: 'p1',
    full_name: 'Ana Pasajera',
    program: 'Ingeniería de Sistemas',
    rating: null,
    trips_as_passenger: 4,
  },
  subscription_id: null,
  seats: 2,
  amount: 4000,
  status: 'accepted',
  pickup: {
    place_id: 'a',
    place_name: 'Ciudad Universitaria',
    kind: 'stop',
    name: 'Ciudad Universitaria',
    lat: 7.387,
    lon: -72.6495,
    eta: TRIP.departs_at,
    walk_m: 0,
  },
  dropoff: {
    place_id: 'b',
    place_name: 'Terminal',
    kind: 'stop',
    name: 'Terminal',
    lat: 7.3712,
    lon: -72.6512,
    eta: TRIP.arrives_at,
    walk_m: 0,
  },
  preferences: { pets: false, luggage: true, no_smoking: false, music: false },
  expires_at: TRIP.departs_at,
  penalty_free: false,
  free_cancel: true,
  created_at: '2099-10-01T12:00:00Z',
  decided_at: null,
  cancelled_at: null,
  cancel_reason: null,
  cancellation: null,
  payment_note: 'Nequi 300 000 0000',
};

function texts(element: HTMLElement): string {
  return element.textContent?.replace(/\s+/g, ' ') ?? '';
}

function button(element: HTMLElement, label: string): HTMLButtonElement {
  const found = Array.from(element.querySelectorAll('button')).find((b) =>
    b.textContent?.includes(label),
  );
  if (!found) throw new Error(`No hay boton "${label}"`);
  return found as HTMLButtonElement;
}

describe('subscriptionEnd', () => {
  it('cubre los dias pedidos sin pasar del final de la serie', () => {
    expect(subscriptionEnd('2026-10-05', 8, '2026-12-01')).toBe('2026-10-12');
    expect(subscriptionEnd('2026-11-28', 15, '2026-12-01')).toBe('2026-12-01');
    expect(subscriptionEnd('2026-10-05', 'series', '2026-12-01')).toBe('2026-12-01');
  });
});

describe('BookingPanel', () => {
  let api: Record<string, ReturnType<typeof vi.fn>>;

  beforeEach(() => {
    api = {
      request: vi.fn().mockResolvedValue(BOOKING),
      joinWaitlist: vi.fn().mockResolvedValue({}),
      confirmOffer: vi.fn().mockResolvedValue({}),
      declineOffer: vi.fn().mockResolvedValue({}),
    };
    TestBed.configureTestingModule({
      imports: [BookingPanel, getTranslocoTestingModule()],
      providers: [
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: BookingsApi, useValue: api },
      ],
    });
    TestBed.inject(AuthService).user.set(ME);
  });

  async function create(trip: Trip, searched = false) {
    const fixture = TestBed.createComponent(BookingPanel);
    fixture.componentRef.setInput('trip', trip);
    if (searched) {
      fixture.componentRef.setInput('searched', {
        pickup: { place_id: 'pin', name: 'Mi casa', kind: 'custom', lat: 7.38, lon: -72.648 },
        dropoff: { place_id: 'b', name: 'Terminal', kind: 'landmark', lat: 7.3712, lon: -72.6512 },
      });
    }
    fixture.detectChanges();
    await settle();
    fixture.detectChanges();
    return fixture;
  }

  it('solicita cupo con los lugares de la busqueda y avisa que no aparta el puesto', async () => {
    const fixture = await create(TRIP, true);
    const element = fixture.nativeElement as HTMLElement;
    expect(texts(element)).toContain('Mi punto: Mi casa');
    expect(texts(element)).toContain('Mientras tanto no se aparta el cupo');
    button(element, 'Solicitar cupo').click();
    await settle();
    expect(api['request']).toHaveBeenCalledWith('t1', {
      seats: 1,
      pickup_place_id: 'pin',
      dropoff_place_id: 'b',
      preferences: { pets: false, luggage: false, no_smoking: false, music: false },
    });
  });

  it('con el viaje lleno ofrece la lista de espera', async () => {
    const fixture = await create({ ...TRIP, seats_available: 0 });
    const element = fixture.nativeElement as HTMLElement;
    button(element, 'Anotarme en la lista de espera').click();
    await settle();
    expect(api['joinWaitlist']).toHaveBeenCalled();
    expect(api['request']).not.toHaveBeenCalled();
  });

  it('muestra la reserva aceptada y la oferta de la lista de espera', async () => {
    const accepted = await create({
      ...TRIP,
      my_booking: {
        id: 'b1',
        status: 'accepted',
        seats: 1,
        pickup_name: 'Ciudad Universitaria',
        pickup_eta: TRIP.departs_at,
        dropoff_name: null,
        dropoff_eta: TRIP.arrives_at,
      },
    });
    expect(texts(accepted.nativeElement)).toContain('Aceptada');
    expect(texts(accepted.nativeElement)).toContain('Punto en la ruta');
    expect(texts(accepted.nativeElement)).toContain('Cancelar reserva');

    const offered = await create({
      ...TRIP,
      seats_available: 1,
      my_waitlist: {
        id: 'w1',
        status: 'offered',
        seats: 1,
        offer_expires_at: '2099-10-06T11:00:00Z',
      },
    });
    button(offered.nativeElement, 'Quiero el cupo').click();
    await settle();
    expect(api['confirmOffer']).toHaveBeenCalledWith('w1');
  });

  it('un viaje solo para mujeres no se ofrece a otros pasajeros', async () => {
    TestBed.inject(AuthService).user.set({ ...ME, sex: 'male' });
    const fixture = await create({ ...TRIP, rules: [{ kind: 'women_only', value: 'allowed' }] });
    expect(texts(fixture.nativeElement)).toContain('Este viaje es solo para mujeres');
    expect(fixture.nativeElement.querySelector('form')).toBeNull();
  });
});

describe('BookingActions.cancel', () => {
  it('pide el motivo cuando el viaje esta cerca y crea la solicitud', async () => {
    const api = {
      cancel: vi
        .fn()
        .mockRejectedValueOnce({ code: 'CANCEL_REASON_REQUIRED', message: '', details: {} })
        .mockResolvedValueOnce({ ...BOOKING, status: 'cancel_requested' }),
    };
    TestBed.configureTestingModule({
      imports: [getTranslocoTestingModule()],
      providers: [{ provide: BookingsApi, useValue: api }],
    });
    const dialogs = TestBed.inject(DialogService);
    vi.spyOn(dialogs, 'confirm').mockResolvedValue(true);
    vi.spyOn(dialogs, 'open').mockReturnValue({
      closed: of({ reason: 'Me enferme' }),
    } as never);
    const result = await TestBed.inject(BookingActions).cancel('b1');
    expect(api.cancel).toHaveBeenNthCalledWith(1, 'b1', null);
    expect(api.cancel).toHaveBeenNthCalledWith(2, 'b1', 'Me enferme');
    expect(result?.status).toBe('cancel_requested');
  });
});

describe('DriverInbox', () => {
  it('lista solicitudes con el perfil del pasajero y las acepta', async () => {
    const inbox: Inbox = {
      bookings: [{ ...BOOKING, status: 'requested', payment_note: null }],
      cancellations: [],
      subscriptions: [],
    };
    const api = {
      inbox: vi
        .fn()
        .mockResolvedValueOnce(inbox)
        .mockResolvedValueOnce({ bookings: [], cancellations: [], subscriptions: [] }),
      accept: vi.fn().mockResolvedValue(BOOKING),
    };
    TestBed.configureTestingModule({
      imports: [DriverInbox, getTranslocoTestingModule()],
      providers: [provideRouter([]), { provide: BookingsApi, useValue: api }],
    });
    const fixture = TestBed.createComponent(DriverInbox);
    fixture.detectChanges();
    await settle();
    fixture.detectChanges();
    const element = fixture.nativeElement as HTMLElement;
    expect(texts(element)).toContain('Reservas por aprobar (1)');
    expect(texts(element)).toContain('Ana Pasajera');
    expect(texts(element)).toContain('Ingeniería de Sistemas');
    expect(texts(element)).toContain('Llevo equipaje grande');
    expect(texts(element)).not.toContain('@');

    button(element, 'Aceptar').click();
    await settle();
    fixture.detectChanges();
    expect(api.accept).toHaveBeenCalledWith('b1');
    expect(texts(element)).toContain('No tienes solicitudes pendientes');
  });
});

describe('PassengerTrips', () => {
  it('muestra los proximos viajes con placa y datos de pago una vez aceptado', async () => {
    const api = {
      mine: vi.fn().mockResolvedValue({ items: [BOOKING], next_cursor: null }),
      mySubscriptions: vi.fn().mockResolvedValue([]),
    };
    TestBed.configureTestingModule({
      imports: [PassengerTrips, getTranslocoTestingModule()],
      providers: [provideRouter([]), { provide: BookingsApi, useValue: api }],
    });
    const fixture = TestBed.createComponent(PassengerTrips);
    fixture.detectChanges();
    await settle();
    fixture.detectChanges();
    const element = fixture.nativeElement as HTMLElement;
    expect(api.mine).toHaveBeenCalledWith('upcoming');
    expect(texts(element)).toContain('ABC123');
    expect(texts(element)).toContain('Nequi 300 000 0000');
    expect(element.querySelector('a[href="/viajes/t1"]')).not.toBeNull();

    const seriesTab = Array.from(element.querySelectorAll('[role=tab]')).find((tab) =>
      tab.textContent?.includes('Series'),
    ) as HTMLButtonElement;
    seriesTab.click();
    fixture.detectChanges();
    await settle();
    fixture.detectChanges();
    expect(api.mySubscriptions).toHaveBeenCalled();
    expect(texts(element)).toContain('No te has unido a ninguna serie');
  });
});
