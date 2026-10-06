import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  computed,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { TranslocoPipe, TranslocoService } from '@jsverse/transloco';
import { LucideCircleCheck, LucideMapPin, LucideSiren } from '@lucide/angular';
import { firstValueFrom } from 'rxjs';
import { apiErrorMessage } from '../../core/http/api-error-message';
import { LanguageService } from '../../core/i18n/language.service';
import { LiveEvent, RealtimeService } from '../../core/ws/realtime.service';
import { DialogService } from '../../shared/ui/dialog.service';
import { EmptyState } from '../../shared/ui/empty-state';
import { GlassButton } from '../../shared/ui/glass-button';
import { GlassCard } from '../../shared/ui/glass-card';
import { Skeleton } from '../../shared/ui/skeleton';
import { StatusBadge } from '../../shared/ui/status-badge';
import { ToastService } from '../../shared/ui/toast.service';
import { formatDeparture } from '../trips/trip-status';
import { ResolutionDialog } from './admin-dialogs';
import { AdminApi, Emergency } from './admin.api';

interface EmergencyEvent extends LiveEvent {
  emergency: Emergency;
}

/**
 * Emergencias: las abiertas arriba, en tiempo real. Atender exige escribir que se hizo,
 * y eso queda en la auditoria.
 */
@Component({
  selector: 'cp-admin-emergencies',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    RouterLink,
    TranslocoPipe,
    EmptyState,
    GlassButton,
    GlassCard,
    Skeleton,
    StatusBadge,
    LucideCircleCheck,
    LucideMapPin,
    LucideSiren,
  ],
  template: `
    <div class="mx-auto flex max-w-4xl flex-col gap-5 py-2">
      <header class="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 class="text-2xl font-bold sm:text-3xl">{{ 'nav.emergencies' | transloco }}</h1>
          <p class="text-muted">{{ 'admin.emergencies.subtitle' | transloco }}</p>
        </div>
        <label class="inline-flex min-h-11 items-center gap-2 text-sm">
          <input
            type="checkbox"
            class="size-5 accent-[var(--color-accent)]"
            [checked]="includeHandled()"
            (change)="toggleHandled()"
          />
          {{ 'admin.emergencies.includeHandled' | transloco }}
        </label>
      </header>
      @if (items() === null) {
        <cp-glass-card><cp-skeleton [lines]="4" /></cp-glass-card>
      } @else {
        <ul class="flex flex-col gap-3" aria-live="polite">
          @for (e of sorted(); track e.id) {
            <li>
              <cp-glass-card
                class="flex flex-col gap-2"
                [class.ring-2]="!e.handled_at"
                [class.ring-danger]="!e.handled_at"
              >
                <div class="flex flex-wrap items-center justify-between gap-2">
                  <p class="inline-flex items-center gap-2 font-semibold">
                    <svg
                      lucideSiren
                      class="size-5"
                      [class.text-danger]="!e.handled_at"
                      aria-hidden="true"
                    ></svg>
                    <a class="text-primary" [routerLink]="['/admin/usuarios', e.user_id]">{{
                      e.user_name
                    }}</a>
                  </p>
                  <cp-status-badge [variant]="e.handled_at ? 'success' : 'danger'">{{
                    (e.handled_at ? 'admin.emergencies.handled' : 'admin.emergencies.open')
                      | transloco
                  }}</cp-status-badge>
                </div>
                <p class="text-sm text-muted">
                  {{ when(e.created_at) }} ·
                  <a class="text-primary" [routerLink]="['/admin/viajes', e.trip_id]">{{
                    e.route
                  }}</a>
                  ·
                  {{ 'trips.status.' + e.trip_status | transloco }}
                </p>
                @if (e.note) {
                  <p>{{ e.note }}</p>
                }
                @if (e.resolution) {
                  <p class="text-sm">
                    <span class="font-semibold"
                      >{{ 'admin.emergencies.resolution' | transloco }}:</span
                    >
                    {{ e.resolution }}
                  </p>
                }
                <div class="flex flex-wrap gap-2">
                  @if (e.lat !== null && e.lon !== null) {
                    <a
                      cp-button
                      variant="secondary"
                      target="_blank"
                      rel="noopener"
                      [href]="mapUrl(e)"
                    >
                      <svg lucideMapPin class="size-4" aria-hidden="true"></svg>
                      {{ 'admin.emergencies.map' | transloco }}
                    </a>
                  }
                  @if (!e.handled_at) {
                    <button cp-button type="button" (click)="handle(e)">
                      <svg lucideCircleCheck class="size-4" aria-hidden="true"></svg>
                      {{ 'admin.emergencies.handle' | transloco }}
                    </button>
                  }
                </div>
              </cp-glass-card>
            </li>
          } @empty {
            <cp-empty-state [title]="'admin.emergencies.none' | transloco" />
          }
        </ul>
      }
    </div>
  `,
})
export default class AdminEmergencies {
  private readonly api = inject(AdminApi);
  private readonly dialogs = inject(DialogService);
  private readonly transloco = inject(TranslocoService);
  private readonly language = inject(LanguageService);
  private readonly toast = inject(ToastService);

  protected readonly includeHandled = signal(false);
  protected readonly items = signal<Emergency[] | null>(null);
  protected readonly sorted = computed(() =>
    [...(this.items() ?? [])].sort(
      (a, b) =>
        Number(!!a.handled_at) - Number(!!b.handled_at) || b.created_at.localeCompare(a.created_at),
    ),
  );

  constructor() {
    void this.load();
    inject(RealtimeService)
      .on<EmergencyEvent>('emergency', 'emergency.handled')
      .pipe(takeUntilDestroyed(inject(DestroyRef)))
      .subscribe(({ emergency }) => this.upsert(emergency));
  }

  private async load(): Promise<void> {
    try {
      this.items.set(await this.api.emergencies(this.includeHandled()));
    } catch (error) {
      this.items.set([]);
      this.toast.show(apiErrorMessage(this.transloco, error), 'danger');
    }
  }

  private upsert(emergency: Emergency): void {
    this.items.update((list) => {
      const rest = (list ?? []).filter((e) => e.id !== emergency.id);
      if (emergency.handled_at && !this.includeHandled()) return rest;
      return [emergency, ...rest];
    });
  }

  protected toggleHandled(): void {
    this.includeHandled.update((value) => !value);
    void this.load();
  }

  protected async handle(emergency: Emergency): Promise<void> {
    const resolution = await firstValueFrom(
      this.dialogs.open<string, undefined, ResolutionDialog>(ResolutionDialog).closed,
    );
    if (!resolution) return;
    try {
      this.upsert(await this.api.handleEmergency(emergency.id, resolution));
      this.toast.show(this.transloco.translate('admin.emergencies.done'), 'success');
    } catch (error) {
      this.toast.show(apiErrorMessage(this.transloco, error), 'danger');
      void this.load();
    }
  }

  protected mapUrl(e: Emergency): string {
    return `https://www.openstreetmap.org/?mlat=${e.lat}&mlon=${e.lon}#map=17/${e.lat}/${e.lon}`;
  }

  protected when(iso: string): string {
    return formatDeparture(iso, this.language.current());
  }
}
