import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  computed,
  effect,
  inject,
  input,
  signal,
  untracked,
} from '@angular/core';
import { TranslocoPipe, TranslocoService } from '@jsverse/transloco';
import { LucideCarFront, LucideClock, LucideLink2Off, LucideMapPin } from '@icons';
import { LOCALE } from '../../core/i18n/locale';
import { MapMarker, MapView } from '../../shared/map/map-view';
import { Brand } from '../../shared/ui/brand';
import { EmptyState } from '../../shared/ui/empty-state';
import { GlassCard } from '../../shared/ui/glass-card';
import { Skeleton } from '../../shared/ui/skeleton';
import { StatusBadge } from '../../shared/ui/status-badge';
import { PublicTrip, LifecycleApi } from '../trips/lifecycle.api';
import { TRIP_STATUS_TONE, formatDeparture, formatTime } from '../trips/trip-status';

/** Cada cuanto se actualiza la ubicacion: quien mira no tiene sesion ni WebSocket. */
const REFRESH_MS = 15_000;

/**
 * Vista publica del viaje compartido: ruta, vehiculo con placa y ubicacion del conductor.
 * Sin nombres ni datos de contacto; deja de funcionar al vencer el enlace.
 */
@Component({
  selector: 'cp-shared-trip',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    TranslocoPipe,
    Brand,
    EmptyState,
    GlassCard,
    MapView,
    Skeleton,
    StatusBadge,
    LucideCarFront,
    LucideClock,
    LucideMapPin,
  ],
  template: `
    <div class="mx-auto flex min-h-dvh max-w-4xl flex-col gap-4 px-4 py-4">
      <header class="flex items-center gap-3">
        <cp-brand [size]="40" />
      </header>
      <main id="main" class="flex flex-col gap-4">
        @if (trip(); as t) {
          <div class="flex flex-wrap items-center gap-2">
            <h1 class="text-2xl font-bold">{{ 'shared.title' | transloco }}</h1>
            <cp-status-badge [variant]="tone()">{{
              'trips.status.' + t.status | transloco
            }}</cp-status-badge>
          </div>
          <cp-map-view
            class="h-80 w-full sm:h-[26rem]"
            [route]="t.geometry"
            [markers]="markers()"
            [label]="'shared.mapLabel' | transloco"
          />
          <cp-glass-card class="grid gap-4 sm:grid-cols-3">
            <div class="flex gap-2">
              <svg
                lucideCarFront
                class="mt-0.5 size-5 shrink-0 text-primary"
                aria-hidden="true"
              ></svg>
              <div>
                <p class="text-sm text-muted">{{ 'shared.vehicle' | transloco }}</p>
                <p class="font-semibold">
                  {{ t.vehicle.brand }} {{ t.vehicle.model }}, {{ t.vehicle.color }}
                </p>
                <p class="font-mono text-lg font-bold tracking-wider">{{ t.vehicle.plate }}</p>
              </div>
            </div>
            <div class="flex gap-2">
              <svg lucideClock class="mt-0.5 size-5 shrink-0 text-primary" aria-hidden="true"></svg>
              <div>
                <p class="text-sm text-muted">{{ 'shared.arrival' | transloco }}</p>
                <p class="font-semibold">{{ when(t.arrives_at) }}</p>
                <p class="text-sm text-muted">
                  {{ t.stops[0].name }} → {{ t.stops[t.stops.length - 1].name }}
                </p>
              </div>
            </div>
            <div class="flex gap-2">
              <svg
                lucideMapPin
                class="mt-0.5 size-5 shrink-0 text-primary"
                aria-hidden="true"
              ></svg>
              <div>
                <p class="text-sm text-muted">{{ 'shared.location' | transloco }}</p>
                <p class="font-semibold" aria-live="polite">
                  @if (t.location) {
                    {{ 'shared.seenAt' | transloco: { time: time(t.location.at) } }}
                  } @else {
                    {{ 'shared.noLocation.' + t.status | transloco }}
                  }
                </p>
              </div>
            </div>
          </cp-glass-card>
          <p class="text-center text-xs text-muted">
            {{ 'shared.expires' | transloco: { time: when(t.expires_at) } }}
          </p>
        } @else if (gone()) {
          <cp-empty-state
            [icon]="goneIcon"
            [title]="'shared.gone' | transloco"
            [description]="'shared.goneHint' | transloco"
          />
        } @else {
          <cp-glass-card><cp-skeleton [lines]="5" /></cp-glass-card>
        }
      </main>
    </div>
  `,
})
export default class SharedTrip {
  readonly token = input.required<string>();

  private readonly api = inject(LifecycleApi);
  private readonly transloco = inject(TranslocoService);

  protected readonly goneIcon = LucideLink2Off;
  protected readonly trip = signal<PublicTrip | null>(null);
  protected readonly gone = signal(false);
  protected readonly tone = computed(() => TRIP_STATUS_TONE[this.trip()?.status ?? 'scheduled']);
  protected readonly markers = computed<MapMarker[]>(() => {
    const trip = this.trip();
    if (!trip) return [];
    const markers: MapMarker[] = trip.stops.map((s) => ({
      lat: s.lat,
      lon: s.lon,
      kind: s.kind,
      label: s.name,
    }));
    if (trip.location) {
      markers.push({
        lat: trip.location.lat,
        lon: trip.location.lon,
        kind: 'vehicle',
        label: this.transloco.translate('shared.vehicle'),
      });
    }
    return markers;
  });

  constructor() {
    effect(() => {
      const token = this.token();
      untracked(() => void this.load(token));
    });
    const timer = setInterval(() => {
      if (!this.gone() && document.visibilityState === 'visible') void this.load(this.token());
    }, REFRESH_MS);
    inject(DestroyRef).onDestroy(() => clearInterval(timer));
  }

  private async load(token: string): Promise<void> {
    try {
      this.trip.set(await this.api.publicTrip(token));
    } catch {
      this.trip.set(null);
      this.gone.set(true);
    }
  }

  protected when(iso: string): string {
    return formatDeparture(iso, LOCALE);
  }

  protected time(iso: string): string {
    return formatTime(iso, LOCALE);
  }
}
