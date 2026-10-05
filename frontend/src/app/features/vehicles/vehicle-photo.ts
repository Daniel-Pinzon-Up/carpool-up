import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  effect,
  inject,
  input,
  signal,
} from '@angular/core';
import { DomSanitizer, SafeUrl } from '@angular/platform-browser';
import { LucideBike, LucideCar } from '@lucide/angular';
import { LoadedFile, SecureFileService } from '../../core/files/secure-file.service';
import { VehicleType, VehiclesApi } from './vehicles.api';

/** Foto del vehiculo (requiere sesion) o un icono del tipo si no hay foto. */
@Component({
  selector: 'cp-vehicle-photo',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [LucideCar, LucideBike],
  host: { class: 'block overflow-hidden rounded-2xl bg-primary/10' },
  template: `
    @if (url(); as src) {
      <img [src]="src" [alt]="alt()" class="size-full object-cover" />
    } @else {
      <div
        class="grid size-full place-items-center text-primary"
        role="img"
        [attr.aria-label]="alt()"
      >
        @if (type() === 'motorcycle') {
          <svg lucideBike class="size-1/2 max-h-12 max-w-12" aria-hidden="true"></svg>
        } @else {
          <svg lucideCar class="size-1/2 max-h-12 max-w-12" aria-hidden="true"></svg>
        }
      </div>
    }
  `,
})
export class VehiclePhoto {
  readonly vehicleId = input.required<string>();
  readonly hasPhoto = input(false);
  readonly type = input<VehicleType>('car');
  readonly alt = input('');
  /** Cambia para forzar recarga tras subir una foto nueva. */
  readonly version = input(0);

  private readonly files = inject(SecureFileService);
  private readonly api = inject(VehiclesApi);
  private readonly sanitizer = inject(DomSanitizer);
  private loaded: LoadedFile | null = null;
  protected readonly url = signal<SafeUrl | null>(null);

  constructor() {
    effect(() => {
      const id = this.vehicleId();
      const hasPhoto = this.hasPhoto();
      this.version();
      void this.load(id, hasPhoto);
    });
    inject(DestroyRef).onDestroy(() => this.files.release(this.loaded));
  }

  private async load(id: string, hasPhoto: boolean): Promise<void> {
    this.files.release(this.loaded);
    this.loaded = null;
    this.url.set(null);
    if (!hasPhoto) return;
    try {
      this.loaded = await this.files.load(this.api.photoPath(id));
      // URL local creada a partir del archivo descargado con autenticacion.
      this.url.set(this.sanitizer.bypassSecurityTrustUrl(this.loaded.url));
    } catch {
      this.url.set(null);
    }
  }
}
