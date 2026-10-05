import { TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { Me } from './auth.models';
import { homeFor } from './auth.guards';
import { AuthService } from './auth.service';
import { ME } from '../../../testing/auth-fixtures';

describe('homeFor', () => {
  let auth: AuthService;
  let router: Router;

  const path = () => router.serializeUrl(homeFor(auth, router));
  const as = (user: Partial<Me> | null) => auth.user.set(user ? { ...ME, ...user } : null);

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({ providers: [provideRouter([])] });
    auth = TestBed.inject(AuthService);
    router = TestBed.inject(Router);
  });

  it('sin sesion muestra la bienvenida la primera vez y luego el login', () => {
    as(null);
    expect(path()).toBe('/bienvenida');
    localStorage.setItem('cp.onboarded', 'true');
    expect(path()).toBe('/ingresar');
  });

  it('cuentas no activas van a su estado', () => {
    for (const status of ['pending_approval', 'suspended'] as const) {
      as({ status });
      expect(path()).toBe('/cuenta/estado');
    }
  });

  it('terminos pendientes tienen prioridad', () => {
    as({ pending_legal: [{ id: 'd1', kind: 'terms', version: '2.0', language: 'es' }] });
    expect(path()).toBe('/cuenta/terminos');
  });

  it('cada rol activo va a su inicio', () => {
    const homes = {
      passenger: '/buscar',
      driver: '/inicio',
      admin: '/admin',
      superadmin: '/admin',
    };
    for (const [role, home] of Object.entries(homes)) {
      as({ role: role as Me['role'] });
      expect(path()).toBe(home);
    }
  });
});
