import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  input,
  signal,
  untracked,
} from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { TranslocoPipe, TranslocoService } from '@jsverse/transloco';
import { LucideStar } from '@lucide/angular';
import { apiErrorMessage } from '../../core/http/api-error-message';
import { LanguageService } from '../../core/i18n/language.service';
import { EmptyState } from '../../shared/ui/empty-state';
import { GlassButton } from '../../shared/ui/glass-button';
import { GlassCard } from '../../shared/ui/glass-card';
import { GlassTextarea } from '../../shared/ui/glass-textarea';
import { Skeleton } from '../../shared/ui/skeleton';
import { StarRating } from '../../shared/ui/star-rating';
import { ToastService } from '../../shared/ui/toast.service';
import { formatDeparture } from '../trips/trip-status';
import { PendingRating, RatingsApi } from './ratings.api';

const COMMENT_MAX = 300;

interface Pending extends PendingRating {
  key: string;
  form: FormGroup<{
    scores: FormGroup<Record<string, FormControl<number>>>;
    comment: FormControl<string>;
  }>;
}

/**
 * Calificar: una tarjeta por persona con estrellas por criterio (todas obligatorias) y un
 * comentario opcional. Sin :tripId muestra todo lo pendiente.
 */
@Component({
  selector: 'cp-rate-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    ReactiveFormsModule,
    RouterLink,
    TranslocoPipe,
    EmptyState,
    GlassButton,
    GlassCard,
    GlassTextarea,
    Skeleton,
    StarRating,
  ],
  template: `
    <div class="mx-auto flex max-w-3xl flex-col gap-5 py-2">
      <header>
        <h1 class="text-2xl font-bold sm:text-3xl">{{ 'ratings.title' | transloco }}</h1>
        <p class="text-muted">{{ 'ratings.subtitle' | transloco }}</p>
      </header>

      @if (items() === null) {
        <cp-glass-card><cp-skeleton [lines]="4" /></cp-glass-card>
      } @else {
        @for (item of items(); track item.key) {
          <cp-glass-card [level]="2">
            <form
              [formGroup]="item.form"
              class="flex flex-col gap-4"
              (ngSubmit)="submit(item)"
              novalidate
            >
              <div>
                <h2 class="text-lg font-bold">
                  {{ 'ratings.for.' + item.target_role | transloco: { name: item.target_name } }}
                </h2>
                <p class="text-sm text-muted">
                  {{ when(item.departs_at) }} · {{ item.origin }} → {{ item.destination }}
                </p>
                <p class="text-xs text-muted">
                  {{ 'ratings.closes' | transloco: { when: when(item.closes_at) } }}
                </p>
              </div>
              <fieldset class="flex flex-col gap-3" [formGroup]="item.form.controls.scores">
                <legend class="sr-only">{{ 'ratings.criteriaLegend' | transloco }}</legend>
                @for (criterion of item.criteria; track criterion) {
                  <div class="flex flex-wrap items-center justify-between gap-2">
                    <cp-star-rating
                      [formControlName]="criterion"
                      size="md"
                      [label]="'ratings.criteria.' + criterion | transloco"
                    />
                  </div>
                }
              </fieldset>
              <cp-glass-textarea
                formControlName="comment"
                [label]="'ratings.comment' | transloco"
                [hint]="'ratings.commentHint' | transloco: { max: commentMax }"
              />
              @if (missing(item)) {
                <p role="alert" class="text-sm text-danger">{{ 'ratings.missing' | transloco }}</p>
              }
              <button cp-button type="submit" class="self-start" [loading]="busy() === item.key">
                {{ 'ratings.send' | transloco }}
              </button>
            </form>
          </cp-glass-card>
        } @empty {
          <cp-empty-state
            [icon]="doneIcon"
            [title]="(sent() ? 'ratings.allDone' : 'ratings.none') | transloco"
            [description]="'ratings.noneHint' | transloco"
          >
            <a cp-button variant="secondary" routerLink="/mis-viajes">
              {{ 'nav.myTrips' | transloco }}
            </a>
          </cp-empty-state>
        }
      }
    </div>
  `,
})
export default class RatePage {
  /** Viaje concreto (ruta /calificar/:tripId); sin el, todo lo pendiente. */
  readonly tripId = input<string | undefined>();

  private readonly api = inject(RatingsApi);
  private readonly toast = inject(ToastService);
  private readonly transloco = inject(TranslocoService);
  private readonly language = inject(LanguageService);

  protected readonly doneIcon = LucideStar;
  protected readonly commentMax = COMMENT_MAX;
  protected readonly items = signal<Pending[] | null>(null);
  protected readonly busy = signal<string | null>(null);
  protected readonly sent = signal(0);
  private readonly tried = signal(new Set<string>());
  private readonly filter = computed(() => this.tripId() ?? null);

  constructor() {
    effect(() => {
      const trip = this.filter();
      untracked(() => void this.load(trip));
    });
  }

  private async load(tripId: string | null): Promise<void> {
    try {
      const pending = await this.api.pending();
      this.items.set(
        pending
          .filter((p) => !tripId || p.trip_id === tripId)
          .map((p) => ({
            ...p,
            key: `${p.trip_id}:${p.target_id}`,
            form: new FormGroup({
              scores: new FormGroup(
                Object.fromEntries(
                  p.criteria.map((c) => [
                    c,
                    new FormControl(0, { nonNullable: true, validators: [Validators.min(1)] }),
                  ]),
                ),
              ),
              comment: new FormControl('', {
                nonNullable: true,
                validators: [Validators.maxLength(COMMENT_MAX)],
              }),
            }),
          })),
      );
    } catch (error) {
      this.items.set([]);
      this.toast.show(apiErrorMessage(this.transloco, error), 'danger');
    }
  }

  protected missing(item: Pending): boolean {
    return this.tried().has(item.key) && item.form.controls.scores.invalid;
  }

  protected async submit(item: Pending): Promise<void> {
    this.tried.update((set) => new Set(set).add(item.key));
    if (item.form.invalid) return;
    const { scores, comment } = item.form.getRawValue();
    this.busy.set(item.key);
    try {
      await this.api.rate(item.trip_id, {
        target_id: item.target_id,
        scores,
        comment: comment.trim() || null,
      });
      this.sent.update((n) => n + 1);
      this.items.update((list) => (list ?? []).filter((p) => p.key !== item.key));
      this.toast.show(this.transloco.translate('ratings.thanks'), 'success');
    } catch (error) {
      this.toast.show(apiErrorMessage(this.transloco, error), 'danger');
    } finally {
      this.busy.set(null);
    }
  }

  protected when(iso: string): string {
    return formatDeparture(iso, this.language.current());
  }
}
