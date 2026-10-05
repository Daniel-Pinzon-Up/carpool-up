import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { TranslocoPipe, TranslocoService } from '@jsverse/transloco';
import {
  LucideBackpack,
  LucidePencil,
  LucidePlus,
  LucideTrash2,
  LucideUsers,
} from '@lucide/angular';
import { AuthService } from '../../core/auth/auth.service';
import { apiErrorMessage } from '../../core/http/api-error-message';
import { DialogService } from '../../shared/ui/dialog.service';
import { EmptyState } from '../../shared/ui/empty-state';
import { GlassButton } from '../../shared/ui/glass-button';
import { GlassCard } from '../../shared/ui/glass-card';
import { Skeleton } from '../../shared/ui/skeleton';
import { StatusBadge } from '../../shared/ui/status-badge';
import { ToastService } from '../../shared/ui/toast.service';
import { VehiclePhoto } from './vehicle-photo';
import { Vehicle, VehiclesApi } from './vehicles.api';

@Component({
  selector: 'cp-vehicles-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    RouterLink,
    TranslocoPipe,
    EmptyState,
    GlassButton,
    GlassCard,
    Skeleton,
    StatusBadge,
    VehiclePhoto,
    LucidePlus,
    LucidePencil,
    LucideTrash2,
    LucideUsers,
    LucideBackpack,
  ],
  template: `
    <div class="mx-auto flex max-w-5xl flex-col gap-6 py-2">
      <header class="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 class="text-2xl font-bold sm:text-3xl">{{ 'vehicles.title' | transloco }}</h1>
          <p class="text-muted">{{ 'vehicles.subtitle' | transloco }}</p>
        </div>
        <a cp-button routerLink="/vehiculos/nuevo">
          <svg lucidePlus class="size-4" aria-hidden="true"></svg>
          {{ 'vehicles.add' | transloco }}
        </a>
      </header>

      @if (loading()) {
        <div class="grid gap-5 sm:grid-cols-2" aria-busy="true">
          @for (row of [1, 2]; track row) {
            <cp-glass-card><cp-skeleton [lines]="4" /></cp-glass-card>
          }
        </div>
      } @else if (vehicles().length === 0) {
        <cp-glass-card>
          <cp-empty-state
            [title]="'vehicles.empty.title' | transloco"
            [description]="'vehicles.empty.body' | transloco"
          >
            <a cp-button routerLink="/vehiculos/nuevo">{{ 'vehicles.add' | transloco }}</a>
          </cp-empty-state>
        </cp-glass-card>
      } @else {
        <ul class="grid gap-5 sm:grid-cols-2">
          @for (vehicle of vehicles(); track vehicle.id) {
            <li>
              <cp-glass-card class="flex h-full flex-col gap-4">
                <cp-vehicle-photo
                  class="aspect-video w-full"
                  [vehicleId]="vehicle.id"
                  [hasPhoto]="vehicle.has_photo"
                  [type]="vehicle.type"
                  [alt]="vehicle.brand + ' ' + vehicle.model"
                />
                <div class="flex items-start justify-between gap-3">
                  <div class="min-w-0">
                    <h2 class="truncate text-lg font-bold">
                      {{ vehicle.brand }} {{ vehicle.model }}
                    </h2>
                    <p class="text-muted">
                      {{ 'vehicles.types.' + vehicle.type | transloco }} · {{ vehicle.color }} ·
                      {{ vehicle.year }}
                    </p>
                  </div>
                  <cp-status-badge [variant]="vehicle.is_active ? 'success' : 'neutral'">
                    {{ (vehicle.is_active ? 'vehicles.active' : 'vehicles.inactive') | transloco }}
                  </cp-status-badge>
                </div>
                <div class="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
                  <span
                    class="rounded-lg border-2 border-text px-2 py-0.5 font-mono font-bold tracking-widest"
                  >
                    {{ vehicle.plate }}
                  </span>
                  <span class="flex items-center gap-1.5 text-muted">
                    <svg lucideUsers class="size-4" aria-hidden="true"></svg>
                    {{ 'vehicles.seats' | transloco: { count: vehicle.capacity } }}
                  </span>
                  @if (vehicle.luggage_space) {
                    <span class="flex items-center gap-1.5 text-muted">
                      <svg lucideBackpack class="size-4" aria-hidden="true"></svg>
                      {{ 'vehicles.luggage' | transloco }}
                    </span>
                  }
                </div>
                <div class="mt-auto flex flex-wrap gap-2">
                  <a cp-button variant="secondary" [routerLink]="['/vehiculos', vehicle.id]">
                    <svg lucidePencil class="size-4" aria-hidden="true"></svg>
                    {{ 'vehicles.edit' | transloco }}
                  </a>
                  <button cp-button variant="ghost" type="button" (click)="toggle(vehicle)">
                    {{
                      (vehicle.is_active ? 'vehicles.deactivate' : 'vehicles.activate') | transloco
                    }}
                  </button>
                  <button
                    cp-button
                    variant="ghost"
                    type="button"
                    class="!text-danger"
                    [attr.aria-label]="'vehicles.deleteLabel' | transloco: { plate: vehicle.plate }"
                    (click)="remove(vehicle)"
                  >
                    <svg lucideTrash2 class="size-4" aria-hidden="true"></svg>
                    {{ 'vehicles.delete' | transloco }}
                  </button>
                </div>
              </cp-glass-card>
            </li>
          }
        </ul>
      }
    </div>
  `,
})
export default class VehiclesPage {
  private readonly api = inject(VehiclesApi);
  private readonly auth = inject(AuthService);
  private readonly dialogs = inject(DialogService);
  private readonly toasts = inject(ToastService);
  private readonly transloco = inject(TranslocoService);

  protected readonly vehicles = signal<Vehicle[]>([]);
  protected readonly loading = signal(true);

  constructor() {
    void this.load();
  }

  private async load(): Promise<void> {
    try {
      this.vehicles.set(await this.api.list());
    } catch (error) {
      this.toasts.show(apiErrorMessage(this.transloco, error), 'danger');
    } finally {
      this.loading.set(false);
    }
  }

  protected async toggle(vehicle: Vehicle): Promise<void> {
    try {
      const updated = await this.api.update(vehicle.id, { is_active: !vehicle.is_active });
      this.vehicles.update((list) => list.map((v) => (v.id === updated.id ? updated : v)));
      await this.auth.reloadMe(); // los requisitos para publicar dependen de esto
    } catch (error) {
      this.toasts.show(apiErrorMessage(this.transloco, error), 'danger');
    }
  }

  protected async remove(vehicle: Vehicle): Promise<void> {
    const t = (key: string) =>
      this.transloco.translate(`vehicles.confirmDelete.${key}`, { plate: vehicle.plate });
    const confirmed = await this.dialogs.confirm({
      title: t('title'),
      message: t('body'),
      confirmLabel: t('confirm'),
      cancelLabel: this.transloco.translate('common.cancel'),
      danger: true,
    });
    if (!confirmed) return;
    try {
      await this.api.remove(vehicle.id);
      this.vehicles.update((list) => list.filter((v) => v.id !== vehicle.id));
      await this.auth.reloadMe();
      this.toasts.show(this.transloco.translate('vehicles.deleted'), 'success');
    } catch (error) {
      this.toasts.show(apiErrorMessage(this.transloco, error), 'danger');
    }
  }
}
