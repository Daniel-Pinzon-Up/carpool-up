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
import { Router, RouterLink } from '@angular/router';
import { TranslocoPipe, TranslocoService } from '@jsverse/transloco';
import { LucideArrowRight, LucideCopy, LucidePencil, LucideTriangleAlert, LucideX } from '@icons';
import { firstValueFrom } from 'rxjs';
import { AuthService } from '../../core/auth/auth.service';
import { apiErrorMessage } from '../../core/http/api-error-message';
import { LanguageService } from '../../core/i18n/language.service';
import { formatCop } from '../../shared/map/routing.api';
import { DialogService } from '../../shared/ui/dialog.service';
import { GlassButton } from '../../shared/ui/glass-button';
import { GlassCard } from '../../shared/ui/glass-card';
import { ErrorState } from '../../shared/ui/error-state';
import { Skeleton } from '../../shared/ui/skeleton';
import { StatusBadge } from '../../shared/ui/status-badge';
import { ToastService } from '../../shared/ui/toast.service';
import { SubscribePanel } from '../bookings/subscribe-panel';
import { TripCard } from './trip-card';
import {
  CancelDialogData,
  CancelTripDialog,
  DuplicateDialog,
  DuplicateResult,
} from './trip-dialogs';
import { SERIES_STATUS_TONE } from './trip-status';
import { Series, TripsApi } from './trips.api';

/** Detalle de una serie: plantilla, ocurrencias con su estado y acciones del conductor. */
@Component({
  selector: 'cp-series-detail',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    RouterLink,
    TranslocoPipe,
    GlassButton,
    GlassCard,
    ErrorState,
    Skeleton,
    StatusBadge,
    SubscribePanel,
    TripCard,
    LucideArrowRight,
    LucideCopy,
    LucidePencil,
    LucideTriangleAlert,
    LucideX,
  ],
  template: `
    <div class="mx-auto flex max-w-4xl flex-col gap-5 py-2">
      @if (error()) {
        <cp-glass-card><cp-error-state [message]="error()" (retry)="reload()" /></cp-glass-card>
      } @else if (series(); as s) {
        <header class="flex flex-wrap items-start justify-between gap-3">
          <div class="flex flex-col gap-1">
            <cp-status-badge class="self-start" [variant]="tone()">{{
              'trips.seriesStatus.' + s.status | transloco
            }}</cp-status-badge>
            <h1 class="flex flex-wrap items-center gap-2 text-2xl font-bold sm:text-3xl">
              {{ s.origin }}
              <svg lucideArrowRight class="size-6 text-muted" aria-hidden="true"></svg>
              <span class="sr-only">{{ 'trips.to' | transloco }}</span>
              {{ s.destination }}
            </h1>
            <p class="text-muted">
              {{ days() }} · {{ s.departure_time.slice(0, 5) }} ·
              {{
                'trips.window' | transloco: { start: date(s.window_start), end: date(s.window_end) }
              }}
            </p>
          </div>
          @if (isOwner()) {
            <div class="flex flex-wrap gap-2">
              @if (s.status === 'active') {
                <a cp-button variant="secondary" [routerLink]="['/series', s.id, 'editar']">
                  <svg lucidePencil class="size-4" aria-hidden="true"></svg>
                  {{ 'trips.actions.edit' | transloco }}
                </a>
                <button cp-button variant="danger" type="button" (click)="cancel()">
                  <svg lucideX class="size-4" aria-hidden="true"></svg>
                  {{ 'trips.actions.cancelSeries' | transloco }}
                </button>
              }
              <button cp-button variant="ghost" type="button" (click)="duplicate()">
                <svg lucideCopy class="size-4" aria-hidden="true"></svg>
                {{ 'trips.actions.duplicate' | transloco }}
              </button>
            </div>
          }
        </header>

        <cp-glass-card>
          <dl class="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
            <div>
              <dt class="text-muted">{{ 'trips.counts.scheduled' | transloco }}</dt>
              <dd class="text-xl font-bold">{{ s.counts.scheduled }}</dd>
            </div>
            <div>
              <dt class="text-muted">{{ 'trips.counts.picoPlaca' | transloco }}</dt>
              <dd class="text-xl font-bold">{{ s.counts.pico_placa }}</dd>
            </div>
            <div>
              <dt class="text-muted">{{ 'planner.seats' | transloco }}</dt>
              <dd class="text-xl font-bold">{{ s.seats }}</dd>
            </div>
            <div>
              <dt class="text-muted">{{ 'publish.price.label' | transloco }}</dt>
              <dd class="text-xl font-bold">{{ money() }}</dd>
            </div>
          </dl>
          @if (s.counts.pico_placa) {
            <p class="mt-4 flex gap-2 text-sm">
              <svg
                lucideTriangleAlert
                class="size-4 shrink-0 text-warning"
                aria-hidden="true"
              ></svg>
              {{ 'trips.picoPlacaAlert' | transloco: { count: s.counts.pico_placa } }}
            </p>
          }
          @if (s.cancel_reason) {
            <p class="mt-4 text-sm">
              <span class="font-semibold">{{ 'trips.cancelReason' | transloco }}:</span>
              {{ s.cancel_reason }}
            </p>
          }
        </cp-glass-card>

        @if (isPassenger()) {
          <cp-subscribe-panel [series]="s" (changed)="reload()" />
        }
        <section aria-labelledby="occurrences-title" class="flex flex-col gap-3">
          <h2 id="occurrences-title" class="text-xl font-bold">
            {{ 'trips.occurrences' | transloco }}
          </h2>
          @for (trip of s.occurrences; track trip.id) {
            <cp-trip-card [trip]="trip" />
          }
        </section>
      } @else {
        <cp-glass-card><cp-skeleton [lines]="6" /></cp-glass-card>
      }
    </div>
  `,
})
export default class SeriesDetail {
  readonly id = input.required<string>();

  private readonly api = inject(TripsApi);
  private readonly auth = inject(AuthService);
  private readonly dialogs = inject(DialogService);
  private readonly toast = inject(ToastService);
  private readonly router = inject(Router);
  private readonly transloco = inject(TranslocoService);
  private readonly language = inject(LanguageService);

  protected readonly series = signal<Series | null>(null);
  protected readonly error = signal<string | null>(null);
  protected readonly isOwner = computed(() => this.series()?.driver.id === this.auth.user()?.id);
  protected readonly isPassenger = computed(
    () => this.auth.user()?.role === 'passenger' && !this.isOwner(),
  );
  protected readonly tone = computed(() => SERIES_STATUS_TONE[this.series()?.status ?? 'active']);
  protected readonly money = computed(() =>
    formatCop(this.series()?.price_per_seat ?? 0, this.language.current()),
  );
  protected readonly days = computed(() =>
    (this.series()?.weekdays ?? [])
      .map((day) =>
        new Date(Date.UTC(2026, 0, 5 + day)).toLocaleDateString(this.language.current(), {
          weekday: 'long',
          timeZone: 'UTC',
        }),
      )
      .join(', '),
  );

  constructor() {
    effect(() => {
      const id = this.id();
      untracked(() => void this.load(id));
    });
  }

  private async load(id: string): Promise<void> {
    this.error.set(null);
    try {
      this.series.set(await this.api.series(id));
    } catch (error) {
      this.error.set(apiErrorMessage(this.transloco, error));
    }
  }

  protected async reload(): Promise<void> {
    await this.load(this.id());
  }

  protected date(value: string): string {
    const [y, m, d] = value.split('-').map(Number);
    return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString(this.language.current(), {
      day: 'numeric',
      month: 'short',
      timeZone: 'UTC',
    });
  }

  protected async cancel(): Promise<void> {
    const series = this.series();
    if (!series) return;
    const ref = this.dialogs.open<string, CancelDialogData, CancelTripDialog>(CancelTripDialog, {
      title: this.transloco.translate('trips.cancel.seriesTitle'),
      message: this.transloco.translate('trips.cancel.seriesMessage'),
    });
    const reason = await firstValueFrom(ref.closed);
    if (!reason) return;
    try {
      this.series.set(await this.api.cancelSeries(series.id, reason));
      this.toast.show(this.transloco.translate('trips.cancel.seriesDone'), 'success');
    } catch (error) {
      this.toast.show(apiErrorMessage(this.transloco, error), 'danger');
    }
  }

  protected async duplicate(): Promise<void> {
    const series = this.series();
    if (!series) return;
    const ref = this.dialogs.open<DuplicateResult, unknown, DuplicateDialog>(DuplicateDialog, {
      kind: 'series',
      time: series.departure_time.slice(0, 5),
    });
    const result = await firstValueFrom(ref.closed);
    if (!result || result.kind !== 'series') return;
    try {
      const copy = await this.api.duplicateSeries(series.id, result.startDate, result.window);
      this.toast.show(this.transloco.translate('trips.duplicate.done'), 'success');
      await this.router.navigate(['/series', copy.id]);
    } catch (error) {
      this.toast.show(apiErrorMessage(this.transloco, error), 'danger');
    }
  }
}
