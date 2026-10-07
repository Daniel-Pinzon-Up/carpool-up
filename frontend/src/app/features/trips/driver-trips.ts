import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { TranslocoPipe, TranslocoService } from '@jsverse/transloco';
import {
  LucideArrowRight,
  LucideCarFront,
  LucideInbox,
  LucidePlus,
  LucideTriangleAlert,
} from '@icons';
import { apiErrorMessage } from '../../core/http/api-error-message';
import { LanguageService } from '../../core/i18n/language.service';
import { EmptyState } from '../../shared/ui/empty-state';
import { GlassButton } from '../../shared/ui/glass-button';
import { GlassCard } from '../../shared/ui/glass-card';
import { GlassTabs, TabItem } from '../../shared/ui/glass-tabs';
import { ErrorState } from '../../shared/ui/error-state';
import { Skeleton } from '../../shared/ui/skeleton';
import { StatusBadge } from '../../shared/ui/status-badge';
import { DriverHistoryItem } from '../ratings/history-items';
import { DriverHistoryEntry, RatingsApi } from '../ratings/ratings.api';
import { TripCard } from './trip-card';
import { SERIES_STATUS_TONE, formatDeparture } from './trip-status';
import { SeriesSummary, TripSummary, TripsApi } from './trips.api';

type Tab = 'upcoming' | 'series' | 'history';

/** Mis viajes del conductor: proximos, series con sus alertas e historial. */
@Component({
  selector: 'cp-driver-trips',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    RouterLink,
    TranslocoPipe,
    EmptyState,
    ErrorState,
    GlassButton,
    GlassCard,
    GlassTabs,
    Skeleton,
    StatusBadge,
    TripCard,
    DriverHistoryItem,
    LucideArrowRight,
    LucideInbox,
    LucidePlus,
    LucideTriangleAlert,
  ],
  template: `
    <div class="mx-auto flex max-w-4xl flex-col gap-6 py-2">
      <header class="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 class="text-2xl font-bold sm:text-3xl">{{ 'trips.title' | transloco }}</h1>
          <p class="text-muted">{{ 'trips.subtitle' | transloco }}</p>
        </div>
        <div class="flex flex-wrap gap-2">
          <a cp-button variant="secondary" routerLink="/solicitudes">
            <svg lucideInbox class="size-4" aria-hidden="true"></svg>
            {{ 'bookings.inbox.title' | transloco }}
          </a>
          <a cp-button routerLink="/publicar">
            <svg lucidePlus class="size-4" aria-hidden="true"></svg>
            {{ 'nav.publish' | transloco }}
          </a>
        </div>
      </header>

      <cp-glass-tabs
        #tabsRef
        [tabs]="tabs()"
        [label]="'trips.title' | transloco"
        [(selected)]="tab"
        (selectedChange)="load()"
      />

      <section
        [id]="tabsRef.panelId(tab())"
        role="tabpanel"
        [attr.aria-labelledby]="tabsRef.tabId(tab())"
        class="flex flex-col gap-3"
      >
        @if (error()) {
          <cp-glass-card><cp-error-state [message]="error()" (retry)="load()" /></cp-glass-card>
        } @else if (loading()) {
          @for (row of [1, 2, 3]; track row) {
            <cp-glass-card><cp-skeleton [lines]="2" /></cp-glass-card>
          }
        } @else if (tab() === 'series') {
          @for (item of series(); track item.id) {
            <a
              [routerLink]="['/series', item.id]"
              class="glass-1 !rounded-2xl flex flex-col gap-2 p-4 transition hover:bg-glass-strong focus-visible:outline-2 focus-visible:outline-primary"
            >
              <div class="flex flex-wrap items-center justify-between gap-2">
                <span class="font-semibold"
                  >{{ days(item.weekdays) }} · {{ item.departure_time.slice(0, 5) }}</span
                >
                <cp-status-badge [variant]="seriesTone(item)">{{
                  'trips.seriesStatus.' + item.status | transloco
                }}</cp-status-badge>
              </div>
              <p class="flex min-w-0 items-center gap-2">
                <span class="truncate">{{ item.origin }}</span>
                <svg lucideArrowRight class="size-4 shrink-0 text-muted" aria-hidden="true"></svg>
                <span class="sr-only">{{ 'trips.to' | transloco }}</span>
                <span class="truncate">{{ item.destination }}</span>
              </p>
              <p class="text-sm text-muted">
                {{
                  'trips.seriesCounts'
                    | transloco: { scheduled: item.counts.scheduled, total: item.counts.total }
                }}
                @if (item.next_departure) {
                  · {{ 'trips.next' | transloco: { when: when(item.next_departure) } }}
                }
              </p>
              @if (item.counts.pico_placa) {
                <p class="flex items-center gap-2 text-sm">
                  <svg
                    lucideTriangleAlert
                    class="size-4 shrink-0 text-warning"
                    aria-hidden="true"
                  ></svg>
                  {{ 'trips.picoPlacaAlert' | transloco: { count: item.counts.pico_placa } }}
                </p>
              }
            </a>
          } @empty {
            <cp-empty-state
              image="brand/car.webp"
              [title]="'trips.empty.series' | transloco"
              [description]="'trips.empty.seriesHint' | transloco"
              [icon]="carIcon"
            />
          }
        } @else if (tab() === 'history') {
          @for (entry of history(); track entry.trip_id) {
            <cp-driver-history-item [entry]="entry" />
          } @empty {
            <cp-empty-state
              image="brand/car.webp"
              [title]="'trips.empty.history' | transloco"
              [description]="'trips.empty.hint' | transloco"
              [icon]="carIcon"
            />
          }
        } @else {
          @for (trip of trips(); track trip.id) {
            <cp-trip-card [trip]="trip" />
          } @empty {
            <cp-empty-state
              image="brand/car.webp"
              [title]="'trips.empty.' + tab() | transloco"
              [description]="'trips.empty.hint' | transloco"
              [icon]="carIcon"
            />
          }
          @if (cursor()) {
            <button
              cp-button
              variant="secondary"
              type="button"
              class="self-center"
              [disabled]="loadingMore()"
              (click)="more()"
            >
              {{ 'trips.more' | transloco }}
            </button>
          }
        }
      </section>
    </div>
  `,
})
export default class DriverTrips {
  private readonly api = inject(TripsApi);
  private readonly transloco = inject(TranslocoService);
  private readonly language = inject(LanguageService);

  protected readonly carIcon = LucideCarFront;
  protected readonly tab = signal<Tab>('upcoming');
  protected readonly trips = signal<TripSummary[]>([]);
  /** Viajes pasados con pasajeros, aportes y calificaciones pendientes. */
  protected readonly history = signal<DriverHistoryEntry[]>([]);
  private readonly ratings = inject(RatingsApi);
  protected readonly series = signal<SeriesSummary[]>([]);
  protected readonly cursor = signal<string | null>(null);
  protected readonly loading = signal(true);
  protected readonly loadingMore = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly tabs = computed<TabItem[]>(() =>
    (['upcoming', 'series', 'history'] as const).map((id) => ({
      id,
      label: this.transloco.translate(`trips.tabs.${id}`),
    })),
  );

  constructor() {
    void this.load();
  }

  protected async load(): Promise<void> {
    this.loading.set(true);
    this.error.set(null);
    try {
      const tab = this.tab();
      if (tab === 'series') {
        this.series.set(await this.api.mySeries());
      } else if (tab === 'history') {
        const page = await this.ratings.driverHistory();
        this.history.set(page.items);
        this.cursor.set(page.next_cursor);
      } else {
        const page = await this.api.myTrips(tab);
        this.trips.set(page.items);
        this.cursor.set(page.next_cursor);
      }
    } catch (error) {
      this.error.set(apiErrorMessage(this.transloco, error));
    } finally {
      this.loading.set(false);
    }
  }

  protected async more(): Promise<void> {
    const tab = this.tab();
    if (tab === 'series' || !this.cursor()) return;
    this.loadingMore.set(true);
    try {
      if (tab === 'history') {
        const older = await this.ratings.driverHistory(this.cursor());
        this.history.update((list) => [...list, ...older.items]);
        this.cursor.set(older.next_cursor);
        return;
      }
      const page = await this.api.myTrips(tab, this.cursor());
      this.trips.update((list) => [...list, ...page.items]);
      this.cursor.set(page.next_cursor);
    } catch (error) {
      this.error.set(apiErrorMessage(this.transloco, error));
    } finally {
      this.loadingMore.set(false);
    }
  }

  protected seriesTone(item: SeriesSummary) {
    return SERIES_STATUS_TONE[item.status];
  }

  protected when(iso: string): string {
    return formatDeparture(iso, this.language.current());
  }

  protected days(weekdays: number[]): string {
    return weekdays
      .map((day) =>
        new Date(Date.UTC(2026, 0, 5 + day)).toLocaleDateString(this.language.current(), {
          weekday: 'short',
          timeZone: 'UTC',
        }),
      )
      .join(', ');
  }
}
