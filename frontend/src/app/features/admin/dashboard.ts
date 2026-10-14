import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  signal,
  untracked,
} from '@angular/core';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { toSignal } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { TranslocoPipe, TranslocoService } from '@jsverse/transloco';
import { LucideShieldCheck, LucideSiren } from '@icons';
import { apiErrorMessage } from '../../core/http/api-error-message';
import { LOCALE } from '../../core/i18n/locale';
import { Meter } from '../../shared/charts/meter';
import { MonthColumns, MonthValue } from '../../shared/charts/month-columns';
import { GlassCard } from '../../shared/ui/glass-card';
import { GlassSelect } from '../../shared/ui/glass-select';
import { ErrorState } from '../../shared/ui/error-state';
import { Skeleton } from '../../shared/ui/skeleton';
import { ToastService } from '../../shared/ui/toast.service';
import { StatTiles } from '../stats/stats-views';
import { AdminApi, AdminOverview } from './admin.api';

/**
 * Panel: indicadores del periodo elegido (7, 30 o 90 dias). Un solo filtro arriba que
 * cambia todo lo de abajo.
 */
@Component({
  selector: 'cp-admin-dashboard',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    ReactiveFormsModule,
    RouterLink,
    TranslocoPipe,
    GlassCard,
    GlassSelect,
    Meter,
    MonthColumns,
    ErrorState,
    Skeleton,
    StatTiles,
    LucideShieldCheck,
    LucideSiren,
  ],
  template: `
    <div class="mx-auto flex max-w-6xl flex-col gap-5 py-2">
      <header class="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 class="text-2xl font-bold sm:text-3xl">{{ 'admin.dashboard.title' | transloco }}</h1>
          <p class="text-muted">{{ 'admin.dashboard.subtitle' | transloco }}</p>
        </div>
        <cp-glass-select
          class="w-48"
          [formControl]="period"
          [label]="'admin.dashboard.period' | transloco"
          [options]="periods()"
        />
      </header>

      @if (data(); as d) {
        <div class="flex flex-wrap gap-3">
          <a
            routerLink="/admin/aprobaciones"
            class="glass-1 !rounded-2xl flex min-h-11 items-center gap-2 px-4 py-2 font-semibold"
          >
            <svg lucideShieldCheck class="size-5 text-primary" aria-hidden="true"></svg>
            {{ 'admin.dashboard.pendingApprovals' | transloco: { count: d.pending_approvals } }}
          </a>
          <a
            routerLink="/admin/emergencias"
            class="glass-1 !rounded-2xl flex min-h-11 items-center gap-2 px-4 py-2 font-semibold"
            [class.text-danger]="d.open_emergencies > 0"
          >
            <svg lucideSiren class="size-5" aria-hidden="true"></svg>
            {{ 'admin.dashboard.openEmergencies' | transloco: { count: d.open_emergencies } }}
          </a>
        </div>
        <cp-stat-tiles [tiles]="tiles()" />

        <div class="grid gap-5 lg:grid-cols-2">
          <cp-glass-card>
            <cp-month-columns
              [title]="'admin.dashboard.perDay' | transloco"
              [keyLabel]="'admin.dashboard.day' | transloco"
              [valueLabel]="'stats.trips' | transloco"
              [items]="perDay()"
            />
          </cp-glass-card>
          <cp-glass-card>
            <cp-month-columns
              [title]="'admin.dashboard.perHour' | transloco"
              [keyLabel]="'admin.dashboard.hourHeader' | transloco"
              [valueLabel]="'stats.trips' | transloco"
              [items]="perHour()"
            />
          </cp-glass-card>
          <cp-glass-card class="flex flex-col gap-3">
            <h2 class="font-semibold">{{ 'admin.dashboard.routes' | transloco }}</h2>
            @for (route of d.top_routes; track route.origin + route.destination) {
              <cp-meter
                [label]="route.origin + ' → ' + route.destination"
                [value]="route.count"
                [max]="d.top_routes[0].count"
                [display]="'stats.tripsCount' | transloco: { count: route.count }"
              />
            } @empty {
              <p class="text-sm text-muted">{{ 'admin.dashboard.noData' | transloco }}</p>
            }
          </cp-glass-card>
          <cp-glass-card class="flex flex-col gap-4">
            <cp-meter
              [label]="'stats.occupancy' | transloco"
              [value]="d.occupancy"
              [max]="1"
              [display]="percent(d.occupancy)"
            />
            <cp-month-columns
              [title]="'admin.dashboard.ratings' | transloco"
              [keyLabel]="'admin.dashboard.starsHeader' | transloco"
              [valueLabel]="'admin.dashboard.ratingCount' | transloco"
              [items]="ratings()"
            />
          </cp-glass-card>
          <cp-glass-card class="lg:col-span-2">
            <h2 class="mb-2 font-semibold">{{ 'admin.dashboard.users' | transloco }}</h2>
            <table class="w-full text-left text-sm">
              <thead>
                <tr class="text-muted">
                  <th scope="col" class="py-1 font-medium">{{ 'admin.users.role' | transloco }}</th>
                  @for (status of statuses; track status) {
                    <th scope="col" class="py-1 text-right font-medium">
                      {{ 'admin.users.statuses.' + status | transloco }}
                    </th>
                  }
                </tr>
              </thead>
              <tbody>
                @for (role of roles; track role) {
                  <tr class="border-t border-glass-border">
                    <th scope="row" class="py-1.5 font-normal">
                      {{ 'roles.' + role | transloco }}
                    </th>
                    @for (status of statuses; track status) {
                      <td class="py-1.5 text-right">{{ userCount(role, status) }}</td>
                    }
                  </tr>
                }
              </tbody>
            </table>
          </cp-glass-card>
        </div>
      } @else if (loadError(); as message) {
        <cp-glass-card><cp-error-state [message]="message" (retry)="load(days())" /></cp-glass-card>
      } @else {
        <cp-glass-card><cp-skeleton [lines]="6" /></cp-glass-card>
      }
    </div>
  `,
})
export default class AdminDashboard {
  private readonly api = inject(AdminApi);
  private readonly transloco = inject(TranslocoService);
  private readonly toast = inject(ToastService);

  protected readonly roles = ['passenger', 'driver', 'admin', 'superadmin'];
  protected readonly statuses = [
    'active',
    'pending_email',
    'pending_approval',
    'suspended',
    'blocked',
  ];
  protected readonly period = new FormControl('30', { nonNullable: true });
  protected readonly days = toSignal(this.period.valueChanges, { initialValue: '30' });
  protected readonly data = signal<AdminOverview | null>(null);
  protected readonly loadError = signal<string | null>(null);

  protected readonly periods = computed(() => {
    return ['7', '30', '90'].map((value) => ({
      value,
      label: this.transloco.translate('admin.dashboard.lastDays', { count: value }),
    }));
  });
  protected readonly tiles = computed(() => {
    const d = this.data();
    if (!d) return [];
    const t = (key: string) => this.transloco.translate(key);
    return [
      { label: t('admin.dashboard.completed'), value: String(d.trips_completed) },
      { label: t('stats.driverCancellations'), value: String(d.driver_cancellations) },
      {
        label: t('admin.dashboard.passengerCancellations'),
        value: String(d.passenger_cancellations),
      },
      { label: t('stats.noShows'), value: String(d.no_shows) },
    ];
  });
  protected readonly perDay = computed<MonthValue[]>(() =>
    (this.data()?.trips_per_day ?? []).map(({ day, count }) => {
      const [y, m, dd] = day.split('-').map(Number);
      const date = new Date(Date.UTC(y, m - 1, dd));
      const lang = LOCALE;
      return {
        label: date.toLocaleDateString(lang, { day: 'numeric', timeZone: 'UTC' }),
        title: date.toLocaleDateString(lang, {
          weekday: 'short',
          day: 'numeric',
          month: 'short',
          timeZone: 'UTC',
        }),
        value: count,
        display: this.transloco.translate('stats.tripsCount', { count }),
      };
    }),
  );
  protected readonly perHour = computed<MonthValue[]>(() =>
    (this.data()?.trips_per_hour ?? []).map((count, hour) => ({
      label: String(hour),
      title: this.transloco.translate('admin.dashboard.hour', { hour }),
      value: count,
      display: this.transloco.translate('stats.tripsCount', { count }),
    })),
  );
  protected readonly ratings = computed<MonthValue[]>(() =>
    (this.data()?.rating_distribution ?? []).map((count, index) => ({
      label: String(index + 1),
      title: this.transloco.translate('admin.dashboard.stars', { count: index + 1 }),
      value: count,
      display: String(count),
    })),
  );

  constructor() {
    effect(() => {
      const days = Number(this.days());
      untracked(() => void this.load(days));
    });
  }

  protected async load(days: number | string): Promise<void> {
    this.loadError.set(null);
    try {
      this.data.set(await this.api.overview(Number(days)));
    } catch (error) {
      if (this.data()) this.toast.show(apiErrorMessage(this.transloco, error), 'danger');
      else this.loadError.set(apiErrorMessage(this.transloco, error));
    }
  }

  protected userCount(role: string, status: string): number {
    return this.data()?.users.find((u) => u.key === `${role}:${status}`)?.count ?? 0;
  }

  protected percent(value: number | null): string {
    return value === null
      ? '-'
      : value.toLocaleString(LOCALE, {
          style: 'percent',
          maximumFractionDigits: 0,
        });
  }
}
