import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { AuthResult, Me } from './auth.models';
import { AuthService } from './auth.service';

export const ME: Me = {
  id: 'u1',
  email: 'laura@unipamplona.edu.co',
  full_name: 'Laura Prueba',
  sex: 'female',
  program: null,
  role: 'passenger',
  status: 'active',
  payment_note: null,
  preferred_language: 'es',
  theme_preference: 'system',
  last_login_at: null,
  document: null,
  pending_legal: [],
};

export function authenticated(user: Partial<Me> = {}): AuthResult {
  return {
    result: 'authenticated',
    access_token: 'token-1',
    expires_in: 900,
    user: { ...ME, ...user },
    challenge_id: null,
    email_hint: null,
    resend_after_seconds: null,
  };
}

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
