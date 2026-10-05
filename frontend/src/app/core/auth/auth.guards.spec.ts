import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { Me } from './auth.models';
import { homeFor } from './auth.guards';
import { AuthService } from './auth.service';
import { ME } from '../../../testing/auth-fixtures';
import { getTranslocoTestingModule } from '../../../testing/transloco-testing';
import { routes } from '../../app.routes';

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

describe('navegacion con las rutas reales', () => {
  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      imports: [getTranslocoTestingModule()],
      providers: [provideRouter(routes), provideHttpClient(), provideHttpClientTesting()],
    });
  });

  // Regresion: el guard de invitados redirigia a casa y, como su grupo tiene path '', se
  // volvia a evaluar en esa misma navegacion sin fin (la pagina se congelaba al entrar).
  it('con sesion entra a la app y las pantallas de acceso llevan a casa', async () => {
    TestBed.inject(AuthService).user.set({ ...ME, role: 'passenger' });
    const router = TestBed.inject(Router);
    expect(await router.navigateByUrl('/perfil')).toBe(true);
    expect(router.url).toBe('/perfil');
    await router.navigateByUrl('/ingresar');
    expect(router.url).toBe('/buscar');
  });

  it('cada rol llega a su propia version de una ruta compartida', async () => {
    const auth = TestBed.inject(AuthService);
    const router = TestBed.inject(Router);
    auth.user.set({ ...ME, role: 'passenger' });
    await router.navigateByUrl('/mis-viajes');
    expect(router.url).toBe('/mis-viajes');
    // Una seccion de otro rol lleva a casa.
    await router.navigateByUrl('/solicitudes');
    expect(router.url).toBe('/buscar');
    auth.user.set({ ...ME, role: 'driver' });
    await router.navigateByUrl('/mis-viajes');
    expect(router.url).toBe('/mis-viajes');
  });

  it('sin sesion la app lleva a la bienvenida', async () => {
    const router = TestBed.inject(Router);
    await router.navigateByUrl('/perfil');
    expect(router.url).toBe('/bienvenida');
  });
});
