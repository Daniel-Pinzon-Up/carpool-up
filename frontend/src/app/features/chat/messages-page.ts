import { ChangeDetectionStrategy, Component, computed, inject, input, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { TranslocoPipe, TranslocoService } from '@jsverse/transloco';
import { LucideLock, LucideMessagesSquare, LucideUsers } from '@icons';
import { AuthService } from '../../core/auth/auth.service';
import { apiErrorMessage } from '../../core/http/api-error-message';
import { LOCALE } from '../../core/i18n/locale';
import { RealtimeService } from '../../core/ws/realtime.service';
import { EmptyState } from '../../shared/ui/empty-state';
import { GlassCard } from '../../shared/ui/glass-card';
import { ErrorState } from '../../shared/ui/error-state';
import { Skeleton } from '../../shared/ui/skeleton';
import { ChatApi, Conversation, MessageEvent } from './chat.api';
import { ConversationView } from './conversation-view';

/**
 * Mensajes: lista de chats y el chat abierto. En escritorio van lado a lado; en movil la
 * lista ocupa la pantalla y el chat se abre encima (con boton para volver).
 */
@Component({
  selector: 'cp-messages-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    RouterLink,
    RouterLinkActive,
    TranslocoPipe,
    ConversationView,
    EmptyState,
    ErrorState,
    GlassCard,
    Skeleton,
    LucideLock,
    LucideUsers,
  ],
  template: `
    <div class="mx-auto flex max-w-6xl flex-col gap-4 py-2">
      <h1 class="text-2xl font-bold sm:text-3xl" [class.max-lg:hidden]="id()">
        {{ 'nav.messages' | transloco }}
      </h1>
      <div class="grid gap-4 lg:h-[calc(100dvh-11rem)] lg:grid-cols-[22rem_minmax(0,1fr)]">
        <cp-glass-card class="!p-2 lg:overflow-y-auto" [class.max-lg:hidden]="id()">
          @if (conversations() === null) {
            <div class="flex flex-col gap-4 p-3">
              @for (row of [1, 2, 3]; track row) {
                <cp-skeleton [lines]="2" />
              }
            </div>
          } @else {
            <ul class="flex flex-col gap-1" [attr.aria-label]="'chat.list' | transloco">
              @for (c of conversations(); track c.id) {
                <li>
                  <a
                    [routerLink]="['/mensajes', c.id]"
                    routerLinkActive="bg-accent/15"
                    #rla="routerLinkActive"
                    [attr.aria-current]="rla.isActive ? 'page' : null"
                    class="flex gap-3 rounded-2xl p-3 transition hover:bg-glass-strong"
                  >
                    <span
                      class="grid size-11 shrink-0 place-items-center rounded-full bg-primary/15"
                    >
                      <svg lucideUsers class="size-5 text-primary" aria-hidden="true"></svg>
                    </span>
                    <span class="min-w-0 flex-1">
                      <span class="flex items-center gap-2">
                        <span class="truncate font-semibold">{{ name(c) }}</span>
                        @if (c.closed) {
                          <svg
                            lucideLock
                            class="size-3.5 shrink-0 text-muted"
                            aria-hidden="true"
                          ></svg>
                          <span class="sr-only">{{ 'chat.closedShort' | transloco }}</span>
                        }
                        @if (c.last_message) {
                          <span class="ml-auto shrink-0 text-xs text-muted">{{
                            when(c.last_message.sent_at)
                          }}</span>
                        }
                      </span>
                      <span class="block truncate text-xs text-muted">{{ detail(c) }}</span>
                      <span class="flex items-center gap-2">
                        <span class="truncate text-sm" [class.font-semibold]="c.unread">
                          {{ preview(c) }}
                        </span>
                        @if (c.unread) {
                          <span
                            class="ml-auto grid h-5 min-w-5 shrink-0 place-items-center rounded-full bg-accent px-1.5 text-xs font-bold text-on-accent"
                          >
                            {{ c.unread }}
                            <span class="sr-only">{{ 'chat.unread' | transloco }}</span>
                          </span>
                        }
                      </span>
                    </span>
                  </a>
                </li>
              } @empty {
                <li>
                  <cp-empty-state
                    [icon]="emptyIcon"
                    [title]="'chat.none' | transloco"
                    [description]="'chat.noneHint' | transloco"
                  />
                </li>
              }
            </ul>
          }
          @if (error()) {
            <cp-error-state [message]="error()" (retry)="load()" />
          }
        </cp-glass-card>

        @if (id(); as conversationId) {
          <cp-glass-card class="!p-0 flex h-[calc(100dvh-9rem)] flex-col overflow-hidden lg:h-auto">
            <cp-conversation-view class="flex-1" [conversationId]="conversationId" />
          </cp-glass-card>
        } @else {
          <cp-glass-card class="hidden place-items-center lg:grid">
            <cp-empty-state
              [icon]="emptyIcon"
              [title]="'chat.pick' | transloco"
              [description]="'chat.pickHint' | transloco"
            />
          </cp-glass-card>
        }
      </div>
    </div>
  `,
})
export default class MessagesPage {
  /** Chat abierto (ruta /mensajes/:id). */
  readonly id = input<string | undefined>();

  private readonly api = inject(ChatApi);
  private readonly auth = inject(AuthService);
  private readonly transloco = inject(TranslocoService);

  protected readonly emptyIcon = LucideMessagesSquare;
  protected readonly conversations = signal<Conversation[] | null>(null);
  protected readonly error = signal<string | null>(null);
  private readonly openId = computed(() => this.id() ?? null);

  constructor() {
    void this.load();
    const realtime = inject(RealtimeService);
    // La lista se mantiene al dia: ultimo mensaje, sin leer y orden.
    realtime
      .on<MessageEvent>('message')
      .pipe(takeUntilDestroyed())
      .subscribe(({ message }) => {
        const list = this.conversations();
        if (!list?.some((c) => c.id === message.conversation_id)) {
          void this.load();
          return;
        }
        const own = message.sender_id === this.auth.user()?.id;
        const updated = list.map((c) =>
          c.id === message.conversation_id
            ? {
                ...c,
                last_message: message,
                unread: own || c.id === this.openId() ? 0 : c.unread + 1,
              }
            : c,
        );
        this.conversations.set(
          updated.sort(
            (a, b) =>
              Number(a.closed) - Number(b.closed) ||
              (b.last_message?.sent_at ?? '').localeCompare(a.last_message?.sent_at ?? ''),
          ),
        );
      });
    realtime
      .on('conversation.joined', 'reconnected')
      .pipe(takeUntilDestroyed())
      .subscribe(() => void this.load());
  }

  protected async load(): Promise<void> {
    this.error.set(null);
    try {
      const list = await this.api.list();
      const open = this.openId();
      this.conversations.set(list.map((c) => (c.id === open ? { ...c, unread: 0 } : c)));
    } catch (error) {
      this.error.set(apiErrorMessage(this.transloco, error));
    }
  }

  protected name(c: Conversation): string {
    return c.title;
  }

  protected detail(c: Conversation): string {
    return this.transloco.translate('chat.groupOn', { when: this.when(c.departs_at, true) });
  }

  protected preview(c: Conversation): string {
    const last = c.last_message;
    if (!last) return this.transloco.translate('chat.noMessages');
    const who =
      last.sender_id === this.auth.user()?.id
        ? this.transloco.translate('chat.you')
        : last.sender_name.split(' ')[0];
    return `${who}: ${last.body}`;
  }

  protected when(iso: string, withDate = false): string {
    const date = new Date(iso);
    const today = new Date().toDateString() === date.toDateString();
    return date.toLocaleString(LOCALE, {
      timeZone: 'America/Bogota',
      ...(today && !withDate
        ? { hour: 'numeric', minute: '2-digit' }
        : {
            day: 'numeric',
            month: 'short',
            ...(withDate ? { hour: 'numeric', minute: '2-digit' } : {}),
          }),
    });
  }
}
