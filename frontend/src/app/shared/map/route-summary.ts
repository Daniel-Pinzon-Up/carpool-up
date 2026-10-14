import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { TranslocoPipe } from '@jsverse/transloco';
import { LucideClock, LucideHandCoins, LucideInfo, LucideRoute } from '@icons';
import { LOCALE } from '../../core/i18n/locale';
import { RoutePreview, formatCop } from './routing.api';

/** Distancia, duracion, ETA por parada y precio sugerido de una ruta, en texto. */
@Component({
  selector: 'cp-route-summary',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [TranslocoPipe, LucideRoute, LucideClock, LucideHandCoins, LucideInfo],
  host: { class: 'block' },
  template: `
    @if (preview(); as route) {
      <dl class="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <div class="glass-1 !rounded-2xl p-3">
          <dt class="flex items-center gap-1.5 text-sm text-muted">
            <svg lucideRoute class="size-4" aria-hidden="true"></svg
            >{{ 'routeSummary.distance' | transloco }}
          </dt>
          <dd class="text-xl font-bold">{{ km() }} km</dd>
        </div>
        <div class="glass-1 !rounded-2xl p-3">
          <dt class="flex items-center gap-1.5 text-sm text-muted">
            <svg lucideClock class="size-4" aria-hidden="true"></svg
            >{{ 'routeSummary.duration' | transloco }}
          </dt>
          <dd class="text-xl font-bold">
            {{ 'routeSummary.minutes' | transloco: { count: minutes() } }}
          </dd>
        </div>
        <div class="glass-1 !rounded-2xl col-span-2 p-3 sm:col-span-1">
          <dt class="flex items-center gap-1.5 text-sm text-muted">
            <svg lucideHandCoins class="size-4" aria-hidden="true"></svg
            >{{ 'routeSummary.price' | transloco }}
          </dt>
          <dd class="text-xl font-bold">
            @if (route.suggested_price !== null) {
              {{ money(route.suggested_price) }}
            } @else {
              <span class="text-base font-medium text-muted">
                {{
                  (route.pricing_configured
                    ? 'routeSummary.priceNeedsSeats'
                    : 'routeSummary.priceNotConfigured'
                  ) | transloco
                }}
              </span>
            }
          </dd>
          @if (route.max_price_per_seat !== null) {
            <dd class="text-xs text-muted">
              {{ 'routeSummary.cap' | transloco: { max: money(route.max_price_per_seat) } }}
            </dd>
          }
        </div>
      </dl>

      <ol class="mt-4 flex flex-col gap-2" [attr.aria-label]="'routeSummary.stops' | transloco">
        @for (point of route.points; track $index; let first = $first; let last = $last) {
          <li class="flex items-center gap-3 text-sm">
            <span
              class="size-3 shrink-0 rounded-full ring-2 ring-white"
              [style.background]="
                first ? 'var(--accent)' : last ? 'var(--danger)' : 'var(--primary)'
              "
              aria-hidden="true"
            ></span>
            <span class="min-w-0 flex-1 truncate">
              <span class="sr-only"
                >{{
                  (first
                    ? 'routeSummary.origin'
                    : last
                      ? 'routeSummary.destination'
                      : 'routeSummary.stop'
                  ) | transloco
                }}:</span
              >
              {{ point.name || ('routeSummary.pin' | transloco) }}
            </span>
            <span class="shrink-0 font-semibold">{{ when(point.eta, point.eta_offset_s) }}</span>
          </li>
        }
      </ol>

      <p class="mt-4 flex gap-2 text-xs text-muted">
        <svg lucideInfo class="size-4 shrink-0" aria-hidden="true"></svg>
        {{ 'routeSummary.etaNote' | transloco }}
      </p>
      @if (route.suggested_price !== null) {
        <p class="mt-1 text-xs text-muted">{{ 'routeSummary.contribution' | transloco }}</p>
      }
    }
  `,
})
export class RouteSummary {
  readonly preview = input<RoutePreview | null>(null);

  protected readonly km = computed(() =>
    ((this.preview()?.distance_m ?? 0) / 1000).toLocaleString(LOCALE, {
      maximumFractionDigits: 1,
    }),
  );
  protected readonly minutes = computed(() =>
    Math.max(1, Math.round((this.preview()?.duration_s ?? 0) / 60)),
  );

  protected money(value: number): string {
    return formatCop(value, LOCALE);
  }

  protected when(eta: string | null, offsetSeconds: number): string {
    if (eta) {
      return new Date(eta).toLocaleTimeString(LOCALE, {
        hour: 'numeric',
        minute: '2-digit',
        timeZone: 'America/Bogota',
      });
    }
    return `+${Math.round(offsetSeconds / 60)} min`;
  }
}
