import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { TranslocoPipe } from '@jsverse/transloco';
import { LucideArrowLeft, LucideChevronDown } from '@lucide/angular';
import { MetaService } from '../../core/meta/meta.service';
import { GlassCard } from '../../shared/ui/glass-card';

/** Preguntas por grupo; los textos viven en help.q.<id>.q y help.q.<id>.a. */
export const HELP_GROUPS: { id: string; questions: string[] }[] = [
  { id: 'account', questions: ['who', 'code', 'revalidate'] },
  { id: 'passenger', questions: ['search', 'cancel', 'noShow', 'waitlist'] },
  { id: 'driver', questions: ['become', 'series', 'picoPlaca', 'price'] },
  { id: 'safety', questions: ['share', 'emergency'] },
  { id: 'privacy', questions: ['data', 'ratings'] },
];

/** Valores de respaldo si la configuracion publica aun no llega. */
const DEFAULTS: Record<string, unknown> = {
  allowed_email_suffix: '.edu.co',
  auth_code_minutes: 10,
  auth_code_resend_seconds: 60,
  revalidation_days: 30,
  search_radius_meters: 500,
  search_time_window_minutes: 60,
  cancel_free_hours: 2,
  no_show_wait_minutes: 10,
  no_show_limit: 3,
  no_show_window_days: 30,
  no_show_ban_days: 7,
  waitlist_offer_minutes: 15,
  emergency_phone: '123',
  rating_window_days: 7,
};

/**
 * Ayuda: preguntas frecuentes en acordeon nativo (details/summary), accesible con teclado y
 * lector de pantalla sin codigo extra. Las cifras salen de la configuracion publica, asi que
 * cambian solas cuando el superadmin ajusta una regla.
 */
@Component({
  selector: 'cp-help-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, TranslocoPipe, GlassCard, LucideArrowLeft, LucideChevronDown],
  styles: `
    details > summary {
      list-style: none;
    }
    details > summary::-webkit-details-marker {
      display: none;
    }
    details[open] .chevron {
      transform: rotate(180deg);
    }
  `,
  template: `
    <div class="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-6 sm:py-10">
      <a
        routerLink="/"
        class="inline-flex min-h-11 items-center gap-2 self-start font-semibold text-primary"
      >
        <svg lucideArrowLeft class="size-4" aria-hidden="true"></svg>
        {{ 'legal.back' | transloco }}
      </a>
      <header>
        <h1 class="text-2xl font-bold sm:text-3xl">{{ 'help.title' | transloco }}</h1>
        <p class="text-muted">{{ 'help.subtitle' | transloco }}</p>
      </header>
      @for (group of groups; track group.id) {
        <section class="flex flex-col gap-3" [attr.aria-labelledby]="'help-' + group.id">
          <h2 [id]="'help-' + group.id" class="text-lg font-semibold">
            {{ 'help.groups.' + group.id | transloco }}
          </h2>
          <cp-glass-card class="!p-0">
            @for (id of group.questions; track id; let last = $last) {
              <details class="group" [class.border-b]="!last" [class.border-glass-border]="!last">
                <summary
                  class="flex min-h-14 cursor-pointer items-center justify-between gap-4 rounded-2xl px-5 py-3 font-semibold"
                >
                  {{ 'help.q.' + id + '.q' | transloco }}
                  <svg
                    lucideChevronDown
                    class="chevron size-5 shrink-0 transition-transform"
                    aria-hidden="true"
                  ></svg>
                </summary>
                <p class="px-5 pb-4 text-muted">
                  {{ 'help.q.' + id + '.a' | transloco: params() }}
                </p>
              </details>
            }
          </cp-glass-card>
        </section>
      }
      <p class="text-sm text-muted">
        {{ 'help.legal' | transloco }}
        <a
          routerLink="/legal/terminos"
          class="font-semibold text-primary underline-offset-4 hover:underline"
          >{{ 'legal.terms' | transloco }}</a
        >
        ·
        <a
          routerLink="/legal/datos"
          class="font-semibold text-primary underline-offset-4 hover:underline"
          >{{ 'legal.dataPolicy' | transloco }}</a
        >
      </p>
    </div>
  `,
})
export default class HelpPage {
  private readonly meta = inject(MetaService);

  protected readonly groups = HELP_GROUPS;
  protected readonly params = computed(() => {
    const s = { ...DEFAULTS, ...this.meta.settings() };
    return {
      suffix: s['allowed_email_suffix'],
      minutes: s['auth_code_minutes'],
      seconds: s['auth_code_resend_seconds'],
      days: s['revalidation_days'],
      meters: s['search_radius_meters'],
      window: s['search_time_window_minutes'],
      hours: s['cancel_free_hours'],
      wait: s['no_show_wait_minutes'],
      limit: s['no_show_limit'],
      windowDays: s['no_show_window_days'],
      ban: s['no_show_ban_days'],
      offer: s['waitlist_offer_minutes'],
      phone: s['emergency_phone'],
      ratingDays: s['rating_window_days'],
    };
  });

  constructor() {
    void this.meta.load();
  }
}
