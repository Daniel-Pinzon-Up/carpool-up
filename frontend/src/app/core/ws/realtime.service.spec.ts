import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { ME } from '../../../testing/auth-fixtures';
import { AuthService } from '../auth/auth.service';
import { LiveEvent, RealtimeService } from './realtime.service';

/** WebSocket de mentira: guarda lo enviado y deja simular apertura, mensajes y cierre. */
class FakeSocket {
  static instances: FakeSocket[] = [];
  static readonly OPEN = 1;
  readyState = 0;
  sent: unknown[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onclose: ((event: { code: number }) => void) | null = null;

  constructor(readonly url: string) {
    FakeSocket.instances.push(this);
  }

  send(data: string): void {
    this.sent.push(JSON.parse(data));
  }

  close(): void {
    this.readyState = 3;
  }

  open(): void {
    this.readyState = 1;
    this.onopen?.();
  }

  emit(event: LiveEvent): void {
    this.onmessage?.({ data: JSON.stringify(event) });
  }

  drop(code = 1006): void {
    this.readyState = 3;
    this.onclose?.({ code });
  }
}

describe('RealtimeService', () => {
  let auth: AuthService;
  let service: RealtimeService;
  const last = () => FakeSocket.instances.at(-1)!;

  beforeEach(() => {
    vi.useFakeTimers();
    FakeSocket.instances = [];
    vi.stubGlobal('WebSocket', FakeSocket);
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    auth = TestBed.inject(AuthService);
    service = TestBed.inject(RealtimeService);
    vi.spyOn(auth, 'accessToken').mockReturnValue('token-1');
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  function signIn(): void {
    auth.user.set(ME);
    TestBed.tick();
  }

  it('se conecta con sesion, se autentica con el primer mensaje y entrega eventos', () => {
    expect(FakeSocket.instances).toHaveLength(0);
    signIn();
    expect(last().url).toMatch(/^ws:\/\/.+\/ws$/);
    last().open();
    expect(last().sent).toEqual([{ type: 'auth', token: 'token-1' }]);
    expect(service.status()).toBe('connecting');

    const seen: LiveEvent[] = [];
    service.on('notification').subscribe((event) => seen.push(event));
    last().emit({ type: 'ready' });
    expect(service.status()).toBe('open');
    last().emit({ type: 'notification', notification: { id: 'n1' } });
    last().emit({ type: 'message' });
    expect(seen.map((e) => e.type)).toEqual(['notification']);
    expect(service.send({ type: 'typing' })).toBe(true);
  });

  it('se reconecta con espera creciente y avisa al volver', () => {
    signIn();
    last().open();
    last().emit({ type: 'ready' });
    const reconnected = vi.fn();
    service.on('reconnected').subscribe(reconnected);

    last().drop();
    expect(service.status()).toBe('reconnecting');
    expect(service.send({ type: 'ping' })).toBe(false);
    vi.advanceTimersByTime(1000);
    expect(FakeSocket.instances).toHaveLength(2);
    last().drop();
    vi.advanceTimersByTime(999);
    expect(FakeSocket.instances).toHaveLength(2); // la segunda espera es mas larga
    vi.advanceTimersByTime(1100);
    expect(FakeSocket.instances).toHaveLength(3);
    last().open();
    last().emit({ type: 'ready' });
    expect(reconnected).toHaveBeenCalledTimes(1);
    expect(service.status()).toBe('open');
  });

  it('con el token vencido lo renueva antes de reconectar', async () => {
    const refresh = vi.spyOn(auth, 'refresh').mockResolvedValue();
    signIn();
    last().open();
    last().emit({ type: 'ready' });
    last().drop(4001);
    expect(refresh).toHaveBeenCalled();
    await Promise.resolve();
    expect(FakeSocket.instances).toHaveLength(2);
  });

  it('al cerrar sesion se desconecta y no reintenta', () => {
    signIn();
    last().open();
    last().emit({ type: 'ready' });
    auth.user.set(null);
    TestBed.tick();
    expect(service.status()).toBe('idle');
    vi.advanceTimersByTime(60_000);
    expect(FakeSocket.instances).toHaveLength(1);
  });
});
