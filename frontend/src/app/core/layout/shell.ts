import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  isDevMode,
  signal,
} from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { TranslocoPipe } from '@jsverse/transloco';
import {
  LucideBell,
  LucideWifiOff,
  LucideDynamicIcon,
  LucidePalette,
  LucidePanelLeftClose,
  LucidePanelLeftOpen,
} from '@lucide/angular';
import { Brand } from '../../shared/ui/brand';
import { ChatUnread } from '../../features/chat/chat.api';
import { NotificationsStore } from '../notifications/notifications.store';
import { RealtimeService } from '../ws/realtime.service';
import { LanguageSelect } from '../../shared/ui/language-select';
import { ThemeToggle } from '../../shared/ui/theme-toggle';
import { AuthService } from '../auth/auth.service';
import { NAV_BY_ROLE } from './navigation';

/**
 * Estructura de la app autenticada.
 * Movil (< 640 px): barra inferior de vidrio. Tablet y escritorio: barra lateral plegable.
 * Los destinos dependen del rol del usuario con sesion.
 */
@Component({
  selector: 'cp-shell',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    Brand,
    RouterOutlet,
    RouterLink,
    RouterLinkActive,
    TranslocoPipe,
    LucideDynamicIcon,
    LucideBell,
    LucideWifiOff,
    LucidePalette,
    LucidePanelLeftClose,
    LucidePanelLeftOpen,
    LanguageSelect,
    ThemeToggle,
  ],
  template: `
    <a
      href="#main"
      class="glass-2 fixed top-2 left-2 z-50 -translate-y-24 px-4 py-2 font-semibold focus:translate-y-0"
    >
      {{ 'layout.skipToContent' | transloco }}
    </a>

    <div class="flex min-h-dvh">
      <!-- Barra lateral: tablet y escritorio -->
      <nav
        class="glass-2 !rounded-none !border-y-0 !border-l-0 sticky top-0 hidden h-dvh shrink-0 flex-col gap-2 p-3 transition-[width] duration-200 sm:flex"
        [class]="collapsed() ? 'w-20' : 'w-64'"
        [attr.aria-label]="'layout.mainNav' | transloco"
      >
        <div class="mb-4 flex items-center px-2 pt-2" [class.justify-center]="collapsed()">
          <cp-brand [size]="44" [showName]="!collapsed()" />
        </div>

        @for (item of items(); track item.path) {
          <a
            [routerLink]="item.path"
            routerLinkActive="bg-accent/15 !text-text"
            #rla="routerLinkActive"
            [attr.aria-current]="rla.isActive ? 'page' : null"
            class="flex min-h-12 items-center gap-3 rounded-2xl px-3 font-medium text-muted transition hover:bg-glass hover:text-text"
            [class.justify-center]="collapsed()"
            [attr.title]="collapsed() ? ('nav.' + item.key | transloco) : null"
          >
            <span class="relative shrink-0">
              <svg
                [lucideIcon]="item.icon"
                class="size-6"
                [class.text-accent]="rla.isActive"
                aria-hidden="true"
              ></svg>
              @if (badge(item.key); as count) {
                <span
                  class="absolute -top-1 -right-1 grid h-5 min-w-5 place-items-center rounded-full bg-accent px-1 text-[0.7rem] font-bold text-on-accent"
                >
                  {{ count > 99 ? '99+' : count }}
                  <span class="sr-only">{{ 'layout.unread' | transloco }}</span>
                </span>
              }
            </span>
            <span [class.sr-only]="collapsed()">{{ 'nav.' + item.key | transloco }}</span>
          </a>
        }

        <div class="mt-auto flex flex-col gap-2">
          @if (devMode) {
            <a
              routerLink="/catalogo"
              routerLinkActive="bg-accent/15 !text-text"
              class="flex min-h-12 items-center gap-3 rounded-2xl px-3 font-medium text-muted transition hover:bg-glass hover:text-text"
              [class.justify-center]="collapsed()"
            >
              <svg lucidePalette class="size-6 shrink-0" aria-hidden="true"></svg>
              <span [class.sr-only]="collapsed()">{{ 'nav.catalog' | transloco }}</span>
            </a>
          }
          <button
            type="button"
            (click)="collapsed.set(!collapsed())"
            [attr.aria-expanded]="!collapsed()"
            class="flex min-h-12 items-center gap-3 rounded-2xl px-3 font-medium text-muted transition hover:bg-glass hover:text-text"
            [class.justify-center]="collapsed()"
          >
            @if (collapsed()) {
              <svg lucidePanelLeftOpen class="size-6 shrink-0" aria-hidden="true"></svg>
            } @else {
              <svg lucidePanelLeftClose class="size-6 shrink-0" aria-hidden="true"></svg>
            }
            <span [class.sr-only]="collapsed()">{{
              (collapsed() ? 'layout.expandNav' : 'layout.collapseNav') | transloco
            }}</span>
          </button>
        </div>
      </nav>

      <div class="flex min-w-0 flex-1 flex-col">
        <header
          class="relative z-30 flex items-center gap-3 px-4 pt-[max(0.75rem,env(safe-area-inset-top))] pb-3 sm:px-8"
        >
          <cp-brand class="sm:hidden" [size]="36" />
          <div class="ml-auto flex items-center gap-2">
            @if (devMode) {
              <a
                routerLink="/catalogo"
                class="glass-1 !rounded-full grid size-11 place-items-center sm:hidden"
                [attr.aria-label]="'nav.catalog' | transloco"
              >
                <svg lucidePalette class="size-5" aria-hidden="true"></svg>
              </a>
            }
            @if (live.status() === 'reconnecting') {
              <span
                class="glass-1 !rounded-full flex min-h-11 items-center gap-2 px-3 text-sm text-muted"
                role="status"
              >
                <svg lucideWifiOff class="size-4" aria-hidden="true"></svg>
                <span class="hidden sm:inline">{{ 'layout.reconnecting' | transloco }}</span>
                <span class="sr-only sm:hidden">{{ 'layout.reconnecting' | transloco }}</span>
              </span>
            }
            <a
              routerLink="/notificaciones"
              routerLinkActive="!bg-accent/20"
              class="glass-1 !rounded-full relative grid size-11 place-items-center"
              [attr.aria-label]="
                notifications.unread()
                  ? ('layout.notificationsUnread' | transloco: { count: notifications.unread() })
                  : ('nav.notifications' | transloco)
              "
            >
              <svg lucideBell class="size-5" aria-hidden="true"></svg>
              @if (notifications.unread(); as count) {
                <span
                  class="absolute -top-0.5 -right-0.5 grid h-5 min-w-5 place-items-center rounded-full bg-accent px-1 text-[0.7rem] font-bold text-on-accent"
                  aria-hidden="true"
                >
                  {{ count > 99 ? '99+' : count }}
                </span>
              }
            </a>
            <cp-language-select />
            <cp-theme-toggle />
          </div>
        </header>

        <main id="main" tabindex="-1" class="flex-1 px-4 pb-28 focus:outline-none sm:px-8 sm:pb-10">
          <router-outlet />
        </main>
      </div>
    </div>

    <!-- Barra inferior: movil -->
    <nav
      class="glass-2 fixed inset-x-3 bottom-[max(0.75rem,env(safe-area-inset-bottom))] z-40 flex justify-around px-1 py-1.5 sm:hidden"
      [attr.aria-label]="'layout.mainNav' | transloco"
    >
      @for (item of mobileItems(); track item.path) {
        <a
          [routerLink]="item.path"
          routerLinkActive="!text-text"
          #rla="routerLinkActive"
          [attr.aria-current]="rla.isActive ? 'page' : null"
          class="flex min-h-12 min-w-14 flex-1 flex-col items-center justify-center gap-0.5 rounded-2xl text-[0.7rem] font-medium text-muted transition"
        >
          <span
            class="relative grid h-7 w-12 place-items-center rounded-full transition"
            [class]="rla.isActive ? 'bg-accent/20' : ''"
          >
            <svg
              [lucideIcon]="item.icon"
              class="size-5"
              [class.text-accent]="rla.isActive"
              aria-hidden="true"
            ></svg>
            @if (badge(item.key); as count) {
              <span
                class="absolute -top-1 right-0 grid h-5 min-w-5 place-items-center rounded-full bg-accent px-1 text-[0.7rem] font-bold text-on-accent"
              >
                {{ count > 99 ? '99+' : count }}
                <span class="sr-only">{{ 'layout.unread' | transloco }}</span>
              </span>
            }
          </span>
          <span class="max-w-full truncate">{{ 'navShort.' + item.key | transloco }}</span>
        </a>
      }
    </nav>
  `,
})
export class Shell {
  private readonly auth = inject(AuthService);
  protected readonly live = inject(RealtimeService);
  protected readonly notifications = inject(NotificationsStore);
  private readonly chatUnread = inject(ChatUnread);
  protected readonly items = computed(() => NAV_BY_ROLE[this.auth.user()?.role ?? 'passenger']);
  protected readonly mobileItems = computed(() => this.items().slice(0, 5));
  protected readonly collapsed = signal(
    globalThis.innerWidth !== undefined && globalThis.innerWidth < 1024,
  );
  protected readonly devMode = isDevMode();

  /** Pendientes por destino de la navegacion: mensajes y avisos. */
  protected badge(key: string): number {
    if (key === 'messages') return this.chatUnread.count();
    if (key === 'notifications') return this.notifications.unread();
    return 0;
  }
}
