import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { TranslocoPipe, TranslocoService } from '@jsverse/transloco';
import { LucideEye, LucideEyeOff, LucideStar } from '@icons';
import { apiErrorMessage } from '../../core/http/api-error-message';
import { LanguageService } from '../../core/i18n/language.service';
import { EmptyState } from '../../shared/ui/empty-state';
import { ErrorState } from '../../shared/ui/error-state';
import { GlassButton } from '../../shared/ui/glass-button';
import { GlassCard } from '../../shared/ui/glass-card';
import { GlassTabs } from '../../shared/ui/glass-tabs';
import { Skeleton } from '../../shared/ui/skeleton';
import { ToastService } from '../../shared/ui/toast.service';
import { AdminApi, AdminRating } from './admin.api';

type View = 'visible' | 'hidden';

/** Moderacion: comentarios de las calificaciones; ocultar no borra, se puede deshacer. */
@Component({
  selector: 'cp-admin-moderation',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    TranslocoPipe,
    EmptyState,
    ErrorState,
    GlassButton,
    GlassCard,
    GlassTabs,
    Skeleton,
    LucideEye,
    LucideEyeOff,
    LucideStar,
  ],
  template: `
    <div class="mx-auto flex max-w-4xl flex-col gap-5 py-2">
      <header>
        <h1 class="text-2xl font-bold sm:text-3xl">{{ 'nav.moderation' | transloco }}</h1>
        <p class="text-muted">{{ 'admin.moderation.subtitle' | transloco }}</p>
      </header>
      <cp-glass-tabs
        #tabsRef
        [tabs]="tabs()"
        [label]="'nav.moderation' | transloco"
        [(selected)]="view"
        (selectedChange)="load()"
      />
      <section
        [id]="tabsRef.panelId(view())"
        role="tabpanel"
        [attr.aria-labelledby]="tabsRef.tabId(view())"
        class="flex flex-col gap-3"
      >
        @if (loadError(); as message) {
          <cp-glass-card><cp-error-state [message]="message" (retry)="load()" /></cp-glass-card>
        } @else if (items() === null) {
          <cp-glass-card><cp-skeleton [lines]="4" /></cp-glass-card>
        } @else {
          @for (r of items(); track r.id) {
            <cp-glass-card class="flex items-start gap-3">
              <div class="min-w-0 flex-1">
                <p class="text-sm text-muted">
                  {{
                    'admin.moderation.byFor'
                      | transloco: { author: r.author_name, target: r.target_name }
                  }}
                  · {{ date(r.created_at) }}
                </p>
                <p class="inline-flex items-center gap-1 font-semibold">
                  <svg lucideStar class="size-4" aria-hidden="true"></svg>
                  {{ average(r.average) }}
                </p>
                <p class="whitespace-pre-line break-words">{{ r.comment }}</p>
              </div>
              <button cp-button variant="secondary" type="button" (click)="toggle(r)">
                @if (r.hidden) {
                  <svg lucideEye class="size-4" aria-hidden="true"></svg>
                  {{ 'admin.moderation.show' | transloco }}
                } @else {
                  <svg lucideEyeOff class="size-4" aria-hidden="true"></svg>
                  {{ 'admin.moderation.hide' | transloco }}
                }
              </button>
            </cp-glass-card>
          } @empty {
            <cp-empty-state [title]="'admin.moderation.none' | transloco" />
          }
          @if (cursor()) {
            <button
              cp-button
              variant="secondary"
              type="button"
              class="self-center"
              (click)="load(true)"
            >
              {{ 'trips.more' | transloco }}
            </button>
          }
        }
      </section>
    </div>
  `,
})
export default class AdminModeration {
  private readonly api = inject(AdminApi);
  private readonly transloco = inject(TranslocoService);
  private readonly language = inject(LanguageService);
  private readonly toast = inject(ToastService);

  protected readonly view = signal<View>('visible');
  protected readonly items = signal<AdminRating[] | null>(null);
  protected readonly loadError = signal<string | null>(null);
  protected readonly cursor = signal<string | null>(null);
  protected readonly tabs = computed(() => {
    this.language.current();
    return (['visible', 'hidden'] as const).map((id) => ({
      id,
      label: this.transloco.translate(`admin.moderation.tabs.${id}`),
    }));
  });

  constructor() {
    void this.load();
  }

  protected async load(more = false): Promise<void> {
    if (!more) {
      this.items.set(null);
      this.loadError.set(null);
    }
    try {
      const page = await this.api.ratings(this.view() === 'hidden', more ? this.cursor() : null);
      this.items.update((list) => (more ? [...(list ?? []), ...page.items] : page.items));
      this.cursor.set(page.next_cursor);
    } catch (error) {
      if (more) this.toast.show(apiErrorMessage(this.transloco, error), 'danger');
      else this.loadError.set(apiErrorMessage(this.transloco, error));
    }
  }

  protected async toggle(rating: AdminRating): Promise<void> {
    try {
      const updated = await this.api.hideRating(rating.id, !rating.hidden);
      // Sale de la pestana actual: ahora pertenece a la otra.
      this.items.update((list) => list?.filter((r) => r.id !== updated.id) ?? null);
      this.toast.show(
        this.transloco.translate(
          updated.hidden ? 'admin.moderation.hidden' : 'admin.moderation.shown',
        ),
        'success',
      );
    } catch (error) {
      this.toast.show(apiErrorMessage(this.transloco, error), 'danger');
    }
  }

  protected average(value: number): string {
    return value.toLocaleString(this.language.current(), { maximumFractionDigits: 1 });
  }

  protected date(iso: string): string {
    return new Date(iso).toLocaleDateString(this.language.current(), {
      dateStyle: 'medium',
      timeZone: 'America/Bogota',
    });
  }
}
