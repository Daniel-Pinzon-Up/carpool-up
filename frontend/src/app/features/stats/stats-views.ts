import { ChangeDetectionStrategy, Component, computed, inject, input, signal } from '@angular/core';
import { TranslocoPipe, TranslocoService } from '@jsverse/transloco';
import { LucideStar } from '@icons';
import { apiErrorMessage } from '../../core/http/api-error-message';
import { ErrorState } from '../../shared/ui/error-state';
import { LanguageService } from '../../core/i18n/language.service';
import { Meter } from '../../shared/charts/meter';
import { MonthColumns, MonthValue } from '../../shared/charts/month-columns';
import { formatCop } from '../../shared/map/routing.api';
import { GlassCard } from '../../shared/ui/glass-card';
import { Skeleton } from '../../shared/ui/skeleton';
import { ToastService } from '../../shared/ui/toast.service';
import {
  CRITERIA,
  DriverStats,
  PassengerStats,
  RatingBlock,
  RatingsApi,
  TargetRole,
  monthLabels,
} from '../ratings/ratings.api';

/** Fila de indicadores: numero grande con su etiqueta. */
@Component({
  selector: 'cp-stat-tiles',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { class: 'grid grid-cols-2 gap-3 sm:grid-cols-4' },
  template: `
    @for (tile of tiles(); track tile.label) {
      <div class="glass-1 !rounded-2xl p-4">
        <p class="text-sm text-muted">{{ tile.label }}</p>
        <p class="text-2xl font-bold">{{ tile.value }}</p>
        @if (tile.hint) {
          <p class="text-xs text-muted">{{ tile.hint }}</p>
        }
      </div>
    }
  `,
})
export class StatTiles {
  readonly tiles = input.required<{ label: string; value: string; hint?: string }[]>();
}

/** Calificacion recibida: promedio general y una barra por criterio (sobre 5). */
@Component({
  selector: 'cp-rating-breakdown',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [TranslocoPipe, Meter, LucideStar],
  template: `
    <h3 class="mb-2 flex items-center gap-2 font-semibold">
      <svg lucideStar class="size-4 text-warning" aria-hidden="true"></svg>
      @if (rating().average !== null) {
        {{
          'stats.ratingAverage'
            | transloco: { value: fixed(rating().average), count: rating().count }
        }}
      } @else {
        {{ 'stats.noRatings' | transloco }}
      }
    </h3>
    @if (rating().average !== null) {
      <div class="flex flex-col gap-3">
        @for (criterion of criteria(); track criterion) {
          <cp-meter
            [label]="'ratings.criteria.' + criterion | transloco"
            [value]="rating().criteria[criterion] ?? null"
            [max]="5"
            [display]="fixed(rating().criteria[criterion] ?? null) + ' / 5'"
          />
        }
      </div>
    }
  `,
})
export class RatingBreakdown {
  readonly rating = input.required<RatingBlock>();
  /** A quien califican (no se llama "role" para no chocar con el atributo ARIA). */
  readonly target = input.required<TargetRole>();
  private readonly language = inject(LanguageService);
  protected readonly criteria = computed(() => CRITERIA[this.target()]);

  protected fixed(value: number | null): string {
    return value === null
      ? '-'
      : value.toLocaleString(this.language.current(), { maximumFractionDigits: 1 });
  }
}

/** Metricas del pasajero en su perfil: viajes, aporte total, lugares y meses. */
@Component({
  selector: 'cp-passenger-metrics',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    TranslocoPipe,
    ErrorState,
    GlassCard,
    Meter,
    MonthColumns,
    RatingBreakdown,
    Skeleton,
    StatTiles,
  ],
  template: `
    <cp-glass-card class="flex flex-col gap-5">
      <h2 class="text-lg font-bold">{{ 'stats.passengerTitle' | transloco }}</h2>
      @if (stats(); as s) {
        <cp-stat-tiles [tiles]="tiles()" />
        <cp-month-columns
          [title]="'stats.tripsByMonth' | transloco"
          [valueLabel]="'stats.trips' | transloco"
          [items]="months()"
        />
        <section aria-labelledby="top-origins">
          <h3 id="top-origins" class="mb-2 font-semibold">{{ 'stats.topOrigins' | transloco }}</h3>
          @for (place of s.top_origins; track place.name) {
            <cp-meter
              class="mb-2"
              [label]="place.name"
              [value]="place.count"
              [max]="s.top_origins[0].count"
              [display]="'stats.tripsCount' | transloco: { count: place.count }"
            />
          } @empty {
            <p class="text-sm text-muted">{{ 'stats.noTrips' | transloco }}</p>
          }
        </section>
        <cp-rating-breakdown [rating]="s.rating" target="passenger" />
      } @else if (loadError(); as message) {
        <cp-error-state [message]="message" (retry)="load()" />
      } @else {
        <cp-skeleton [lines]="4" />
      }
    </cp-glass-card>
  `,
})
export class PassengerMetrics {
  private readonly api = inject(RatingsApi);
  private readonly language = inject(LanguageService);
  private readonly transloco = inject(TranslocoService);
  private readonly toast = inject(ToastService);

  protected readonly stats = signal<PassengerStats | null>(null);
  protected readonly loadError = signal<string | null>(null);
  protected readonly tiles = computed(() => {
    const s = this.stats();
    if (!s) return [];
    const t = (key: string) => this.transloco.translate(key);
    return [
      { label: t('stats.trips'), value: String(s.trips) },
      {
        label: t('stats.spent'),
        value: formatCop(s.spent, this.language.current()),
        hint: t('stats.spentHint'),
      },
      { label: t('stats.cancellations'), value: String(s.cancellations) },
      { label: t('stats.noShows'), value: String(s.no_shows) },
    ];
  });
  protected readonly months = computed<MonthValue[]>(() =>
    (this.stats()?.by_month ?? []).map((m) => ({
      ...monthLabels(m.month, this.language.current()),
      value: m.trips,
      display: this.transloco.translate('stats.tripsCount', { count: m.trips }),
    })),
  );

  constructor() {
    void this.load();
  }

  protected async load(): Promise<void> {
    this.loadError.set(null);
    try {
      this.stats.set(await this.api.passengerStats());
    } catch (error) {
      this.loadError.set(apiErrorMessage(this.transloco, error));
    }
  }
}

/** Estadisticas del conductor: viajes, ocupacion, aportes, calificacion y cancelaciones. */
@Component({
  selector: 'cp-driver-stats',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    TranslocoPipe,
    ErrorState,
    GlassCard,
    Meter,
    MonthColumns,
    RatingBreakdown,
    Skeleton,
    StatTiles,
  ],
  template: `
    <div class="mx-auto flex max-w-4xl flex-col gap-5 py-2">
      <header>
        <h1 class="text-2xl font-bold sm:text-3xl">{{ 'stats.driverTitle' | transloco }}</h1>
        <p class="text-muted">{{ 'stats.driverSubtitle' | transloco }}</p>
      </header>
      @if (stats(); as s) {
        <cp-stat-tiles [tiles]="tiles()" />
        <div class="grid gap-5 lg:grid-cols-2">
          <cp-glass-card class="flex flex-col gap-4">
            <cp-meter
              [label]="'stats.occupancy' | transloco"
              [value]="s.occupancy"
              [max]="1"
              [display]="percent(s.occupancy)"
            />
            <p class="text-xs text-muted">{{ 'stats.occupancyHint' | transloco }}</p>
            <cp-meter
              [label]="'stats.confirmed' | transloco"
              [value]="s.confirmed_contributions"
              [max]="s.contributions || 1"
              [display]="money(s.confirmed_contributions) + ' / ' + money(s.contributions)"
            />
          </cp-glass-card>
          <cp-glass-card>
            <cp-rating-breakdown [rating]="s.rating" target="driver" />
          </cp-glass-card>
        </div>
        <cp-glass-card>
          <cp-month-columns
            [title]="'stats.tripsByMonth' | transloco"
            [valueLabel]="'stats.trips' | transloco"
            [items]="months()"
          />
        </cp-glass-card>
      } @else if (loadError(); as message) {
        <cp-glass-card><cp-error-state [message]="message" (retry)="load()" /></cp-glass-card>
      } @else {
        <cp-glass-card><cp-skeleton [lines]="5" /></cp-glass-card>
      }
    </div>
  `,
})
export default class DriverStatsPage {
  private readonly api = inject(RatingsApi);
  private readonly language = inject(LanguageService);
  private readonly transloco = inject(TranslocoService);
  private readonly toast = inject(ToastService);

  protected readonly stats = signal<DriverStats | null>(null);
  protected readonly loadError = signal<string | null>(null);
  protected readonly tiles = computed(() => {
    const s = this.stats();
    if (!s) return [];
    const t = (key: string) => this.transloco.translate(key);
    return [
      { label: t('stats.trips'), value: String(s.trips) },
      { label: t('stats.passengers'), value: String(s.passengers) },
      {
        label: t('stats.contributions'),
        value: this.money(s.contributions),
        hint: t('stats.spentHint'),
      },
      { label: t('stats.driverCancellations'), value: String(s.cancellations) },
    ];
  });
  protected readonly months = computed<MonthValue[]>(() =>
    (this.stats()?.by_month ?? []).map((m) => ({
      ...monthLabels(m.month, this.language.current()),
      value: m.trips,
      display: this.transloco.translate('stats.tripsCount', { count: m.trips }),
    })),
  );

  constructor() {
    void this.load();
  }

  protected async load(): Promise<void> {
    this.loadError.set(null);
    try {
      this.stats.set(await this.api.driverStats());
    } catch (error) {
      this.loadError.set(apiErrorMessage(this.transloco, error));
    }
  }

  protected money(amount: number): string {
    return formatCop(amount, this.language.current());
  }

  protected percent(value: number | null): string {
    return value === null
      ? '-'
      : value.toLocaleString(this.language.current(), {
          style: 'percent',
          maximumFractionDigits: 0,
        });
  }
}
