import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { Subject, filter } from 'rxjs';
import { getTranslocoTestingModule } from '../../../testing/transloco-testing';
import { ME } from '../../../testing/auth-fixtures';
import { AuthService } from '../../core/auth/auth.service';
import { NotificationsStore } from '../../core/notifications/notifications.store';
import { LiveEvent, RealtimeService } from '../../core/ws/realtime.service';
import { ToastService } from '../../shared/ui/toast.service';
import { ChatApi, ChatMessage, Conversation } from './chat.api';
import { ConversationView } from './conversation-view';
import MessagesPage from './messages-page';

async function settle(): Promise<void> {
  for (let i = 0; i < 10; i++) await Promise.resolve();
}

/** Canal en vivo de mentira: las pruebas emiten eventos y leen lo enviado. */
class FakeRealtime {
  readonly events = new Subject<LiveEvent>();
  readonly sent: Record<string, unknown>[] = [];
  connected = true;
  status = () => 'open';
  on(...types: string[]) {
    return this.events.pipe(filter((event) => types.includes(event.type)));
  }
  send(message: Record<string, unknown>): boolean {
    if (!this.connected) return false;
    this.sent.push(message);
    return true;
  }
}

const OTHER = { id: 'd1', full_name: 'Carlos Ruiz' };

function message(
  id: string,
  body: string,
  sender = OTHER,
  at = '2026-10-06T12:00:00Z',
): ChatMessage {
  return {
    id,
    conversation_id: 'c1',
    sender_id: sender.id,
    sender_name: sender.full_name,
    body,
    sent_at: at,
  };
}

const GROUP: Conversation = {
  id: 'c1',
  trip_id: 't1',
  title: 'Ciudad Universitaria - Terminal',
  departs_at: '2026-10-06T12:00:00Z',
  members: [
    { id: 'd1', full_name: 'Carlos Ruiz', is_driver: true },
    { id: ME.id, full_name: ME.full_name, is_driver: false },
  ],
  last_message: null,
  unread: 0,
  closed: false,
};

describe('chat', () => {
  let live: FakeRealtime;
  let api: Record<string, ReturnType<typeof vi.fn>>;

  beforeEach(() => {
    live = new FakeRealtime();
    api = {
      list: vi
        .fn()
        .mockResolvedValue([{ ...GROUP, last_message: message('m1', 'Hola'), unread: 1 }]),
      get: vi.fn().mockResolvedValue(GROUP),
      messages: vi.fn().mockResolvedValue([message('m1', 'Hola')]),
      send: vi.fn(),
      markRead: vi.fn().mockResolvedValue(undefined),
      unread: vi.fn().mockResolvedValue({ unread: 0, conversations: 0 }),
    };
    TestBed.configureTestingModule({
      imports: [getTranslocoTestingModule()],
      providers: [
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: RealtimeService, useValue: live },
        { provide: ChatApi, useValue: api },
      ],
    });
    TestBed.inject(AuthService).user.set(ME);
  });

  async function view(conversation: Conversation = GROUP) {
    api['get'].mockResolvedValue(conversation);
    const fixture = TestBed.createComponent(ConversationView);
    fixture.componentRef.setInput('conversationId', conversation.id);
    fixture.detectChanges();
    await settle();
    fixture.detectChanges();
    return fixture;
  }

  function text(element: HTMLElement): string {
    return element.textContent?.replace(/\s+/g, ' ') ?? '';
  }

  it('envia por el WebSocket, muestra el pendiente y lo confirma con el ack', async () => {
    const fixture = await view();
    const element = fixture.nativeElement as HTMLElement;
    expect(text(element)).toContain('Hola');
    expect(element.querySelector('[role=log]')?.getAttribute('aria-live')).toBe('polite');

    const input = element.querySelector('textarea') as HTMLTextAreaElement;
    input.value = 'Voy saliendo';
    input.dispatchEvent(new Event('input'));
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));
    fixture.detectChanges();
    const sent = live.sent.find((m) => m['type'] === 'chat.send')!;
    expect(sent).toMatchObject({ conversation_id: 'c1', body: 'Voy saliendo' });
    expect(text(element)).toContain('Enviando...');

    live.events.next({
      type: 'chat.ack',
      client_id: sent['client_id'],
      message: message('m2', 'Voy saliendo', { id: ME.id, full_name: ME.full_name }),
    });
    // El mismo mensaje tambien llega por el canal del chat: no se duplica.
    live.events.next({
      type: 'message',
      message: message('m2', 'Voy saliendo', { id: ME.id, full_name: ME.full_name }),
    });
    fixture.detectChanges();
    expect(text(element)).not.toContain('Enviando...');
    expect(text(element).match(/Voy saliendo/g)).toHaveLength(1);
  });

  it('sin conexion usa HTTP y permite reintentar si falla', async () => {
    live.connected = false;
    api['send'].mockRejectedValueOnce(new Error('offline'));
    const fixture = await view();
    const element = fixture.nativeElement as HTMLElement;
    const input = element.querySelector('textarea') as HTMLTextAreaElement;
    input.value = 'Hola de nuevo';
    input.dispatchEvent(new Event('input'));
    fixture.detectChanges();
    (element.querySelector('button[type=submit]') as HTMLButtonElement).click();
    await settle();
    fixture.detectChanges();
    expect(text(element)).toContain('No se envió');

    api['send'].mockResolvedValueOnce(
      message('m3', 'Hola de nuevo', { id: ME.id, full_name: ME.full_name }),
    );
    const retry = Array.from(element.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Reintentar'),
    ) as HTMLButtonElement;
    retry.click();
    await settle();
    fixture.detectChanges();
    expect(api['send']).toHaveBeenCalledTimes(2);
    expect(text(element)).not.toContain('No se envió');
  });

  it('muestra mensajes y "escribiendo" en vivo y marca el chat como leido', async () => {
    const fixture = await view();
    const element = fixture.nativeElement as HTMLElement;
    live.events.next({ type: 'typing', conversation_id: 'c1', user_id: 'd1', name: 'Carlos Ruiz' });
    fixture.detectChanges();
    expect(text(element)).toContain('Carlos Ruiz está escribiendo...');

    live.events.next({
      type: 'message',
      message: message('m4', 'Ya llegue', OTHER, '2026-10-06T12:05:00Z'),
    });
    fixture.detectChanges();
    expect(text(element)).toContain('Ya llegue');
    expect(text(element)).not.toContain('está escribiendo');
    expect(live.sent).toContainEqual({ type: 'chat.read', conversation_id: 'c1' });

    // Al reconectar pide lo que llego despues del ultimo mensaje visto.
    api['messages'].mockResolvedValueOnce([
      message('m5', 'Perdido', OTHER, '2026-10-06T12:06:00Z'),
    ]);
    live.events.next({ type: 'reconnected' });
    await settle();
    fixture.detectChanges();
    expect(api['messages']).toHaveBeenLastCalledWith('c1', { after: 'm4' });
    expect(text(element)).toContain('Perdido');
  });

  it('un chat cerrado se lee pero no se escribe', async () => {
    const fixture = await view({ ...GROUP, closed: true });
    expect(fixture.nativeElement.querySelector('textarea')).toBeNull();
    expect(text(fixture.nativeElement)).toContain('Puedes leerlo, pero no escribir');
  });

  it('la lista se actualiza con cada mensaje que llega', async () => {
    const fixture = TestBed.createComponent(MessagesPage);
    fixture.detectChanges();
    await settle();
    fixture.detectChanges();
    const element = fixture.nativeElement as HTMLElement;
    expect(text(element)).toContain('Carlos: Hola');
    live.events.next({
      type: 'message',
      message: message('m9', 'Estoy afuera', OTHER, '2026-10-06T12:09:00Z'),
    });
    fixture.detectChanges();
    expect(text(element)).toContain('Carlos: Estoy afuera');
    expect(element.querySelector('a[href="/mensajes/c1"]')?.textContent).toContain('2');
  });
});

describe('NotificationsStore', () => {
  it('cuenta los avisos en vivo, los anuncia y descuenta las lecturas', async () => {
    const live = new FakeRealtime();
    TestBed.configureTestingModule({
      imports: [getTranslocoTestingModule()],
      providers: [
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: RealtimeService, useValue: live },
      ],
    });
    const toast = vi.spyOn(TestBed.inject(ToastService), 'show');
    const store = TestBed.inject(NotificationsStore);
    const incoming = vi.fn();
    store.incoming.subscribe(incoming);
    const notification = (kind: string) => ({
      type: 'notification',
      notification: { id: kind, kind, payload: {}, read_at: null, created_at: '' },
    });
    live.events.next(notification('booking_accepted'));
    live.events.next(notification('message_new'));
    expect(store.unread()).toBe(2);
    expect(incoming).toHaveBeenCalledTimes(2);
    // Los mensajes del chat no salen como toast (tienen su contador).
    expect(toast).toHaveBeenCalledTimes(1);
    expect(toast.mock.calls[0][0]).toBe('¡Tu reserva fue aceptada!');
    live.events.next({ type: 'notification.read', id: 'booking_accepted' });
    expect(store.unread()).toBe(1);
    live.events.next({ type: 'notification.read_all' });
    expect(store.unread()).toBe(0);
  });
});
