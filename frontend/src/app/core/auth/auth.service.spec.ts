import { HttpErrorResponse, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { AuthResult } from './auth.models';
import { AuthService, isSessionRejected } from './auth.service';
import { errorInterceptor } from '../http/error.interceptor';
import { authenticated } from '../../../testing/auth-fixtures';

function challenge(result: AuthResult['result']): AuthResult {
  return {
    result,
    access_token: null,
    expires_in: null,
    user: null,
    challenge_id: 'ch-1',
    email_hint: 'la***@unipamplona.edu.co',
    resend_after_seconds: 60,
  };
}

describe('AuthService', () => {
  let service: AuthService;
  let http: HttpTestingController;

  beforeEach(() => {
    sessionStorage.clear();
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(AuthService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('guarda token y usuario al iniciar sesion sin segundo factor', async () => {
    const login = service.login('laura@unipamplona.edu.co', 'clave-segura-123');
    http.expectOne('/api/v1/auth/login').flush(authenticated());
    await login;
    expect(service.accessToken()).toBe('token-1');
    expect(service.isActive()).toBe(true);
    expect(localStorage.length).toBe(0); // el token nunca se persiste
  });

  it('guarda el desafio y verifica el codigo en el endpoint correcto', async () => {
    const login = service.login('laura@unipamplona.edu.co', 'clave-segura-123');
    http.expectOne('/api/v1/auth/login').flush(challenge('two_factor_required'));
    await login;
    expect(service.challenge()?.purpose).toBe('two_factor');
    expect(service.isAuthenticated()).toBe(false);
    expect(JSON.parse(sessionStorage.getItem('cp.challenge') ?? '{}').id).toBe('ch-1');

    const verify = service.verifyCode('123456');
    const request = http.expectOne('/api/v1/auth/2fa/verify');
    expect(request.request.body).toEqual({ challenge_id: 'ch-1', code: '123456' });
    request.flush(authenticated());
    await verify;
    expect(service.challenge()).toBeNull();
    expect(service.isAuthenticated()).toBe(true);
  });

  it('el registro deja un desafio de verificacion de correo', async () => {
    const register = service.register(new FormData());
    http.expectOne('/api/v1/auth/register').flush(challenge('email_verification_required'));
    await register;
    expect(service.challenge()?.purpose).toBe('email_verification');
  });

  it('peticiones simultaneas comparten una sola renovacion', async () => {
    const first = service.refresh();
    const second = service.refresh();
    const requests = http.match('/api/v1/auth/refresh');
    expect(requests).toHaveLength(1);
    requests[0].flush(authenticated());
    await Promise.all([first, second]);
    expect(service.accessToken()).toBe('token-1');
  });

  it('restore no falla si no hay sesion', async () => {
    const restore = service.restore();
    http
      .expectOne('/api/v1/auth/refresh')
      .flush({ code: 'REFRESH_INVALID' }, { status: 401, statusText: 'Unauthorized' });
    await restore;
    expect(service.isAuthenticated()).toBe(false);
  });

  it('restore reintenta ante un error pasajero y recupera la sesion', async () => {
    vi.useFakeTimers();
    try {
      const restore = service.restore();
      http
        .expectOne('/api/v1/auth/refresh')
        .flush({ code: 'RATE_LIMITED' }, { status: 429, statusText: 'Too Many Requests' });
      await vi.advanceTimersByTimeAsync(1000);
      http.expectOne('/api/v1/auth/refresh').error(new ProgressEvent('error'));
      await vi.advanceTimersByTimeAsync(2000);
      http.expectOne('/api/v1/auth/refresh').flush(authenticated());
      await restore;
      expect(service.isAuthenticated()).toBe(true);
    } finally {
      vi.useRealTimers();
    }
  });

  it('restore se rinde tras varios fallos pasajeros sin colgar la app', async () => {
    vi.useFakeTimers();
    try {
      const restore = service.restore();
      for (const delay of [1000, 2000, 4000]) {
        http
          .expectOne('/api/v1/auth/refresh')
          .flush({ code: 'INTERNAL_ERROR' }, { status: 503, statusText: 'Unavailable' });
        await vi.advanceTimersByTimeAsync(delay);
      }
      http
        .expectOne('/api/v1/auth/refresh')
        .flush({ code: 'INTERNAL_ERROR' }, { status: 503, statusText: 'Unavailable' });
      await restore;
      expect(service.isAuthenticated()).toBe(false);
    } finally {
      vi.useRealTimers();
    }
  });

  it('logout limpia la sesion aunque falle la red', async () => {
    const login = service.login('a@unipamplona.edu.co', 'x');
    http.expectOne('/api/v1/auth/login').flush(authenticated());
    await login;
    const logout = service.logout();
    http.expectOne('/api/v1/auth/logout').error(new ProgressEvent('error'));
    await expect(logout).rejects.toBeTruthy();
    expect(service.accessToken()).toBeNull();
    expect(service.user()).toBeNull();
  });
});

describe('isSessionRejected', () => {
  it('reconoce el 401 crudo y el ya normalizado por errorInterceptor', () => {
    expect(isSessionRejected(new HttpErrorResponse({ status: 401 }))).toBe(true);
    expect(
      isSessionRejected({ code: 'REFRESH_INVALID', message: '', details: {}, status: 401 }),
    ).toBe(true);
    expect(isSessionRejected({ code: 'NETWORK_ERROR', message: '', details: {}, status: 0 })).toBe(
      false,
    );
    expect(isSessionRejected(null)).toBe(false);
  });

  it('restore no reintenta ni demora el arranque cuando no hay sesion', async () => {
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([errorInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    const service = TestBed.inject(AuthService);
    const http = TestBed.inject(HttpTestingController);
    const restore = service.restore();
    http
      .expectOne('/api/v1/auth/refresh')
      .flush({ code: 'REFRESH_INVALID' }, { status: 401, statusText: 'Unauthorized' });
    await restore;
    expect(service.accessToken()).toBeNull();
    http.verify();
  });
});
