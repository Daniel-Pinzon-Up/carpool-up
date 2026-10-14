import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { TranslocoPipe, TranslocoService } from '@jsverse/transloco';
import { LucideCarFront, LucideInbox, LucidePlus } from '@icons';
import { apiErrorMessage } from '../../core/http/api-error-message';
import { EmptyState } from '../../shared/ui/empty-state';
import { GlassButton } from '../../shared/ui/glass-button';
import { GlassCard } from '../../shared/ui/glass-card';
import { GlassTabs, TabItem } from '../../shared/ui/glass-tabs';
import { ErrorState } from '../../shared/ui/error-state';
import { Skeleton } from '../../shared/ui/skeleton';
import { DriverHistoryItem } from '../ratings/history-items';
import { DriverHistoryEntry, RatingsApi } from '../ratings/ratings.api';
import { TripCard } from './trip-card';
import { TripSummary, TripsApi } from './trips.api';

type Tab = 'upcoming' | 'history';

/** Mis viajes del conductor: proximos e historial. */
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
    TripCard,
    DriverHistoryItem,
    LucideInbox,
    LucidePlus,
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

  protected readonly carIcon = LucideCarFront;
  protected readonly tab = signal<Tab>('upcoming');
  protected readonly trips = signal<TripSummary[]>([]);
  /** Viajes pasados con pasajeros, aportes y calificaciones pendientes. */
  protected readonly history = signal<DriverHistoryEntry[]>([]);
  private readonly ratings = inject(RatingsApi);
  protected readonly cursor = signal<string | null>(null);
  protected readonly loading = signal(true);
  protected readonly loadingMore = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly tabs = computed<TabItem[]>(() =>
    (['upcoming', 'history'] as const).map((id) => ({
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
      if (tab === 'history') {
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
    if (!this.cursor()) return;
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
}
