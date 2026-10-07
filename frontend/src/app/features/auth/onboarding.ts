import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { TranslocoPipe } from '@jsverse/transloco';
import {
  LucideArrowRight,
  LucideDynamicIcon,
  LucideHandCoins,
  LucideRoute,
  LucideShieldCheck,
} from '@icons';
import { ONBOARDED_KEY } from '../../core/auth/auth.guards';
import { writePref } from '../../core/storage/local-preferences';
import { GlassButton } from '../../shared/ui/glass-button';
import { GlassCard } from '../../shared/ui/glass-card';

const SLIDES = [
  { key: 'value', icon: LucideRoute, image: 'brand/pickup.webp' },
  { key: 'how', icon: LucideHandCoins, image: 'brand/car-watercolor.webp' },
  { key: 'safety', icon: LucideShieldCheck, image: null },
] as const;

/** Tres pasos de bienvenida: propuesta de valor, como funciona y seguridad. */
@Component({
  selector: 'cp-onboarding',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, TranslocoPipe, GlassCard, GlassButton, LucideDynamicIcon, LucideArrowRight],
  template: `
    <cp-glass-card [level]="2" class="!p-8">
      <section aria-live="polite" class="flex flex-col items-center text-center">
        @if (slide().image; as src) {
          <img [src]="src" alt="" width="720" height="536" class="mb-6 h-44 w-auto sm:h-52" />
        } @else {
          <span class="mb-6 grid size-24 place-items-center rounded-[2rem] bg-accent/15">
            <svg [lucideIcon]="slide().icon" class="size-12 text-accent" aria-hidden="true"></svg>
          </span>
        }
        <p class="mb-2 text-sm font-semibold text-muted">
          {{ 'onboarding.step' | transloco: { current: index() + 1, total: slides.length } }}
        </p>
        <h1 class="mb-3 text-2xl font-bold sm:text-3xl">
          {{ 'onboarding.' + slide().key + '.title' | transloco }}
        </h1>
        <p class="max-w-sm text-muted">{{ 'onboarding.' + slide().key + '.body' | transloco }}</p>
      </section>

      <div class="my-8 flex justify-center gap-2" aria-hidden="true">
        @for (item of slides; track item.key; let i = $index) {
          <span
            class="h-2 rounded-full transition-all duration-200"
            [class]="i === index() ? 'w-8 bg-accent' : 'w-2 bg-muted/40'"
          ></span>
        }
      </div>

      @if (isLast()) {
        <div class="flex flex-col gap-3">
          <button cp-button size="lg" [block]="true" type="button" (click)="finish('/registro')">
            {{ 'onboarding.createAccount' | transloco }}
          </button>
          <button
            cp-button
            variant="secondary"
            size="lg"
            [block]="true"
            type="button"
            (click)="finish('/ingresar')"
          >
            {{ 'onboarding.haveAccount' | transloco }}
          </button>
        </div>
      } @else {
        <div class="flex items-center justify-between gap-3">
          <button cp-button variant="ghost" type="button" (click)="finish('/ingresar')">
            {{ 'onboarding.skip' | transloco }}
          </button>
          <button cp-button type="button" (click)="index.set(index() + 1)">
            {{ 'onboarding.next' | transloco }}
            <svg lucideArrowRight class="size-4" aria-hidden="true"></svg>
          </button>
        </div>
      }
    </cp-glass-card>
    <p class="mt-6 text-center text-sm text-muted">
      <a routerLink="/legal/terminos" class="underline underline-offset-4">{{
        'legal.terms' | transloco
      }}</a>
    </p>
  `,
})
export default class Onboarding {
  private readonly router = inject(Router);
  protected readonly slides = SLIDES;
  protected readonly index = signal(0);
  protected readonly slide = computed(() => SLIDES[this.index()]);
  protected readonly isLast = computed(() => this.index() === SLIDES.length - 1);

  protected finish(path: string): void {
    writePref(ONBOARDED_KEY, 'true');
    void this.router.navigateByUrl(path);
  }
}
