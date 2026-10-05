import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { authInterceptor } from './auth.interceptor';
import { authenticated } from '../../../testing/auth-fixtures';
import { AuthService } from './auth.service';

describe('authInterceptor', () => {
  let http: HttpClient;
  let backend: HttpTestingController;
  let auth: AuthService;

  beforeEach(async () => {
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    http = TestBed.inject(HttpClient);
    backend = TestBed.inject(HttpTestingController);
    auth = TestBed.inject(AuthService);
    const login = auth.login('a@unipamplona.edu.co', 'x');
    backend.expectOne('/api/v1/auth/login').flush(authenticated());
    await login;
  });

  afterEach(() => backend.verify());

  it('adjunta el token solo a la API', () => {
    void firstValueFrom(http.get('/api/v1/users/me'));
    expect(backend.expectOne('/api/v1/users/me').request.headers.get('Authorization')).toBe(
      'Bearer token-1',
    );
    void firstValueFrom(http.get('/i18n/es.json'));
    expect(backend.expectOne('/i18n/es.json').request.headers.has('Authorization')).toBe(false);
  });

  it('ante un 401 renueva una vez y repite con el token nuevo', async () => {
    const result = firstValueFrom(http.get<{ ok: boolean }>('/api/v1/users/me'));
    backend
      .expectOne('/api/v1/users/me')
      .flush({ code: 'UNAUTHORIZED' }, { status: 401, statusText: 'Unauthorized' });
    await Promise.resolve();
    backend
      .expectOne('/api/v1/auth/refresh')
      .flush({ ...authenticated(), access_token: 'token-2' });
    await new Promise((resolve) => setTimeout(resolve));
    const retry = backend.expectOne('/api/v1/users/me');
    expect(retry.request.headers.get('Authorization')).toBe('Bearer token-2');
    retry.flush({ ok: true });
    expect(await result).toEqual({ ok: true });
  });

  it('si la renovacion falla cierra la sesion y va a /ingresar', async () => {
    const navigate = vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);
    const result = firstValueFrom(http.get('/api/v1/users/me'));
    backend
      .expectOne('/api/v1/users/me')
      .flush({ code: 'UNAUTHORIZED' }, { status: 401, statusText: 'Unauthorized' });
    await Promise.resolve();
    backend
      .expectOne('/api/v1/auth/refresh')
      .flush({ code: 'REFRESH_INVALID' }, { status: 401, statusText: 'Unauthorized' });
    await expect(result).rejects.toBeTruthy();
    expect(auth.isAuthenticated()).toBe(false);
    expect(navigate).toHaveBeenCalledWith(['/ingresar']);
  });

  it('no reintenta el login', async () => {
    const result = firstValueFrom(http.post('/api/v1/auth/login', {}));
    backend
      .expectOne('/api/v1/auth/login')
      .flush({ code: 'INVALID_CREDENTIALS' }, { status: 401, statusText: 'Unauthorized' });
    await expect(result).rejects.toBeTruthy();
    backend.expectNone('/api/v1/auth/refresh');
  });
});
