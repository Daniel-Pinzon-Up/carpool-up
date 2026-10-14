import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  signal,
  untracked,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { TranslocoPipe, TranslocoService } from '@jsverse/transloco';
import { LucideCalendarX, LucideSearch } from '@icons';
import { apiErrorMessage } from '../../core/http/api-error-message';
import { NotificationsStore } from '../../core/notifications/notifications.store';
import { EmptyState } from '../../shared/ui/empty-state';
import { ErrorState } from '../../shared/ui/error-state';
import { GlassButton } from '../../shared/ui/glass-button';
import { GlassCard } from '../../shared/ui/glass-card';
import { GlassTabs, TabItem } from '../../shared/ui/glass-tabs';
import { Skeleton } from '../../shared/ui/skeleton';
import { ToastService } from '../../shared/ui/toast.service';
import { PassengerHistoryItem } from '../ratings/history-items';
import { PassengerHistoryEntry, RatingsApi } from '../ratings/ratings.api';
import { BookingActions } from './booking-actions';
import { BookingCard } from './booking-card';
import { Booking, BookingsApi } from './bookings.api';

type Tab = 'upcoming' | 'history';

/** Mis viajes del pasajero: proximos e historial. */
@Component({
  selector: 'cp-passenger-trips',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    RouterLink,
    TranslocoPipe,
    BookingCard,
    PassengerHistoryItem,
    EmptyState,
    ErrorState,
    GlassButton,
    GlassCard,
    GlassTabs,
    Skeleton,
    LucideSearch,
  ],
  template: `
    <div class="mx-auto flex max-w-4xl flex-col gap-5 py-2">
      <header class="flex flex-wrap items-center justify-between gap-3">
        <h1 class="text-2xl font-bold sm:text-3xl">{{ 'nav.myTrips' | transloco }}</h1>
        <a cp-button variant="secondary" routerLink="/buscar">
          <svg lucideSearch class="size-4" aria-hidden="true"></svg>
          {{ 'search.title' | transloco }}
        </a>
      </header>

      <cp-glass-tabs
        #tabs
        [tabs]="tabItems()"
        [label]="'nav.myTrips' | transloco"
        [(selected)]="tab"
      />

      <section
        role="tabpanel"
        [id]="tabs.panelId(tab())"
        [attr.aria-labelledby]="tabs.tabId(tab())"
        [attr.aria-busy]="loading()"
        class="flex flex-col gap-3"
      >
        @if (loading()) {
          @for (row of [1, 2]; track row) {
            <cp-glass-card><cp-skeleton [lines]="3" /></cp-glass-card>
          }
        } @else if (loadError(); as message) {
          <cp-glass-card
            ><cp-error-state [message]="message" (retry)="load(tab())"
          /></cp-glass-card>
        } @else if (tab() === 'history') {
          @for (entry of history(); track entry.booking_id) {
            <cp-passenger-history-item [entry]="entry" />
          } @empty {
            <cp-empty-state
              [icon]="emptyIcon"
              [title]="'bookings.empty.history' | transloco"
              [description]="'bookings.empty.hint' | transloco"
              image="brand/car.webp"
            />
          }
          @if (nextCursor()) {
            <button
              cp-button
              variant="secondary"
              type="button"
              class="self-center"
              (click)="more()"
            >
              {{ 'trips.more' | transloco }}
            </button>
          }
        } @else {
          @for (booking of bookings(); track booking.id) {
            <cp-booking-card [booking]="booking">
              @if (cancellable(booking)) {
                <button cp-button variant="danger" type="button" (click)="cancel(booking)">
                  {{ 'bookings.cancel.action' | transloco }}
                </button>
              }
            </cp-booking-card>
          } @empty {
            <cp-empty-state
              [icon]="emptyIcon"
              [title]="'bookings.empty.' + tab() | transloco"
              [description]="'bookings.empty.hint' | transloco"
              image="brand/car.webp"
            >
              <a cp-button routerLink="/buscar">{{ 'search.title' | transloco }}</a>
            </cp-empty-state>
          }
          @if (nextCursor()) {
            <button
              cp-button
              variant="secondary"
              type="button"
              class="self-center"
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
export default class PassengerTrips {
  private readonly api = inject(BookingsApi);
  private readonly actions = inject(BookingActions);
  private readonly toast = inject(ToastService);
  private readonly transloco = inject(TranslocoService);

  protected readonly emptyIcon = LucideCalendarX;
  protected readonly tab = signal<Tab>('upcoming');
  protected readonly tabItems = computed<TabItem[]>(() => {
    return (['upcoming', 'history'] as Tab[]).map((id) => ({
      id,
      label: this.transloco.translate(`bookings.tabs.${id}`),
    }));
  });
  protected readonly loading = signal(true);
  protected readonly loadError = signal<string | null>(null);
  protected readonly bookings = signal<Booking[]>([]);
  protected readonly nextCursor = signal<string | null>(null);
  /** Viajes pasados con ticket y estado de la calificacion. */
  protected readonly history = signal<PassengerHistoryEntry[]>([]);
  private readonly ratings = inject(RatingsApi);

  constructor() {
    effect(() => {
      const tab = this.tab();
      untracked(() => void this.load(tab));
    });
    // Aceptaciones y cancelaciones se ven sin recargar la pagina.
    inject(NotificationsStore)
      .incoming.pipe(takeUntilDestroyed())
      .subscribe((item) => {
        if (item.kind !== 'message_new') void this.load(this.tab());
      });
  }

  protected async load(tab: Tab): Promise<void> {
    this.loading.set(true);
    this.loadError.set(null);
    try {
      if (tab === 'history') {
        const page = await this.ratings.passengerHistory();
        this.history.set(page.items);
        this.nextCursor.set(page.next_cursor);
      } else {
        const page = await this.api.mine(tab);
        this.bookings.set(page.items);
        this.nextCursor.set(page.next_cursor);
      }
    } catch (error) {
      this.loadError.set(apiErrorMessage(this.transloco, error));
    } finally {
      this.loading.set(false);
    }
  }

  protected async more(): Promise<void> {
    const tab = this.tab();
    try {
      if (tab === 'history') {
        const older = await this.ratings.passengerHistory(this.nextCursor());
        this.history.update((list) => [...list, ...older.items]);
        this.nextCursor.set(older.next_cursor);
        return;
      }
      const page = await this.api.mine(tab, this.nextCursor());
      this.bookings.update((list) => [...list, ...page.items]);
      this.nextCursor.set(page.next_cursor);
    } catch (error) {
      this.toast.show(apiErrorMessage(this.transloco, error), 'danger');
    }
  }

  protected cancellable(booking: Booking): boolean {
    return (
      (booking.status === 'requested' || booking.status === 'accepted') &&
      booking.trip.status === 'scheduled'
    );
  }

  protected async cancel(booking: Booking): Promise<void> {
    const result = await this.actions.cancel(booking.id, !booking.free_cancel);
    if (result) await this.load(this.tab());
  }
}
