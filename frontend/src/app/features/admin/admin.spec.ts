import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Route, provideRouter } from '@angular/router';
import { Subject, filter } from 'rxjs';
import { getTranslocoTestingModule } from '../../../testing/transloco-testing';
import { routes } from '../../app.routes';
import { Me } from '../../core/auth/auth.models';
import { AuthService } from '../../core/auth/auth.service';
import { LiveEvent, RealtimeService } from '../../core/ws/realtime.service';
import { DialogService } from '../../shared/ui/dialog.service';
import { AdminApi, AdminUserDetail, Emergency } from './admin.api';
import AdminEmergencies from './emergencies';
import { fromDraft, toDraft } from './settings/parameters-panel';
import { AdminUserDetailPage } from './users';

async function settle(): Promise<void> {
  for (let i = 0; i < 6; i++) await Promise.resolve();
}

function detail(role: AdminUserDetail['role'], id = 'target'): AdminUserDetail {
  return {
    id,
    email: 'persona@unipamplona.edu.co',
    full_name: 'Persona Prueba',
    role,
    status: 'active',
    program: null,
    created_at: '2026-08-01T12:00:00Z',
    last_login_at: null,
    sex: 'female',
    document_status: 'approved',
    license_status: null,
    license_expires_on: null,
    rating: 4.5,
    rating_count: 3,
    trips_as_driver: 0,
    trips_as_passenger: 4,
    driver_cancellations: 0,
    passenger_no_shows: 1,
    active_bookings: 1,
    upcoming_trips: 0,
    suspensions: [],
    active_ban: null,
  };
}

function emergency(id: string, handled = false): Emergency {
  return {
    id,
    trip_id: 't1',
    trip_status: 'in_progress',
    route: 'Sede principal → Centro',
    user_id: 'u1',
    user_name: 'Pasajera',
    lat: 7.37,
    lon: -72.64,
    note: null,
    created_at: `2026-10-06T1${id.length}:00:00Z`,
    handled_at: handled ? '2026-10-06T15:00:00Z' : null,
    resolution: handled ? 'Llamamos a la pasajera' : null,
  };
}

describe('AdminApi', () => {
  it('omite los filtros vacios en la consulta', async () => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    const api = TestBed.inject(AdminApi);
    const http = TestBed.inject(HttpTestingController);

    const pending = api.users({ q: '', role: 'driver', status: '', cursor: null });
    const req = http.expectOne((r) => r.url === '/api/v1/admin/users');
    expect(req.request.params.keys().sort()).toEqual(['limit', 'role']);
    req.flush({ items: [], next_cursor: null });
    await pending;
  });
});

describe('Rutas del panel', () => {
  const admin = routes.flatMap((r) => r.children ?? []).find((r) => r.path === 'admin') as Route;

  it('todo el panel exige rol de administrador y la configuracion, superadmin', () => {
    expect(admin.canMatch).toHaveLength(1);
    const paths = (admin.children ?? []).map((r) => r.path);
    expect(paths).toEqual([
      '',
      'aprobaciones',
      'usuarios',
      'usuarios/:id',
      'viajes',
      'viajes/:id',
      'emergencias',
      'moderacion',
      'configuracion',
    ]);
    const settings = admin.children?.find((r) => r.path === 'configuracion');
    expect(settings?.canMatch).toHaveLength(1);
    expect(admin.children?.filter((r) => r.canMatch)).toHaveLength(1);
  });
});

describe('Parametros', () => {
  it('convierte el borrador al tipo del valor original', () => {
    expect(fromDraft(3, '5')).toBe(5);
    expect(Number.isNaN(fromDraft(3, ''))).toBe(true);
    expect(fromDraft(true, 'false')).toBe(false);
    expect(fromDraft([7, 'semester'], '[14, "semester"]')).toEqual([14, 'semester']);
    expect(toDraft({ a: 1 })).toBe('{\n  "a": 1\n}');
    expect(() => fromDraft([1], '[1,')).toThrow(SyntaxError);
  });
});

describe('Ficha de usuario', () => {
  let api: { user: ReturnType<typeof vi.fn> };

  function render(me: Me['role'], target: AdminUserDetail) {
    api = { user: vi.fn().mockResolvedValue(target) };
    TestBed.configureTestingModule({
      imports: [AdminUserDetailPage, getTranslocoTestingModule()],
      providers: [provideRouter([]), { provide: AdminApi, useValue: api }],
    });
    TestBed.inject(AuthService).user.set({ id: 'me', role: me } as Me);
    const fixture = TestBed.createComponent(AdminUserDetailPage);
    fixture.componentRef.setInput('id', target.id);
    return fixture;
  }

  async function actions(me: Me['role'], target: AdminUserDetail): Promise<string[]> {
    const fixture = render(me, target);
    fixture.detectChanges();
    await settle();
    fixture.detectChanges();
    return [...fixture.nativeElement.querySelectorAll('button')].map((b: HTMLElement) =>
      b.textContent!.trim(),
    );
  }

  it('el administrador gestiona pasajeros pero no cambia roles', async () => {
    const buttons = await actions('admin', detail('passenger'));
    expect(buttons).toContain('Suspender');
    expect(buttons).toContain('Bloquear');
    expect(buttons).not.toContain('Guardar rol');
  });

  it('el administrador no ve acciones sobre otro administrador', async () => {
    expect(await actions('admin', detail('admin'))).toEqual([]);
  });

  it('el superadmin gestiona administradores y cambia roles', async () => {
    const buttons = await actions('superadmin', detail('admin'));
    expect(buttons).toContain('Suspender');
    expect(buttons).toContain('Guardar rol');
  });

  it('nadie actua sobre un superadmin ni sobre si mismo', async () => {
    expect(await actions('superadmin', detail('superadmin'))).toEqual([]);
    TestBed.resetTestingModule();
    expect(await actions('superadmin', detail('admin', 'me'))).toEqual([]);
  });
});

describe('Emergencias', () => {
  let live: Subject<LiveEvent>;
  let api: { emergencies: ReturnType<typeof vi.fn>; handleEmergency: ReturnType<typeof vi.fn> };
  let dialogs: { open: ReturnType<typeof vi.fn> };

  beforeEach(() => {
    live = new Subject<LiveEvent>();
    api = {
      emergencies: vi.fn().mockResolvedValue([emergency('a')]),
      handleEmergency: vi.fn().mockResolvedValue(emergency('a', true)),
    };
    dialogs = { open: vi.fn().mockReturnValue({ closed: new Subject<string>() }) };
    TestBed.configureTestingModule({
      imports: [AdminEmergencies, getTranslocoTestingModule()],
      providers: [
        provideRouter([]),
        { provide: AdminApi, useValue: api },
        { provide: DialogService, useValue: dialogs },
        {
          provide: RealtimeService,
          useValue: {
            on: (...types: string[]) => live.pipe(filter((e) => types.includes(e.type))),
          },
        },
      ],
    });
  });

  function names(fixture: { nativeElement: HTMLElement }): string[] {
    return [...fixture.nativeElement.querySelectorAll('li:has(cp-status-badge)')].map((li) =>
      li.querySelector('cp-status-badge')!.textContent!.trim(),
    );
  }

  it('agrega las nuevas en tiempo real y quita las atendidas', async () => {
    const fixture = TestBed.createComponent(AdminEmergencies);
    await settle();
    fixture.detectChanges();
    expect(names(fixture)).toEqual(['Abierta']);

    live.next({ type: 'emergency', emergency: emergency('bb') });
    fixture.detectChanges();
    expect(names(fixture)).toEqual(['Abierta', 'Abierta']);

    live.next({ type: 'emergency.handled', emergency: emergency('a', true) });
    fixture.detectChanges();
    expect(names(fixture)).toEqual(['Abierta']);
  });

  it('atender exige escribir la resolucion', async () => {
    const closed = new Subject<string>();
    dialogs.open.mockReturnValue({ closed });
    const fixture = TestBed.createComponent(AdminEmergencies);
    await settle();
    fixture.detectChanges();

    const handle = [...fixture.nativeElement.querySelectorAll('button')].find((b: HTMLElement) =>
      b.textContent!.includes('Marcar como atendida'),
    ) as HTMLButtonElement;
    handle.click();
    closed.next('Llamamos a la pasajera');
    closed.complete();
    await settle();
    fixture.detectChanges();

    expect(api.handleEmergency).toHaveBeenCalledWith('a', 'Llamamos a la pasajera');
    expect(fixture.nativeElement.querySelectorAll('cp-status-badge')).toHaveLength(0);
    expect(fixture.nativeElement.textContent).toContain('No hay emergencias abiertas');
  });
});
