import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterLink, RouterOutlet } from '@angular/router';
import { TranslocoPipe } from '@jsverse/transloco';
import { Brand } from '../../shared/ui/brand';

/** Marco de las pantallas sin sesion: marca y una tarjeta centrada. */
@Component({
  selector: 'cp-auth-layout',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterOutlet, RouterLink, TranslocoPipe, Brand],
  template: `
    <div class="flex min-h-dvh flex-col px-4 pt-[max(1rem,env(safe-area-inset-top))] pb-8 sm:px-8">
      <header class="flex items-center gap-3 py-2">
        <a routerLink="/" class="rounded-xl">
          <cp-brand [size]="44" [wordmark]="true" />
        </a>
      </header>
      <main id="main" class="flex flex-1 items-start justify-center pt-6 sm:items-center sm:pt-0">
        <div class="w-full max-w-lg">
          <router-outlet />
        </div>
      </main>
      <footer class="mt-8 flex flex-wrap justify-center gap-x-5 gap-y-2 text-sm text-muted">
        <a routerLink="/ayuda" class="underline-offset-4 hover:underline">
          {{ 'help.title' | transloco }}
        </a>
        <a routerLink="/legal/terminos" class="underline-offset-4 hover:underline">
          {{ 'legal.terms' | transloco }}
        </a>
        <a routerLink="/legal/datos" class="underline-offset-4 hover:underline">
          {{ 'legal.dataPolicy' | transloco }}
        </a>
      </footer>
    </div>
  `,
})
export default class AuthLayout {}
