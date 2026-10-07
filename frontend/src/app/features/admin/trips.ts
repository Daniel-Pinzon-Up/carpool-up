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
import { FormControl, FormGroup, ReactiveFormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { TranslocoPipe, TranslocoService } from '@jsverse/transloco';
import {
  LucideArrowLeft,
  LucideCalendarX,
  LucideEye,
  LucideEyeOff,
  LucideMessageCircle,
  LucideSearch,
  LucideSiren,
} from '@lucide/angular';
import { firstValueFrom } from 'rxjs';
import { apiErrorMessage } from '../../core/http/api-error-message';
import { LanguageService } from '../../core/i18n/language.service';
import { DialogService } from '../../shared/ui/dialog.service';
import { EmptyState } from '../../shared/ui/empty-state';
import { ErrorState } from '../../shared/ui/error-state';
import { GlassButton } from '../../shared/ui/glass-button';
import { GlassCard } from '../../shared/ui/glass-card';
import { GlassInput } from '../../shared/ui/glass-input';
import { GlassSelect } from '../../shared/ui/glass-select';
import { Skeleton } from '../../shared/ui/skeleton';
import { BadgeTone, StatusBadge } from '../../shared/ui/status-badge';
import { ToastService } from '../../shared/ui/toast.service';
import { BOOKING_STATUS_TONE, BookingStatus } from '../bookings/bookings.api';
import { ReasonDialog, ReasonDialogData, ReasonResult } from '../bookings/reason-dialog';
import { TRIP_STATUS_TONE, formatDeparture } from '../trips/trip-status';
import { TripStatus } from '../trips/trips.api';
import { AdminApi, AdminMessage, AdminTripDetail, AdminTripRow } from './admin.api';

/** Viajes: monitoreo por estado, dia y texto (ruta o conductor). */
@Component({
  selector: 'cp-admin-trips',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    ReactiveFormsModule,
    RouterLink,
    TranslocoPipe,
    EmptyState,
    ErrorState,
    GlassButton,
    GlassCard,
    GlassInput,
    GlassSelect,
    Skeleton,
    StatusBadge,
    LucideSearch,
    LucideSiren,
  ],
  template: `
    <div class="mx-auto flex max-w-5xl flex-col gap-5 py-2">
      <h1 class="text-2xl font-bold sm:text-3xl">{{ 'nav.trips' | transloco }}</h1>
      <cp-glass-card>
        <form
          [formGroup]="filters"
          class="grid gap-3 sm:grid-cols-[1fr_12rem_11rem_auto] sm:items-end"
          (ngSubmit)="search()"
        >
          <cp-glass-input
            formControlName="q"
            type="search"
            [label]="'admin.trips.search' | transloco"
          />
          <cp-glass-select
            formControlName="status"
            [label]="'admin.users.status' | transloco"
            [options]="statusOptions()"
          />
          <cp-glass-input
            formControlName="day"
            type="date"
            [label]="'admin.trips.day' | transloco"
          />
          <button cp-button type="submit">
            <svg lucideSearch class="size-4" aria-hidden="true"></svg>
            {{ 'search.submit' | transloco }}
          </button>
        </form>
      </cp-glass-card>
      @if (loadError(); as message) {
        <cp-glass-card><cp-error-state [message]="message" (retry)="search()" /></cp-glass-card>
      } @else if (rows() === null) {
        <cp-glass-card><cp-skeleton [lines]="5" /></cp-glass-card>
      } @else {
        <ul class="flex flex-col gap-2">
          @for (trip of rows(); track trip.id) {
            <li>
              <a
                [routerLink]="['/admin/viajes', trip.id]"
                class="glass-1 !rounded-2xl flex flex-wrap items-center gap-3 p-4 transition hover:bg-glass-strong"
              >
                <span class="min-w-0 flex-1">
                  <span class="block truncate font-semibold"
                    >{{ trip.origin }} → {{ trip.destination }}</span
                  >
                  <span class="block truncate text-sm text-muted">
                    {{ when(trip.departs_at) }} · {{ trip.driver_name }} ·
                    {{
                      'admin.trips.seats'
                        | transloco: { booked: trip.seats_booked, total: trip.seats_total }
                    }}
                  </span>
                </span>
                @if (trip.open_emergencies > 0) {
                  <span class="inline-flex items-center gap-1 text-sm font-semibold text-danger">
                    <svg lucideSiren class="size-4" aria-hidden="true"></svg>
                    {{ 'admin.trips.emergencies' | transloco: { count: trip.open_emergencies } }}
                  </span>
                }
                <cp-status-badge [variant]="tone(trip.status)">{{
                  'trips.status.' + trip.status | transloco
                }}</cp-status-badge>
              </a>
            </li>
          } @empty {
            <li><cp-empty-state [title]="'admin.trips.none' | transloco" /></li>
          }
        </ul>
        @if (cursor()) {
          <button
            cp-button
            variant="secondary"
            type="button"
            class="self-center"
            (click)="search(true)"
          >
            {{ 'trips.more' | transloco }}
          </button>
        }
      }
    </div>
  `,
})
export default class AdminTrips {
  private readonly api = inject(AdminApi);
  private readonly transloco = inject(TranslocoService);
  private readonly language = inject(LanguageService);
  private readonly toast = inject(ToastService);

  protected readonly filters = new FormGroup({
    q: new FormControl('', { nonNullable: true }),
    status: new FormControl('', { nonNullable: true }),
    day: new FormControl('', { nonNullable: true }),
  });
  protected readonly rows = signal<AdminTripRow[] | null>(null);
  protected readonly loadError = signal<string | null>(null);
  protected readonly cursor = signal<string | null>(null);
  protected readonly statusOptions = computed(() => {
    this.language.current();
    return [
      { value: '', label: this.transloco.translate('admin.users.any') },
      ...Object.keys(TRIP_STATUS_TONE).map((value) => ({
        value,
        label: this.transloco.translate(`trips.status.${value}`),
      })),
    ];
  });

  constructor() {
    void this.search();
  }

  protected async search(more = false): Promise<void> {
    if (!more) this.loadError.set(null);
    try {
      const page = await this.api.trips({
        ...this.filters.getRawValue(),
        cursor: more ? this.cursor() : null,
      });
      this.rows.update((list) => (more ? [...(list ?? []), ...page.items] : page.items));
      this.cursor.set(page.next_cursor);
    } catch (error) {
      if (more) this.toast.show(apiErrorMessage(this.transloco, error), 'danger');
      else this.loadError.set(apiErrorMessage(this.transloco, error));
    }
  }

  protected tone(status: TripStatus): BadgeTone {
    return TRIP_STATUS_TONE[status];
  }

  protected when(iso: string): string {
    return formatDeparture(iso, this.language.current());
  }
}

/**
 * Detalle de un viaje para el administrador: reservas, emergencias, cancelacion y, solo
 * si hace falta, el chat (abrirlo queda en la auditoria).
 */
@Component({
  selector: 'cp-admin-trip-detail',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    RouterLink,
    TranslocoPipe,
    GlassButton,
    ErrorState,
    GlassCard,
    Skeleton,
    StatusBadge,
    LucideArrowLeft,
    LucideCalendarX,
    LucideEye,
    LucideEyeOff,
    LucideMessageCircle,
    LucideSiren,
  ],
  template: `
    <div class="mx-auto flex max-w-4xl flex-col gap-5 py-2">
      <a
        routerLink="/admin/viajes"
        class="inline-flex min-h-11 items-center gap-2 self-start text-primary"
      >
        <svg lucideArrowLeft class="size-4" aria-hidden="true"></svg>
        {{ 'nav.trips' | transloco }}
      </a>
      @if (trip(); as t) {
        <header class="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 class="text-2xl font-bold">{{ t.origin }} → {{ t.destination }}</h1>
            <p class="text-muted">{{ when(t.departs_at) }}</p>
          </div>
          <cp-status-badge [variant]="tripTone(t.status)">{{
            'trips.status.' + t.status | transloco
          }}</cp-status-badge>
        </header>

        <cp-glass-card>
          <dl class="grid gap-3 text-sm sm:grid-cols-3">
            <div>
              <dt class="text-muted">{{ 'trips.driver' | transloco }}</dt>
              <dd>
                <a
                  class="font-semibold text-primary"
                  [routerLink]="['/admin/usuarios', t.driver_id]"
                  >{{ t.driver_name }}</a
                >
              </dd>
            </div>
            <div>
              <dt class="text-muted">{{ 'admin.trips.vehicle' | transloco }}</dt>
              <dd class="font-semibold">{{ t.vehicle }} · {{ t.plate }}</dd>
            </div>
            <div>
              <dt class="text-muted">{{ 'admin.trips.seatsLabel' | transloco }}</dt>
              <dd class="font-semibold">
                {{
                  'admin.trips.seats' | transloco: { booked: t.seats_booked, total: t.seats_total }
                }}
              </dd>
            </div>
            @if (t.cancel_reason) {
              <div class="sm:col-span-3">
                <dt class="text-muted">{{ 'trips.cancelReason' | transloco }}</dt>
                <dd>{{ t.cancel_reason }}</dd>
              </div>
            }
          </dl>
        </cp-glass-card>

        @if (t.emergencies.length) {
          <cp-glass-card class="flex flex-col gap-2">
            <h2 class="inline-flex items-center gap-2 font-semibold text-danger">
              <svg lucideSiren class="size-5" aria-hidden="true"></svg>
              {{ 'nav.emergencies' | transloco }}
            </h2>
            @for (e of t.emergencies; track e.id) {
              <p class="text-sm">
                {{ e.user_name }} · {{ when(e.created_at) }} ·
                {{
                  (e.handled_at ? 'admin.emergencies.handled' : 'admin.emergencies.open')
                    | transloco
                }}
              </p>
            }
            <a routerLink="/admin/emergencias" class="text-sm font-semibold text-primary">
              {{ 'admin.emergencies.goTo' | transloco }}
            </a>
          </cp-glass-card>
        }

        <cp-glass-card>
          <h2 class="mb-2 font-semibold">{{ 'admin.trips.bookings' | transloco }}</h2>
          <ul class="flex flex-col gap-2 text-sm">
            @for (b of t.bookings; track b.id) {
              <li class="flex flex-wrap items-center gap-2 rounded-xl bg-glass p-3">
                <a
                  class="min-w-0 flex-1 truncate font-semibold text-primary"
                  [routerLink]="['/admin/usuarios', b.passenger_id]"
                >
                  {{ b.passenger_name }}
                </a>
                <span class="text-muted">{{ 'trips.seats' | transloco: { count: b.seats } }}</span>
                <cp-status-badge [variant]="bookingTone(b.status)">{{
                  'admin.bookingStatus.' + b.status | transloco
                }}</cp-status-badge>
              </li>
            } @empty {
              <li class="text-muted">{{ 'admin.trips.noBookings' | transloco }}</li>
            }
          </ul>
        </cp-glass-card>

        <div class="flex flex-wrap gap-2">
          @if (t.status === 'scheduled' && !t.deleted) {
            <button cp-button variant="danger" type="button" (click)="cancel()">
              <svg lucideCalendarX class="size-4" aria-hidden="true"></svg>
              {{ 'admin.trips.cancel' | transloco }}
            </button>
          }
          @if (t.has_chat && messages() === null) {
            <button cp-button variant="secondary" type="button" (click)="openChat()">
              <svg lucideMessageCircle class="size-4" aria-hidden="true"></svg>
              {{ 'admin.trips.viewChat' | transloco }}
            </button>
          }
        </div>

        @if (messages(); as list) {
          <cp-glass-card class="flex flex-col gap-2">
            <h2 class="font-semibold">{{ 'admin.trips.chat' | transloco }}</h2>
            <p class="text-xs text-muted">{{ 'admin.trips.chatAudited' | transloco }}</p>
            <ul class="flex flex-col gap-2">
              @for (m of list; track m.id) {
                <li
                  class="flex items-start gap-2 rounded-xl bg-glass p-3 text-sm"
                  [class.opacity-60]="m.hidden"
                >
                  <div class="min-w-0 flex-1">
                    <p class="font-semibold">
                      {{ m.sender_name }}
                      <span class="font-normal text-muted">· {{ when(m.sent_at) }}</span>
                    </p>
                    <p class="whitespace-pre-line break-words">{{ m.body }}</p>
                  </div>
                  <button
                    cp-button
                    variant="ghost"
                    type="button"
                    [attr.aria-label]="
                      (m.hidden ? 'admin.moderation.show' : 'admin.moderation.hide') | transloco
                    "
                    (click)="toggleMessage(m)"
                  >
                    @if (m.hidden) {
                      <svg lucideEye class="size-4" aria-hidden="true"></svg>
                    } @else {
                      <svg lucideEyeOff class="size-4" aria-hidden="true"></svg>
                    }
                  </button>
                </li>
              } @empty {
                <li class="text-sm text-muted">{{ 'admin.trips.noMessages' | transloco }}</li>
              }
            </ul>
          </cp-glass-card>
        }
      } @else if (loadError(); as message) {
        <cp-glass-card><cp-error-state [message]="message" (retry)="load(id())" /></cp-glass-card>
      } @else {
        <cp-glass-card><cp-skeleton [lines]="6" /></cp-glass-card>
      }
    </div>
  `,
})
export class AdminTripDetailPage {
  readonly id = input.required<string>();

  private readonly api = inject(AdminApi);
  private readonly dialogs = inject(DialogService);
  private readonly transloco = inject(TranslocoService);
  private readonly language = inject(LanguageService);
  private readonly toast = inject(ToastService);

  protected readonly trip = signal<AdminTripDetail | null>(null);
  protected readonly loadError = signal<string | null>(null);
  protected readonly messages = signal<AdminMessage[] | null>(null);

  constructor() {
    effect(() => {
      const id = this.id();
      untracked(() => void this.load(id));
    });
  }

  protected async load(id: string): Promise<void> {
    this.messages.set(null);
    this.loadError.set(null);
    try {
      this.trip.set(await this.api.trip(id));
    } catch (error) {
      if (this.trip()) this.toast.show(apiErrorMessage(this.transloco, error), 'danger');
      else this.loadError.set(apiErrorMessage(this.transloco, error));
    }
  }

  protected async cancel(): Promise<void> {
    const ref = this.dialogs.open<ReasonResult, ReasonDialogData, ReasonDialog>(ReasonDialog, {
      title: this.transloco.translate('admin.trips.cancel'),
      message: this.transloco.translate('admin.trips.cancelMessage'),
      confirmLabel: this.transloco.translate('admin.trips.cancel'),
      required: true,
      danger: true,
    });
    const answer = await firstValueFrom(ref.closed);
    if (!answer?.reason) return;
    try {
      this.trip.set(await this.api.cancelTrip(this.id(), answer.reason));
      this.toast.show(this.transloco.translate('admin.trips.cancelled'), 'success');
    } catch (error) {
      this.toast.show(apiErrorMessage(this.transloco, error), 'danger');
    }
  }

  protected async openChat(): Promise<void> {
    const ok = await this.dialogs.confirm({
      title: this.transloco.translate('admin.trips.viewChat'),
      message: this.transloco.translate('admin.trips.chatWarning'),
      confirmLabel: this.transloco.translate('admin.trips.viewChat'),
      cancelLabel: this.transloco.translate('common.cancel'),
    });
    if (!ok) return;
    try {
      this.messages.set(await this.api.tripMessages(this.id()));
    } catch (error) {
      this.toast.show(apiErrorMessage(this.transloco, error), 'danger');
    }
  }

  protected async toggleMessage(message: AdminMessage): Promise<void> {
    try {
      const updated = await this.api.hideMessage(message.id, !message.hidden);
      this.messages.update((list) => list?.map((m) => (m.id === updated.id ? updated : m)) ?? null);
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

  protected tripTone(status: TripStatus): BadgeTone {
    return TRIP_STATUS_TONE[status];
  }

  protected bookingTone(status: BookingStatus): BadgeTone {
    return BOOKING_STATUS_TONE[status];
  }

  protected when(iso: string): string {
    return formatDeparture(iso, this.language.current());
  }
}
