import { DialogRef } from '@angular/cdk/dialog';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { FormControl, ReactiveFormsModule, Validators } from '@angular/forms';
import { TranslocoPipe, TranslocoService } from '@jsverse/transloco';
import { LucideCircleAlert } from '@lucide/angular';
import { apiErrorMessage } from '../../core/http/api-error-message';
import { GlassButton } from '../ui/glass-button';
import { GlassInput } from '../ui/glass-input';
import { GlassModal } from '../ui/glass-modal';
import { MapMarker, MapView, PickedPoint } from './map-view';
import { PlaceValue, PlacesApi } from './places.api';

/** Elegir un punto tocando el mapa. Crea un pin privado y lo devuelve. */
@Component({
  selector: 'cp-map-pick-dialog',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    ReactiveFormsModule,
    TranslocoPipe,
    GlassModal,
    GlassButton,
    GlassInput,
    MapView,
    LucideCircleAlert,
  ],
  styles: `
    :host {
      display: block;
      width: min(92vw, 44rem);
    }
  `,
  template: `
    <cp-glass-modal [title]="'map.pickTitle' | transloco">
      <cp-map-view
        class="h-80 w-full"
        [pickable]="true"
        [markers]="markers()"
        (picked)="picked.set($event)"
      />
      @if (picked(); as point) {
        <p class="mt-2 text-sm text-muted">
          {{ 'map.pickedAt' | transloco: { lat: point.lat.toFixed(5), lon: point.lon.toFixed(5) } }}
        </p>
      }
      <cp-glass-input
        class="mt-4"
        [formControl]="name"
        [label]="'map.pinName' | transloco"
        [hint]="'map.pinNameHint' | transloco"
      />
      @if (error()) {
        <p role="alert" class="mt-3 flex gap-2 text-sm text-danger">
          <svg lucideCircleAlert class="size-5 shrink-0" aria-hidden="true"></svg>
          {{ error() }}
        </p>
      }
      <ng-container actions>
        <button cp-button variant="secondary" type="button" (click)="ref.close()">
          {{ 'common.cancel' | transloco }}
        </button>
        <button
          cp-button
          type="button"
          [disabled]="!picked()"
          [loading]="busy()"
          (click)="confirm()"
        >
          {{ 'map.usePoint' | transloco }}
        </button>
      </ng-container>
    </cp-glass-modal>
  `,
})
export class MapPickDialog {
  protected readonly ref = inject<DialogRef<PlaceValue>>(DialogRef);
  private readonly places = inject(PlacesApi);
  private readonly transloco = inject(TranslocoService);

  protected readonly picked = signal<PickedPoint | null>(null);
  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly name = new FormControl(this.transloco.translate('map.defaultPinName'), {
    nonNullable: true,
    validators: [Validators.required, Validators.maxLength(80)],
  });
  protected readonly markers = computed<MapMarker[]>(() => {
    const point = this.picked();
    return point
      ? [{ ...point, kind: 'pin', label: this.transloco.translate('map.selectedPoint') }]
      : [];
  });

  protected async confirm(): Promise<void> {
    const point = this.picked();
    if (!point || this.busy()) return;
    this.busy.set(true);
    this.error.set(null);
    try {
      const name = this.name.value.trim() || this.transloco.translate('map.defaultPinName');
      const place = await this.places.createCustom(name.slice(0, 80), point.lat, point.lon);
      this.ref.close(place);
    } catch (error) {
      this.error.set(apiErrorMessage(this.transloco, error));
    } finally {
      this.busy.set(false);
    }
  }
}
