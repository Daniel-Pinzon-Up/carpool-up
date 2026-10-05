import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, effect, inject, signal, untracked } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { AuthService } from '../../core/auth/auth.service';
import { LiveEvent, RealtimeService } from '../../core/ws/realtime.service';

export interface ChatMessage {
  id: string;
  conversation_id: string;
  sender_id: string;
  sender_name: string;
  body: string;
  sent_at: string;
}

export interface Conversation {
  id: string;
  kind: 'trip_group' | 'direct';
  trip_id: string | null;
  series_id: string | null;
  title: string;
  departs_at: string | null;
  counterpart: string | null;
  members: { id: string; full_name: string; is_driver: boolean }[];
  last_message: ChatMessage | null;
  unread: number;
  closed: boolean;
}

export interface MessageEvent extends LiveEvent {
  message: ChatMessage;
}

export interface TypingEvent extends LiveEvent {
  conversation_id: string;
  user_id: string;
  name: string;
}

export const MAX_MESSAGE_LENGTH = 1000;
const API = '/api/v1/conversations';

@Injectable({ providedIn: 'root' })
export class ChatApi {
  private readonly http = inject(HttpClient);

  list(): Promise<Conversation[]> {
    return firstValueFrom(this.http.get<Conversation[]>(API));
  }

  get(id: string): Promise<Conversation> {
    return firstValueFrom(this.http.get<Conversation>(`${API}/${id}`));
  }

  messages(id: string, cursor: { before?: string; after?: string } = {}): Promise<ChatMessage[]> {
    let params = new HttpParams();
    if (cursor.before) params = params.set('before', cursor.before);
    if (cursor.after) params = params.set('after', cursor.after);
    return firstValueFrom(this.http.get<ChatMessage[]>(`${API}/${id}/messages`, { params }));
  }

  send(id: string, body: string): Promise<ChatMessage> {
    return firstValueFrom(this.http.post<ChatMessage>(`${API}/${id}/messages`, { body }));
  }

  markRead(id: string): Promise<void> {
    return firstValueFrom(this.http.post<void>(`${API}/${id}/read`, {}));
  }

  unread(): Promise<{ unread: number; conversations: number }> {
    return firstValueFrom(
      this.http.get<{ unread: number; conversations: number }>(`${API}/unread`),
    );
  }
}

/**
 * Mensajes sin leer para el contador de la navegacion. Sube con cada mensaje ajeno que
 * llega en vivo, salvo en el chat abierto; se recalcula al leer y al reconectar.
 */
@Injectable({ providedIn: 'root' })
export class ChatUnread {
  private readonly api = inject(ChatApi);
  private readonly auth = inject(AuthService);
  private readonly realtime = inject(RealtimeService);

  readonly count = signal(0);
  /** Chat que se esta viendo: sus mensajes no cuentan como pendientes. */
  readonly open = signal<string | null>(null);

  constructor() {
    effect(() => {
      const active = this.auth.isActive();
      untracked(() => (active ? void this.reload() : this.count.set(0)));
    });
    this.realtime.on<MessageEvent>('message').subscribe(({ message }) => {
      const own = message.sender_id === this.auth.user()?.id;
      if (!own && message.conversation_id !== this.open()) {
        this.count.update((count) => count + 1);
      }
    });
    this.realtime.on('reconnected').subscribe(() => void this.reload());
  }

  async reload(): Promise<void> {
    try {
      this.count.set((await this.api.unread()).unread);
    } catch {
      // Informativo: se reintenta al reconectar.
    }
  }
}
