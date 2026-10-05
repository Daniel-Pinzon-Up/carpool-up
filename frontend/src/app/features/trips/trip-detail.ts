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
import {
  LucideCopy,
  LucideFootprints,
  LucidePencil,
  LucideRepeat,
  LucideRoute,
  LucideTriangleAlert,
  LucideUsers,
  LucideX,
} from '@lucide/angular';
import { firstValueFrom } from 'rxjs';
import { AuthService } from '../../core/auth/auth.service';
import { apiErrorMessage } from '../../core/http/api-error-message';
import { LanguageService } from '../../core/i18n/language.service';
import { MapMarker, MapView } from '../../shared/map/map-view';
import { formatCop } from '../../shared/map/routing.api';
import { DialogService } from '../../shared/ui/dialog.service';
import { GlassButton } from '../../shared/ui/glass-button';
import { GlassCard } from '../../shared/ui/glass-card';
import { Skeleton } from '../../shared/ui/skeleton';
import { StatusBadge } from '../../shared/ui/status-badge';
import { ToastService } from '../../shared/ui/toast.service';
import {
  CancelDialogData,
  CancelTripDialog,
  DuplicateDialog,
  DuplicateResult,
} from './trip-dialogs';
import { TRIP_STATUS_TONE, formatDeparture, formatTime } from './trip-status';
import { SearchResult } from '../search/search.api';
import { Trip, TripsApi, pamplonaTime } from './trips.api';

/** Detalle de un viaje: mapa, paradas con hora, reglas, vehiculo y acciones del conductor. */
@Component({
  selector: 'cp-trip-detail',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    RouterLink,
    TranslocoPipe,
    GlassButton,
    GlassCard,
    MapView,
    Skeleton,
    StatusBadge,
    LucideCopy,
    LucideFootprints,
    LucidePencil,
    LucideRepeat,
    LucideRoute,
    LucideTriangleAlert,
    LucideUsers,
    LucideX,
  ],
  template: `
    <div class="mx-auto flex max-w-5xl flex-col gap-5 py-2">
      @if (error()) {
        <p role="alert" class="text-danger">{{ error() }}</p>
      } @else if (trip(); as t) {
        <header class="flex flex-wrap items-start justify-between gap-3">
          <div class="flex flex-col gap-1">
            <cp-status-badge class="self-start" [variant]="tone()">{{
              'trips.status.' + t.status | transloco
            }}</cp-status-badge>
            <h1 class="text-2xl font-bold sm:text-3xl">{{ t.origin }} – {{ t.destination }}</h1>
            <p class="text-muted">{{ when() }}</p>
          </div>
          @if (isOwner()) {
            <div class="flex flex-wrap gap-2">
              @if (t.editable) {
                <a cp-button variant="secondary" [routerLink]="['/viajes', t.id, 'editar']">
                  <svg lucidePencil class="size-4" aria-hidden="true"></svg>
                  {{ 'trips.actions.edit' | transloco }}
                </a>
                <button cp-button variant="danger" type="button" (click)="cancel()">
                  <svg lucideX class="size-4" aria-hidden="true"></svg>
                  {{ 'trips.actions.cancel' | transloco }}
                </button>
              }
              <button cp-button variant="ghost" type="button" (click)="duplicate()">
                <svg lucideCopy class="size-4" aria-hidden="true"></svg>
                {{ 'trips.actions.duplicate' | transloco }}
              </button>
            </div>
          }
        </header>

        @if (t.status === 'cancelled_pico_placa') {
          <p class="glass-1 !rounded-2xl flex gap-2 p-4" role="status">
            <svg lucideTriangleAlert class="size-5 shrink-0 text-warning" aria-hidden="true"></svg>
            {{ 'trips.picoPlacaCancelled' | transloco }}
          </p>
        }
        @if (t.cancel_reason) {
          <p class="glass-1 !rounded-2xl p-4">
            <span class="font-semibold">{{ 'trips.cancelReason' | transloco }}:</span>
            {{ t.cancel_reason }}
          </p>
        }
        @if (t.series_id && isOwner()) {
          <a
            [routerLink]="['/series', t.series_id]"
            class="inline-flex min-h-11 items-center gap-2 self-start font-semibold text-primary"
          >
            <svg lucideRepeat class="size-4" aria-hidden="true"></svg>
            {{ 'trips.viewSeries' | transloco }}
          </a>
        }

        @if (match(); as m) {
          <section
            aria-labelledby="my-pickup-title"
            class="glass-2 !rounded-2xl grid gap-3 p-4 sm:grid-cols-2"
          >
            <h2 id="my-pickup-title" class="sr-only">{{ 'trips.yourTrip' | transloco }}</h2>
            <div>
              <p class="text-sm text-muted">{{ 'search.card.pickup' | transloco }}</p>
              <p class="font-semibold">
                {{ m.pickup.name || ('search.card.onRoute' | transloco) }} ·
                {{ time(m.pickup.eta) }}
              </p>
              <p class="flex items-center gap-1 text-xs text-muted">
                <svg lucideFootprints class="size-3.5" aria-hidden="true"></svg>
                {{ 'search.card.walk' | transloco: { meters: m.pickup.walk_m } }}
              </p>
            </div>
            <div>
              <p class="text-sm text-muted">{{ 'search.card.dropoff' | transloco }}</p>
              <p class="font-semibold">
                {{ m.dropoff.name || ('search.card.onRoute' | transloco) }} ·
                {{ time(m.dropoff.eta) }}
              </p>
              <p class="text-xs text-muted">
                {{ 'search.card.seats' | transloco: { count: m.seats_available } }}
              </p>
            </div>
          </section>
        }

        <div class="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,22rem)]">
          <cp-map-view
            class="h-72 w-full sm:h-[24rem]"
            [route]="t.geometry"
            [markers]="markers()"
            [label]="'trips.mapLabel' | transloco"
          />
          <cp-glass-card [level]="2">
            <h2 class="mb-3 flex items-center gap-2 font-bold">
              <svg lucideRoute class="size-5" aria-hidden="true"></svg>
              {{ 'routeSummary.stops' | transloco }}
            </h2>
            <ol class="flex flex-col gap-2">
              @for (stop of t.stops; track stop.position) {
                <li class="flex items-center gap-3 text-sm">
                  <span
                    class="size-3 shrink-0 rounded-full ring-2 ring-white"
                    [style.background]="stopColor(stop.kind)"
                    aria-hidden="true"
                  ></span>
                  <span class="min-w-0 flex-1 truncate">
                    <span class="sr-only">{{ 'routeSummary.' + stop.kind | transloco }}:</span>
                    {{ stop.name }}
                  </span>
                  @if (stop.eta) {
                    <span class="shrink-0 font-semibold">{{ time(stop.eta) }}</span>
                  }
                </li>
              }
            </ol>
            <dl class="mt-5 grid grid-cols-2 gap-3 text-sm">
              <div>
                <dt class="text-muted">{{ 'routeSummary.distance' | transloco }}</dt>
                <dd class="font-semibold">{{ km() }} km</dd>
              </div>
              <div>
                <dt class="text-muted">{{ 'routeSummary.duration' | transloco }}</dt>
                <dd class="font-semibold">
                  {{ 'routeSummary.minutes' | transloco: { count: minutes() } }}
                </dd>
              </div>
              <div>
                <dt class="text-muted">{{ 'publish.price.label' | transloco }}</dt>
                <dd class="font-semibold">{{ money() }}</dd>
              </div>
              <div>
                <dt class="text-muted">{{ 'planner.seats' | transloco }}</dt>
                <dd class="flex items-center gap-1 font-semibold">
                  <svg lucideUsers class="size-4" aria-hidden="true"></svg>{{ t.seats_total }}
                </dd>
              </div>
              <div class="col-span-2">
                <dt class="text-muted">{{ 'planner.vehicle' | transloco }}</dt>
                <dd class="font-semibold">
                  {{ t.vehicle.brand }} {{ t.vehicle.model }}, {{ t.vehicle.color }}
                  @if (t.vehicle.plate) {
                    · {{ t.vehicle.plate }}
                  }
                </dd>
              </div>
              <div class="col-span-2">
                <dt class="text-muted">{{ 'trips.driver' | transloco }}</dt>
                <dd class="font-semibold">{{ t.driver.full_name }}</dd>
              </div>
            </dl>
            <h2 class="mt-5 mb-2 font-bold">{{ 'publish.steps.rules' | transloco }}</h2>
            <ul class="flex flex-wrap gap-1.5">
              @for (rule of t.rules; track rule.kind) {
                <li class="rounded-full bg-glass px-2.5 py-1 text-xs font-medium">
                  @if (rule.kind === 'custom') {
                    {{ rule.value }}
                  } @else if (rule.kind === 'women_only') {
                    {{ 'publish.rules.women_only' | transloco }}
                  } @else {
                    {{ 'publish.rules.' + rule.kind | transloco }}:
                    {{ 'publish.rules.choice.' + rule.value | transloco }}
                  }
                </li>
              } @empty {
                <li class="text-sm text-muted">{{ 'publish.summary.noRules' | transloco }}</li>
              }
            </ul>
          </cp-glass-card>
        </div>
      } @else {
        <cp-glass-card><cp-skeleton [lines]="6" /></cp-glass-card>
      }
    </div>
  `,
})
export default class TripDetail {
  readonly id = input.required<string>();

  private readonly api = inject(TripsApi);
  private readonly auth = inject(AuthService);
  private readonly dialogs = inject(DialogService);
  private readonly toast = inject(ToastService);
  private readonly router = inject(Router);
  private readonly transloco = inject(TranslocoService);
  private readonly language = inject(LanguageService);

  protected readonly trip = signal<Trip | null>(null);
  /** Recogida y bajada calculadas por la busqueda (llegan en el estado de la navegacion). */
  protected readonly match = signal<SearchResult | null>(null);
  protected readonly error = signal<string | null>(null);
  protected readonly isOwner = computed(() => this.trip()?.driver.id === this.auth.user()?.id);
  protected readonly tone = computed(() => TRIP_STATUS_TONE[this.trip()?.status ?? 'scheduled']);
  protected readonly when = computed(() => {
    const trip = this.trip();
    return trip ? formatDeparture(trip.departs_at, this.language.current()) : '';
  });
  protected readonly km = computed(() =>
    ((this.trip()?.distance_m ?? 0) / 1000).toLocaleString(this.language.current(), {
      maximumFractionDigits: 1,
    }),
  );
  protected readonly minutes = computed(() =>
    Math.max(1, Math.round((this.trip()?.est_duration_s ?? 0) / 60)),
  );
  protected readonly money = computed(() =>
    formatCop(this.trip()?.price_per_seat ?? 0, this.language.current()),
  );
  protected readonly markers = computed<MapMarker[]>(() => {
    const stops: MapMarker[] = (this.trip()?.stops ?? []).map((stop) => ({
      lat: stop.lat,
      lon: stop.lon,
      kind: stop.kind,
      label: stop.name,
    }));
    const match = this.match();
    if (!match) return stops;
    const label = (key: string) => this.transloco.translate(key);
    return [
      ...stops,
      {
        lat: match.pickup.lat,
        lon: match.pickup.lon,
        kind: 'pin',
        label: label('search.card.pickup'),
      },
      {
        lat: match.dropoff.lat,
        lon: match.dropoff.lon,
        kind: 'pin',
        label: label('search.card.dropoff'),
      },
    ];
  });

  constructor() {
    effect(() => {
      const id = this.id();
      untracked(() => void this.load(id));
    });
  }

  private async load(id: string): Promise<void> {
    this.error.set(null);
    const state = (globalThis.history?.state ?? {}) as { match?: SearchResult };
    this.match.set(state.match?.trip_id === id ? state.match : null);
    try {
      this.trip.set(await this.api.trip(id));
    } catch (error) {
      this.error.set(apiErrorMessage(this.transloco, error));
    }
  }

  protected time(iso: string): string {
    return formatTime(iso, this.language.current());
  }

  protected stopColor(kind: string): string {
    return kind === 'origin'
      ? 'var(--accent)'
      : kind === 'destination'
        ? 'var(--danger)'
        : 'var(--primary)';
  }

  protected async cancel(): Promise<void> {
    const trip = this.trip();
    if (!trip) return;
    const ref = this.dialogs.open<string, CancelDialogData, CancelTripDialog>(CancelTripDialog, {
      title: this.transloco.translate('trips.cancel.title'),
      message: this.transloco.translate('trips.cancel.message'),
    });
    const reason = await firstValueFrom(ref.closed);
    if (!reason) return;
    try {
      this.trip.set(await this.api.cancelTrip(trip.id, reason));
      this.toast.show(this.transloco.translate('trips.cancel.done'), 'success');
    } catch (error) {
      this.toast.show(apiErrorMessage(this.transloco, error), 'danger');
    }
  }

  protected async duplicate(): Promise<void> {
    const trip = this.trip();
    if (!trip) return;
    const ref = this.dialogs.open<DuplicateResult, unknown, DuplicateDialog>(DuplicateDialog, {
      kind: 'trip',
      time: pamplonaTime(trip.departs_at),
    });
    const result = await firstValueFrom(ref.closed);
    if (!result || result.kind !== 'trip') return;
    try {
      const copy = await this.api.duplicateTrip(trip.id, result.departsAt);
      this.toast.show(this.transloco.translate('trips.duplicate.done'), 'success');
      await this.router.navigate(['/viajes', copy.id]);
    } catch (error) {
      this.toast.show(apiErrorMessage(this.transloco, error), 'danger');
    }
  }
}
