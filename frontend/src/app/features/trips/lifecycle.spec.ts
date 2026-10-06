import { DIALOG_DATA, DialogRef } from '@angular/cdk/dialog';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { Component, input } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { getTranslocoTestingModule } from '../../../testing/transloco-testing';
import { ME } from '../../../testing/auth-fixtures';
import { AuthService } from '../../core/auth/auth.service';
import { LocationSharingService } from '../../core/location/location-sharing.service';
import { RealtimeService } from '../../core/ws/realtime.service';
import { MapView } from '../../shared/map/map-view';
import { DialogService } from '../../shared/ui/dialog.service';
import { TrustedContacts } from '../profile/trusted-contacts';
import SharedTrip from '../share/shared-trip';
import { LifecycleApi, PublicTrip } from './lifecycle.api';
import { EmergencyDialog } from './safety-dialogs';
import { TripControl } from './trip-live';
import { Trip } from './trips.api';

async function settle(): Promise<void> {
  for (let i = 0; i < 10; i++) await Promise.resolve();
}

function text(element: HTMLElement): string {
  return element.textContent?.replace(/\s+/g, ' ') ?? '';
}

function button(element: HTMLElement, label: string): HTMLButtonElement {
  const found = Array.from(element.querySelectorAll('button')).find((b) =>
    b.textContent?.includes(label),
  );
  if (!found) throw new Error(`No hay boton "${label}"`);
  return found as HTMLButtonElement;
}

@Component({ selector: 'cp-map-view', template: '' })
class MapViewStub {
  readonly route = input<unknown>(null);
  readonly markers = input<unknown[]>([]);
  readonly label = input('');
}

const TRIP = {
  id: 't1',
  status: 'scheduled',
  driver: { id: ME.id, full_name: ME.full_name },
} as unknown as Trip;

describe('LocationSharingService', () => {
  let watcher: ((position: GeolocationPosition) => void) | null;
  let failure: ((error: GeolocationPositionError) => void) | null;
  let sent: Record<string, unknown>[];

  beforeEach(() => {
    vi.useFakeTimers();
    watcher = failure = null;
    sent = [];
    vi.stubGlobal('navigator', {
      ...navigator,
      geolocation: {
        watchPosition: (ok: typeof watcher, ko: typeof failure) => {
          watcher = ok;
          failure = ko;
          return 7;
        },
        clearWatch: vi.fn(),
      },
      wakeLock: {
        request: vi.fn().mockResolvedValue({ release: vi.fn().mockResolvedValue(undefined) }),
      },
    });
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        {
          provide: RealtimeService,
          useValue: { send: (m: Record<string, unknown>) => (sent.push(m), true) },
        },
      ],
    });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  const at = (lat: number) =>
    ({
      coords: { latitude: lat, longitude: -72.6, accuracy: 10, heading: null, speed: 5 },
    }) as GeolocationPosition;

  it('envia la ubicacion del viaje como mucho cada 5 segundos y mantiene la pantalla', async () => {
    const service = TestBed.inject(LocationSharingService);
    service.start('t1');
    await settle();
    expect(service.keepsScreenOn()).toBe(true);
    watcher!(at(7.38));
    watcher!(at(7.39));
    expect(sent).toEqual([
      {
        type: 'location.update',
        trip_id: 't1',
        lat: 7.38,
        lon: -72.6,
        accuracy: 10,
        heading: null,
        speed: 5,
      },
    ]);
    expect(service.status()).toBe('on');
    vi.advanceTimersByTime(5000);
    watcher!(at(7.4));
    expect(sent).toHaveLength(2);
  });

  it('sin permiso queda en denied y deja de seguir el GPS', () => {
    const service = TestBed.inject(LocationSharingService);
    service.start('t1');
    failure!({ code: 1, PERMISSION_DENIED: 1 } as GeolocationPositionError);
    expect(service.status()).toBe('denied');
    expect(service.tripId()).toBeNull();
  });
});

describe('TripControl', () => {
  let api: Record<string, ReturnType<typeof vi.fn>>;
  let sharing: {
    start: ReturnType<typeof vi.fn>;
    stop: ReturnType<typeof vi.fn>;
    tripId: () => null;
    status: () => string;
    keepsScreenOn: () => boolean;
  };

  beforeEach(() => {
    api = {
      start: vi.fn().mockResolvedValue({}),
      finish: vi
        .fn()
        .mockRejectedValueOnce({ code: 'PASSENGERS_UNMARKED', message: '', details: {} })
        .mockResolvedValue({}),
      tickets: vi.fn().mockResolvedValue([
        {
          id: 'k1',
          passenger_name: 'Ana Pasajera',
          code: 'CP-ABCD-EFGH',
          amount: 2000,
          paid_confirmed: false,
        },
      ]),
      markPaid: vi.fn().mockResolvedValue({
        id: 'k1',
        passenger_name: 'Ana Pasajera',
        code: 'CP-ABCD-EFGH',
        amount: 2000,
        paid_confirmed: true,
      }),
    };
    sharing = {
      start: vi.fn(),
      stop: vi.fn(),
      tripId: () => null,
      status: () => 'on',
      keepsScreenOn: () => false,
    };
    TestBed.configureTestingModule({
      imports: [TripControl, getTranslocoTestingModule()],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: LifecycleApi, useValue: api },
        { provide: LocationSharingService, useValue: sharing },
      ],
    });
    vi.spyOn(TestBed.inject(DialogService), 'confirm').mockResolvedValue(true);
  });

  async function control(status: string) {
    const fixture = TestBed.createComponent(TripControl);
    fixture.componentRef.setInput('trip', { ...TRIP, status });
    fixture.detectChanges();
    await settle();
    fixture.detectChanges();
    return fixture;
  }

  it('inicia el viaje y empieza a compartir la ubicacion', async () => {
    const fixture = await control('scheduled');
    const changed = vi.fn();
    fixture.componentInstance.changed.subscribe(changed);
    button(fixture.nativeElement, 'Iniciar viaje').click();
    await settle();
    expect(api['start']).toHaveBeenCalledWith('t1');
    expect(sharing.start).toHaveBeenCalledWith('t1');
    expect(changed).toHaveBeenCalled();
  });

  it('en curso retoma la ubicacion y no finaliza con pasajeros sin marcar', async () => {
    const fixture = await control('in_progress');
    expect(sharing.start).toHaveBeenCalledWith('t1');
    expect(text(fixture.nativeElement)).toContain('Compartiendo tu ubicación');
    button(fixture.nativeElement, 'Finalizar viaje').click();
    await settle();
    fixture.detectChanges();
    expect(text(fixture.nativeElement)).toContain('Marca a cada pasajero');
    button(fixture.nativeElement, 'Finalizar viaje').click();
    await settle();
    expect(sharing.stop).toHaveBeenCalled();
  });

  it('completado muestra los tickets y confirma el aporte', async () => {
    const fixture = await control('completed');
    expect(text(fixture.nativeElement)).toContain('CP-ABCD-EFGH');
    const box = fixture.nativeElement.querySelector('input[type=checkbox]') as HTMLInputElement;
    box.checked = true;
    box.dispatchEvent(new Event('change'));
    await settle();
    expect(api['markPaid']).toHaveBeenCalledWith('k1', true);
  });
});

describe('SharedTrip', () => {
  const PUBLIC: PublicTrip = {
    status: 'in_progress',
    departs_at: '2026-10-06T12:00:00Z',
    started_at: '2026-10-06T12:01:00Z',
    finished_at: null,
    arrives_at: '2026-10-06T12:11:00Z',
    geometry: [],
    stops: [
      { name: 'Ciudad Universitaria', lat: 7.387, lon: -72.65, kind: 'origin' },
      { name: 'Terminal', lat: 7.371, lon: -72.651, kind: 'destination' },
    ],
    vehicle: { type: 'car', brand: 'Chevrolet', model: 'Spark', color: 'Gris', plate: 'ABC123' },
    location: { lat: 7.38, lon: -72.65, at: '2026-10-06T12:05:00Z' },
    expires_at: '2026-10-06T12:41:00Z',
  };

  async function page(result: Promise<PublicTrip>) {
    TestBed.configureTestingModule({
      imports: [SharedTrip, getTranslocoTestingModule()],
      providers: [
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: LifecycleApi, useValue: { publicTrip: vi.fn().mockReturnValue(result) } },
      ],
    }).overrideComponent(SharedTrip, {
      remove: { imports: [MapView] },
      add: { imports: [MapViewStub] },
    });
    const fixture = TestBed.createComponent(SharedTrip);
    fixture.componentRef.setInput('token', 'tok');
    fixture.detectChanges();
    await settle();
    fixture.detectChanges();
    return fixture;
  }

  it('muestra vehiculo, placa y ubicacion; si el enlace vencio lo explica', async () => {
    const fixture = await page(Promise.resolve(PUBLIC));
    const element = fixture.nativeElement as HTMLElement;
    expect(text(element)).toContain('ABC123');
    expect(text(element)).toContain('Chevrolet Spark, Gris');
    expect(text(element)).toContain('Actualizada a las');
    const map = fixture.debugElement.query((d) => d.name === 'cp-map-view');
    expect(
      (map.componentInstance as MapViewStub).markers().map((m) => (m as { kind: string }).kind),
    ).toEqual(['origin', 'destination', 'vehicle']);
    TestBed.resetTestingModule();
    const gone = await page(Promise.reject(new Error('404')));
    expect(text(gone.nativeElement)).toContain('Este enlace ya no está disponible');
  });
});

describe('EmergencyDialog', () => {
  it('avisa con la ubicacion del telefono y muestra la confirmacion', async () => {
    vi.stubGlobal('navigator', {
      ...navigator,
      geolocation: {
        getCurrentPosition: (ok: (p: GeolocationPosition) => void) =>
          ok({ coords: { latitude: 7.38, longitude: -72.65 } } as GeolocationPosition),
      },
    });
    const api = {
      contacts: vi
        .fn()
        .mockResolvedValue([{ id: 'c1', name: 'Mama', phone: '3001234567', relationship: null }]),
      emergency: vi.fn().mockResolvedValue({
        emergency: { id: 'e1', created_at: '2026-10-06T12:05:00Z' },
        phone: '123',
      }),
    };
    TestBed.configureTestingModule({
      imports: [EmergencyDialog, getTranslocoTestingModule()],
      providers: [
        { provide: DIALOG_DATA, useValue: { tripId: 't1' } },
        { provide: DialogRef, useValue: { close: vi.fn() } },
        { provide: LifecycleApi, useValue: api },
      ],
    });
    const fixture = TestBed.createComponent(EmergencyDialog);
    fixture.detectChanges();
    await settle();
    fixture.detectChanges();
    const element = fixture.nativeElement as HTMLElement;
    expect(element.querySelector('a[href="tel:123"]')).not.toBeNull();
    expect(element.querySelector('a[href="tel:3001234567"]')).not.toBeNull();
    (element.querySelector('form') as HTMLFormElement).dispatchEvent(
      new Event('submit', { cancelable: true }),
    );
    await settle();
    fixture.detectChanges();
    expect(api.emergency).toHaveBeenCalledWith('t1', { lat: 7.38, lon: -72.65 });
    expect(text(element)).toContain('Aviso enviado');
    vi.unstubAllGlobals();
  });
});

describe('TrustedContacts', () => {
  it('agrega contactos y avisa cuando se llega al maximo', async () => {
    const five = Array.from({ length: 5 }, (_, n) => ({
      id: `c${n}`,
      name: `Contacto ${n}`,
      phone: `30000000${n}`,
      relationship: null,
    }));
    const api = {
      contacts: vi.fn().mockResolvedValueOnce([]).mockResolvedValueOnce(five),
      addContact: vi.fn().mockResolvedValue(five[0]),
    };
    TestBed.configureTestingModule({
      imports: [TrustedContacts, getTranslocoTestingModule()],
      providers: [{ provide: LifecycleApi, useValue: api }],
    });
    TestBed.inject(AuthService).user.set(ME);
    const fixture = TestBed.createComponent(TrustedContacts);
    fixture.detectChanges();
    await settle();
    fixture.detectChanges();
    const element = fixture.nativeElement as HTMLElement;
    const inputs = element.querySelectorAll('input');
    inputs[0].value = 'Mama';
    inputs[0].dispatchEvent(new Event('input'));
    inputs[1].value = '+57 300 123 4567';
    inputs[1].dispatchEvent(new Event('input'));
    (element.querySelector('form') as HTMLFormElement).dispatchEvent(new Event('submit'));
    await settle();
    fixture.detectChanges();
    expect(api.addContact).toHaveBeenCalledWith({
      name: 'Mama',
      phone: '+57 300 123 4567',
      relationship: null,
    });
    expect(text(element)).toContain('Ya tienes los 5 contactos permitidos');
  });
});
