import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  computed,
  effect,
  inject,
  input,
  signal,
  untracked,
  viewChild,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { TranslocoPipe, TranslocoService } from '@jsverse/transloco';
import { LucideArrowLeft, LucideLock, LucideRotateCw, LucideSendHorizontal, LucideX } from '@icons';
import { AuthService } from '../../core/auth/auth.service';
import { apiErrorMessage } from '../../core/http/api-error-message';
import { LanguageService } from '../../core/i18n/language.service';
import { LiveEvent, RealtimeService } from '../../core/ws/realtime.service';
import { GlassButton } from '../../shared/ui/glass-button';
import { Skeleton } from '../../shared/ui/skeleton';
import {
  ChatApi,
  ChatMessage,
  ChatUnread,
  Conversation,
  MAX_MESSAGE_LENGTH,
  MessageEvent,
  TypingEvent,
} from './chat.api';

interface Pending {
  clientId: string;
  body: string;
  failed: boolean;
}

interface AckEvent extends LiveEvent {
  client_id: string;
  message: ChatMessage;
}

interface ErrorEvent extends LiveEvent {
  client_id: string | null;
  code: string;
}

const TYPING_SEND_MS = 3000;
const TYPING_SHOW_MS = 4000;

/**
 * Un chat: historial con carga hacia atras, mensajes en vivo, "escribiendo", envio por
 * WebSocket con respaldo HTTP y reintento, y recuperacion de lo perdido al reconectar.
 */
@Component({
  selector: 'cp-conversation-view',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    ReactiveFormsModule,
    RouterLink,
    TranslocoPipe,
    GlassButton,
    Skeleton,
    LucideArrowLeft,
    LucideLock,
    LucideRotateCw,
    LucideSendHorizontal,
    LucideX,
  ],
  host: { class: 'flex min-h-0 flex-col' },
  template: `
    @if (conversation(); as c) {
      <header class="flex items-center gap-3 border-b border-glass-border px-4 py-3">
        <a
          routerLink="/mensajes"
          class="grid size-11 shrink-0 place-items-center rounded-full hover:bg-glass lg:hidden"
          [attr.aria-label]="'chat.back' | transloco"
        >
          <svg lucideArrowLeft class="size-5" aria-hidden="true"></svg>
        </a>
        <div class="min-w-0 flex-1">
          <h2 class="truncate font-bold">{{ heading() }}</h2>
          <p class="truncate text-sm text-muted">{{ subtitle() }}</p>
        </div>
        @if (c.trip_id) {
          <a [routerLink]="['/viajes', c.trip_id]" class="text-sm font-semibold text-primary">
            {{ 'chat.viewTrip' | transloco }}
          </a>
        } @else if (c.series_id) {
          <a [routerLink]="['/series', c.series_id]" class="text-sm font-semibold text-primary">
            {{ 'chat.viewSeries' | transloco }}
          </a>
        }
      </header>

      <div #scroller class="min-h-0 flex-1 overflow-y-auto px-4 py-3" (scroll)="onScroll()">
        @if (hasOlder()) {
          <div class="mb-3 flex justify-center">
            <button cp-button variant="ghost" type="button" (click)="loadOlder()">
              {{ 'chat.older' | transloco }}
            </button>
          </div>
        }
        <ol role="log" aria-live="polite" [attr.aria-label]="heading()" class="flex flex-col gap-2">
          @for (m of messages(); track m.id; let i = $index) {
            @if (newDay(i)) {
              <li class="my-2 text-center text-xs font-semibold text-muted">
                {{ day(m.sent_at) }}
              </li>
            }
            <li class="flex flex-col" [class.items-end]="mine(m)">
              <div
                class="max-w-[85%] rounded-2xl px-3 py-2 sm:max-w-[70%]"
                [class]="mine(m) ? 'bg-accent text-on-accent' : 'glass-1'"
              >
                @if (!mine(m) && c.kind === 'trip_group') {
                  <p class="text-xs font-semibold">{{ m.sender_name }}</p>
                }
                <p class="break-words whitespace-pre-wrap">{{ m.body }}</p>
                <p class="mt-0.5 text-right text-[0.7rem] opacity-75">
                  <span class="sr-only"
                    >{{ mine(m) ? ('chat.you' | transloco) : m.sender_name }},</span
                  >
                  {{ time(m.sent_at) }}
                </p>
              </div>
            </li>
          } @empty {
            <li class="py-10 text-center text-muted">{{ 'chat.empty' | transloco }}</li>
          }
          @for (p of pending(); track p.clientId) {
            <li class="flex flex-col items-end">
              <div
                class="max-w-[85%] rounded-2xl bg-accent/60 px-3 py-2 text-on-accent sm:max-w-[70%]"
              >
                <p class="break-words whitespace-pre-wrap">{{ p.body }}</p>
                <p class="mt-0.5 text-right text-[0.7rem]">
                  {{ (p.failed ? 'chat.failed' : 'chat.sending') | transloco }}
                </p>
              </div>
              @if (p.failed) {
                <div class="mt-1 flex gap-1">
                  <button cp-button variant="ghost" type="button" (click)="retry(p)">
                    <svg lucideRotateCw class="size-4" aria-hidden="true"></svg>
                    {{ 'chat.retry' | transloco }}
                  </button>
                  <button cp-button variant="ghost" type="button" (click)="discard(p)">
                    <svg lucideX class="size-4" aria-hidden="true"></svg>
                    {{ 'chat.discard' | transloco }}
                  </button>
                </div>
              }
            </li>
          }
        </ol>
      </div>

      <p class="min-h-6 px-4 text-sm text-muted" aria-live="polite">
        @if (typing(); as name) {
          {{ 'chat.typing' | transloco: { name: name } }}
        }
      </p>

      @if (c.closed) {
        <p
          class="flex items-center gap-2 border-t border-glass-border px-4 py-4 text-sm text-muted"
        >
          <svg lucideLock class="size-4 shrink-0" aria-hidden="true"></svg>
          {{ 'chat.closed' | transloco }}
        </p>
      } @else {
        <form
          class="flex items-end gap-2 border-t border-glass-border p-3"
          (submit)="$event.preventDefault(); submit()"
        >
          <label class="sr-only" for="chat-input">{{ 'chat.placeholder' | transloco }}</label>
          <textarea
            id="chat-input"
            rows="1"
            [formControl]="draft"
            [attr.maxlength]="max"
            [placeholder]="'chat.placeholder' | transloco"
            (keydown)="onKeydown($event)"
            (input)="onTyping()"
            class="glass-1 max-h-32 min-h-11 flex-1 resize-none !rounded-2xl px-4 py-2.5 focus-visible:outline-2 focus-visible:outline-primary"
          ></textarea>
          <button
            cp-button
            type="submit"
            class="!size-11 !p-0"
            [disabled]="!canSend()"
            [attr.aria-label]="'chat.send' | transloco"
          >
            <svg lucideSendHorizontal class="size-5" aria-hidden="true"></svg>
          </button>
        </form>
        @if (remaining() < 100) {
          <p class="px-4 pb-2 text-right text-xs text-muted">
            {{ 'chat.remaining' | transloco: { count: remaining() } }}
          </p>
        }
      }
    } @else if (error()) {
      <p role="alert" class="p-6 text-danger">{{ error() }}</p>
    } @else {
      <div class="p-6"><cp-skeleton [lines]="5" /></div>
    }
  `,
})
export class ConversationView {
  readonly conversationId = input.required<string>();

  private readonly api = inject(ChatApi);
  private readonly unread = inject(ChatUnread);
  private readonly realtime = inject(RealtimeService);
  private readonly auth = inject(AuthService);
  private readonly transloco = inject(TranslocoService);
  private readonly language = inject(LanguageService);
  private readonly scroller = viewChild<ElementRef<HTMLElement>>('scroller');

  protected readonly max = MAX_MESSAGE_LENGTH;
  protected readonly conversation = signal<Conversation | null>(null);
  protected readonly messages = signal<ChatMessage[]>([]);
  protected readonly pending = signal<Pending[]>([]);
  protected readonly hasOlder = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly typing = signal<string | null>(null);
  protected readonly draft = new FormControl('', { nonNullable: true });
  private readonly draftText = signal('');
  private atBottom = true;
  private lastTypingSent = 0;
  private typingTimer: ReturnType<typeof setTimeout> | null = null;

  protected readonly remaining = computed(() => this.max - this.draftText().length);
  protected readonly canSend = computed(() => this.draftText().trim().length > 0);
  protected readonly heading = computed(() => {
    const c = this.conversation();
    if (!c) return '';
    return c.kind === 'direct' && c.counterpart ? c.counterpart : c.title;
  });
  protected readonly subtitle = computed(() => {
    const c = this.conversation();
    if (!c) return '';
    if (c.kind === 'direct') return c.title;
    const names = c.members.map((m) => m.full_name).join(', ');
    return c.departs_at ? `${this.day(c.departs_at)} · ${names}` : names;
  });

  constructor() {
    this.draft.valueChanges
      .pipe(takeUntilDestroyed())
      .subscribe((value) => this.draftText.set(value));
    effect(() => {
      const id = this.conversationId();
      untracked(() => void this.load(id));
    });

    this.realtime
      .on<MessageEvent>('message')
      .pipe(takeUntilDestroyed())
      .subscribe(({ message }) => {
        if (message.conversation_id !== this.conversationId()) return;
        this.append([message]);
        if (message.sender_id !== this.auth.user()?.id) {
          this.typing.set(null);
          this.markRead();
        }
      });
    this.realtime
      .on<AckEvent>('chat.ack')
      .pipe(takeUntilDestroyed())
      .subscribe(({ client_id, message }) => {
        this.pending.update((list) => list.filter((p) => p.clientId !== client_id));
        this.append([message]);
      });
    this.realtime
      .on<ErrorEvent>('error')
      .pipe(takeUntilDestroyed())
      .subscribe(({ client_id }) => {
        if (client_id) this.fail(client_id);
      });
    this.realtime
      .on<TypingEvent>('typing')
      .pipe(takeUntilDestroyed())
      .subscribe((event) => {
        if (event.conversation_id !== this.conversationId()) return;
        this.typing.set(event.name);
        if (this.typingTimer) clearTimeout(this.typingTimer);
        this.typingTimer = setTimeout(() => this.typing.set(null), TYPING_SHOW_MS);
      });
    this.realtime
      .on('reconnected')
      .pipe(takeUntilDestroyed())
      .subscribe(() => void this.catchUp());

    inject(DestroyRef).onDestroy(() => {
      if (this.typingTimer) clearTimeout(this.typingTimer);
      if (this.unread.open() === this.conversationId()) this.unread.open.set(null);
    });
  }

  private async load(id: string): Promise<void> {
    this.unread.open.set(id);
    this.error.set(null);
    this.conversation.set(null);
    this.messages.set([]);
    this.pending.set([]);
    try {
      const [conversation, messages] = await Promise.all([this.api.get(id), this.api.messages(id)]);
      this.conversation.set(conversation);
      this.messages.set(messages);
      this.hasOlder.set(messages.length >= 50);
      this.atBottom = true;
      this.scrollToBottom();
      if (conversation.unread) await this.markRead();
    } catch (error) {
      this.error.set(apiErrorMessage(this.transloco, error));
    }
  }

  /** Lo que llego mientras no habia conexion. */
  private async catchUp(): Promise<void> {
    const last = this.messages().at(-1);
    if (!this.conversation() || !last) return;
    try {
      this.append(await this.api.messages(this.conversationId(), { after: last.id }));
    } catch {
      // Se intenta otra vez en la siguiente reconexion.
    }
  }

  protected async loadOlder(): Promise<void> {
    const first = this.messages()[0];
    if (!first) return;
    const element = this.scroller()?.nativeElement;
    const before = element ? element.scrollHeight - element.scrollTop : 0;
    const older = await this.api.messages(this.conversationId(), { before: first.id });
    this.hasOlder.set(older.length >= 50);
    this.messages.update((list) => [...older, ...list]);
    // Mantiene a la vista el mismo mensaje tras agregar los anteriores arriba.
    requestAnimationFrame(() => {
      if (element) element.scrollTop = element.scrollHeight - before;
    });
  }

  private append(incoming: ChatMessage[]): void {
    const known = new Set(this.messages().map((m) => m.id));
    const fresh = incoming.filter((m) => !known.has(m.id));
    if (!fresh.length) return;
    this.messages.update((list) =>
      [...list, ...fresh].sort((a, b) => a.sent_at.localeCompare(b.sent_at)),
    );
    if (this.atBottom) this.scrollToBottom();
  }

  private async markRead(): Promise<void> {
    const id = this.conversationId();
    if (!this.realtime.send({ type: 'chat.read', conversation_id: id })) {
      await this.api.markRead(id).catch(() => undefined);
    }
    // El servidor ya marco el chat; el contador se recalcula.
    setTimeout(() => void this.unread.reload(), 300);
  }

  protected submit(): void {
    const body = this.draft.value.trim();
    if (!body) return;
    this.draft.setValue('');
    this.atBottom = true;
    void this.deliver({ clientId: crypto.randomUUID(), body, failed: false });
  }

  private async deliver(item: Pending): Promise<void> {
    this.pending.update((list) => [...list.filter((p) => p.clientId !== item.clientId), item]);
    this.scrollToBottom();
    const sent = this.realtime.send({
      type: 'chat.send',
      conversation_id: this.conversationId(),
      body: item.body,
      client_id: item.clientId,
    });
    if (sent) return; // Llega chat.ack (o error) por el WebSocket.
    try {
      const message = await this.api.send(this.conversationId(), item.body);
      this.pending.update((list) => list.filter((p) => p.clientId !== item.clientId));
      this.append([message]);
    } catch {
      this.fail(item.clientId);
    }
  }

  private fail(clientId: string): void {
    this.pending.update((list) =>
      list.map((p) => (p.clientId === clientId ? { ...p, failed: true } : p)),
    );
  }

  protected retry(item: Pending): void {
    void this.deliver({ ...item, failed: false });
  }

  protected discard(item: Pending): void {
    this.pending.update((list) => list.filter((p) => p.clientId !== item.clientId));
  }

  protected onKeydown(event: KeyboardEvent): void {
    // Enter envia; Mayus + Enter hace salto de linea.
    if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      this.submit();
    }
  }

  protected onTyping(): void {
    const now = Date.now();
    if (now - this.lastTypingSent < TYPING_SEND_MS) return;
    this.lastTypingSent = now;
    this.realtime.send({ type: 'typing', conversation_id: this.conversationId() });
  }

  protected onScroll(): void {
    const element = this.scroller()?.nativeElement;
    if (element) {
      this.atBottom = element.scrollHeight - element.scrollTop - element.clientHeight < 80;
    }
  }

  private scrollToBottom(): void {
    requestAnimationFrame(() => {
      const element = this.scroller()?.nativeElement;
      if (element) element.scrollTop = element.scrollHeight;
    });
  }

  protected mine(message: ChatMessage): boolean {
    return message.sender_id === this.auth.user()?.id;
  }

  protected newDay(index: number): boolean {
    const list = this.messages();
    return index === 0 || this.dayKey(list[index].sent_at) !== this.dayKey(list[index - 1].sent_at);
  }

  private dayKey(iso: string): string {
    return new Date(iso).toLocaleDateString('en-CA', { timeZone: 'America/Bogota' });
  }

  protected day(iso: string): string {
    return new Date(iso).toLocaleDateString(this.language.current(), {
      weekday: 'long',
      day: 'numeric',
      month: 'long',
      timeZone: 'America/Bogota',
    });
  }

  protected time(iso: string): string {
    return new Date(iso).toLocaleTimeString(this.language.current(), {
      hour: 'numeric',
      minute: '2-digit',
      timeZone: 'America/Bogota',
    });
  }
}
