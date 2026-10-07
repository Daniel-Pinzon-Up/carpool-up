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
import { LucideArrowRight, LucideCalendarX, LucideHourglass, LucideSearch } from '@lucide/angular';
import { apiErrorMessage } from '../../core/http/api-error-message';
import { NotificationsStore } from '../../core/notifications/notifications.store';
import { LanguageService } from '../../core/i18n/language.service';
import { EmptyState } from '../../shared/ui/empty-state';
import { ErrorState } from '../../shared/ui/error-state';
import { GlassButton } from '../../shared/ui/glass-button';
import { GlassCard } from '../../shared/ui/glass-card';
import { GlassTabs, TabItem } from '../../shared/ui/glass-tabs';
import { Skeleton } from '../../shared/ui/skeleton';
import { StatusBadge } from '../../shared/ui/status-badge';
import { ToastService } from '../../shared/ui/toast.service';
import { formatDeparture, formatTime } from '../trips/trip-status';
import { PassengerHistoryItem } from '../ratings/history-items';
import { PassengerHistoryEntry, RatingsApi } from '../ratings/ratings.api';
import { BookingActions } from './booking-actions';
import { BookingCard } from './booking-card';
import {
  Booking,
  BookingsApi,
  SUBSCRIPTION_STATUS_TONE,
  Subscription,
  WaitlistEntry,
} from './bookings.api';

type Tab = 'upcoming' | 'history' | 'series' | 'waitlist';

/** Mis viajes del pasajero: proximos, historial, series a las que se unio y lista de espera. */
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
    StatusBadge,
    LucideArrowRight,
    LucideHourglass,
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
        } @else if (tab() === 'upcoming') {
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
        } @else if (tab() === 'series') {
          @for (sub of subscriptions(); track sub.id) {
            <article class="glass-1 !rounded-2xl flex flex-col gap-2 p-4">
              <div class="flex flex-wrap items-start justify-between gap-2">
                <a
                  [routerLink]="['/series', sub.series.id]"
                  class="flex min-w-0 items-center gap-2 font-semibold underline-offset-4 hover:underline"
                >
                  <span class="truncate">{{ sub.series.origin }}</span>
                  <svg lucideArrowRight class="size-4 shrink-0 text-muted" aria-hidden="true"></svg>
                  <span class="sr-only">{{ 'trips.to' | transloco }}</span>
                  <span class="truncate">{{ sub.series.destination }}</span>
                </a>
                <cp-status-badge [variant]="subTone(sub)">{{
                  'bookings.subscriptionStatus.' + sub.status | transloco
                }}</cp-status-badge>
              </div>
              <p class="text-sm">
                {{ sub.series.departure_time.slice(0, 5) }} ·
                {{
                  'bookings.subscription.range'
                    | transloco: { start: date(sub.from_date), end: date(sub.to_date) }
                }}
              </p>
              @if (sub.status === 'active') {
                <p class="text-sm text-muted">
                  {{
                    'bookings.subscription.summary'
                      | transloco
                        : { booked: sub.booked_dates.length, skipped: sub.skipped_dates.length }
                  }}
                </p>
              }
              @if (sub.reject_reason) {
                <p class="text-sm text-muted">
                  <span class="font-semibold">{{ 'trips.cancelReason' | transloco }}:</span>
                  {{ sub.reject_reason }}
                </p>
              }
              @if (sub.status === 'requested' || sub.status === 'active') {
                <button
                  cp-button
                  variant="danger"
                  type="button"
                  class="self-start"
                  (click)="cancelSubscription(sub)"
                >
                  {{ 'bookings.subscription.cancel' | transloco }}
                </button>
              }
            </article>
          } @empty {
            <cp-empty-state
              [icon]="emptyIcon"
              [title]="'bookings.empty.series' | transloco"
              [description]="'bookings.empty.seriesHint' | transloco"
            />
          }
        } @else {
          @for (entry of waitlist(); track entry.id) {
            <article class="glass-1 !rounded-2xl flex flex-col gap-2 p-4">
              <a
                [routerLink]="['/viajes', entry.trip.id]"
                class="font-semibold underline-offset-4 hover:underline"
              >
                {{ when(entry.trip.departs_at) }} · {{ entry.trip.origin }} –
                {{ entry.trip.destination }}
              </a>
              @if (entry.status === 'offered') {
                <p class="flex gap-2 text-sm font-semibold" role="status">
                  <svg lucideHourglass class="size-4 shrink-0 text-accent" aria-hidden="true"></svg>
                  {{
                    'bookings.waitlist.offer'
                      | transloco: { time: time(entry.offer_expires_at ?? '') }
                  }}
                </p>
                <div class="flex flex-wrap gap-2">
                  <button cp-button type="button" (click)="confirm(entry)">
                    {{ 'bookings.waitlist.confirm' | transloco }}
                  </button>
                  <button cp-button variant="secondary" type="button" (click)="decline(entry)">
                    {{ 'bookings.waitlist.decline' | transloco }}
                  </button>
                </div>
              } @else {
                <p class="text-sm text-muted">
                  {{ 'bookings.waitlist.position' | transloco: { ahead: entry.ahead } }}
                </p>
              }
            </article>
          } @empty {
            <cp-empty-state
              [icon]="emptyIcon"
              [title]="'bookings.empty.waitlist' | transloco"
              [description]="'bookings.empty.waitlistHint' | transloco"
            />
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
  private readonly language = inject(LanguageService);

  protected readonly emptyIcon = LucideCalendarX;
  protected readonly tab = signal<Tab>('upcoming');
  protected readonly tabItems = computed<TabItem[]>(() => {
    this.language.current();
    return (['upcoming', 'history', 'series', 'waitlist'] as Tab[]).map((id) => ({
      id,
      label: this.transloco.translate(`bookings.tabs.${id}`),
    }));
  });
  protected readonly loading = signal(true);
  protected readonly loadError = signal<string | null>(null);
  protected readonly bookings = signal<Booking[]>([]);
  protected readonly nextCursor = signal<string | null>(null);
  protected readonly subscriptions = signal<Subscription[]>([]);
  protected readonly waitlist = signal<WaitlistEntry[]>([]);
  /** Viajes pasados con ticket y estado de la calificacion. */
  protected readonly history = signal<PassengerHistoryEntry[]>([]);
  private readonly ratings = inject(RatingsApi);

  constructor() {
    effect(() => {
      const tab = this.tab();
      untracked(() => void this.load(tab));
    });
    // Aceptaciones, ofertas de cupo y cancelaciones se ven sin recargar la pagina.
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
      if (tab === 'series') {
        this.subscriptions.set(await this.api.mySubscriptions());
      } else if (tab === 'waitlist') {
        this.waitlist.set(await this.api.myWaitlist());
      } else if (tab === 'history') {
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
    if (tab !== 'upcoming' && tab !== 'history') return;
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

  protected async cancelSubscription(sub: Subscription): Promise<void> {
    if (await this.actions.cancelSubscription(sub.id)) await this.load('series');
  }

  private async respond(action: () => Promise<unknown>, done: string): Promise<void> {
    try {
      await action();
      this.toast.show(this.transloco.translate(done), 'success');
      await this.load('waitlist');
    } catch (error) {
      this.toast.show(apiErrorMessage(this.transloco, error), 'danger');
    }
  }

  protected confirm(entry: WaitlistEntry): Promise<void> {
    return this.respond(() => this.api.confirmOffer(entry.id), 'bookings.panel.sent');
  }

  protected decline(entry: WaitlistEntry): Promise<void> {
    return this.respond(() => this.api.declineOffer(entry.id), 'bookings.waitlist.left');
  }

  protected subTone(sub: Subscription) {
    return SUBSCRIPTION_STATUS_TONE[sub.status];
  }

  protected when(iso: string): string {
    return formatDeparture(iso, this.language.current());
  }

  protected time(iso: string): string {
    return iso ? formatTime(iso, this.language.current()) : '';
  }

  protected date(value: string): string {
    const [y, m, d] = value.split('-').map(Number);
    return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString(this.language.current(), {
      day: 'numeric',
      month: 'short',
      timeZone: 'UTC',
    });
  }
}
