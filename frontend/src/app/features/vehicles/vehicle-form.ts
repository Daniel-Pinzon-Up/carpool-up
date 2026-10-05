import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  input,
  OnInit,
  signal,
} from '@angular/core';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import {
  AbstractControl,
  FormBuilder,
  ReactiveFormsModule,
  ValidationErrors,
  Validators,
} from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { TranslocoPipe, TranslocoService } from '@jsverse/transloco';
import { LucideArrowLeft, LucideBike, LucideCar, LucideCircleAlert } from '@lucide/angular';
import { AuthService } from '../../core/auth/auth.service';
import { apiErrorMessage } from '../../core/http/api-error-message';
import { MetaService } from '../../core/meta/meta.service';
import { fieldError } from '../../shared/forms/validation';
import { Choice, ChoiceCards } from '../../shared/ui/choice-cards';
import { FileDrop } from '../../shared/ui/file-drop';
import { GlassButton } from '../../shared/ui/glass-button';
import { GlassCard } from '../../shared/ui/glass-card';
import { GlassCheckbox } from '../../shared/ui/glass-checkbox';
import { GlassInput } from '../../shared/ui/glass-input';
import { SeatPicker } from '../../shared/ui/seat-picker';
import { Skeleton } from '../../shared/ui/skeleton';
import { ToastService } from '../../shared/ui/toast.service';
import {
  CAPACITY,
  MIN_YEAR,
  PLATE_PATTERNS,
  Vehicle,
  VehicleType,
  VehiclesApi,
  normalizePlate,
} from './vehicles.api';

const PHOTO_TYPES = ['image/jpeg', 'image/png', 'image/webp'];

/** Alta y edicion de un vehiculo. Tipo y placa solo se eligen al crearlo. */
@Component({
  selector: 'cp-vehicle-form',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    ReactiveFormsModule,
    RouterLink,
    TranslocoPipe,
    ChoiceCards,
    FileDrop,
    GlassButton,
    GlassCard,
    GlassCheckbox,
    GlassInput,
    SeatPicker,
    Skeleton,
    LucideArrowLeft,
    LucideCircleAlert,
  ],
  templateUrl: './vehicle-form.html',
})
export default class VehicleForm implements OnInit {
  /** Viene de la ruta /vehiculos/:id; ausente al crear. */
  readonly id = input<string>();

  private readonly api = inject(VehiclesApi);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly transloco = inject(TranslocoService);
  private readonly toasts = inject(ToastService);
  private readonly fb = inject(FormBuilder).nonNullable;
  protected readonly meta = inject(MetaService);

  protected readonly photoTypes = PHOTO_TYPES;
  protected readonly maxYear = new Date().getFullYear() + 1;
  protected readonly existing = signal<Vehicle | null>(null);
  protected readonly loading = signal(false);
  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly submitted = signal(false);
  protected readonly isEdit = computed(() => !!this.id());

  protected readonly form = this.fb.group({
    type: ['car' as string, Validators.required],
    plate: ['', [Validators.required, (c: AbstractControl) => this.plateRule(c)]],
    brand: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(40)]],
    model: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(40)]],
    color: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(40)]],
    year: [
      new Date().getFullYear() - 5,
      [Validators.required, Validators.min(MIN_YEAR), Validators.max(this.maxYear)],
    ],
    capacity: [5, Validators.required],
    luggage_space: [false],
    photo: this.fb.control<File | null>(null),
  });

  private readonly typeValue = toSignal(this.form.controls.type.valueChanges, {
    initialValue: this.form.controls.type.value,
  });
  protected readonly vehicleType = computed(
    () => (this.existing()?.type ?? this.typeValue()) as VehicleType,
  );
  protected readonly capacityRange = computed(() => CAPACITY[this.vehicleType()]);
  protected readonly typeChoices = computed<Choice[]>(() =>
    (['car', 'motorcycle'] as const).map((value) => ({
      value,
      icon: value === 'car' ? LucideCar : LucideBike,
      title: this.transloco.translate(`vehicles.types.${value}`),
      description: this.transloco.translate(`vehicles.typeHelp.${value}`),
    })),
  );

  constructor() {
    void this.meta.load();
    this.form.controls.type.valueChanges.pipe(takeUntilDestroyed()).subscribe((type) => {
      const [min, max] = CAPACITY[type as VehicleType];
      const capacity = this.form.controls.capacity;
      capacity.setValue(Math.min(Math.max(capacity.value, min), max));
      this.form.controls.plate.updateValueAndValidity();
    });
  }

  ngOnInit(): void {
    const id = this.id();
    if (id) void this.loadExisting(id);
  }

  private async loadExisting(id: string): Promise<void> {
    this.loading.set(true);
    try {
      const vehicle = (await this.api.list()).find((v) => v.id === id) ?? null;
      if (!vehicle) {
        await this.router.navigateByUrl('/vehiculos');
        return;
      }
      this.existing.set(vehicle);
      this.form.patchValue({ ...vehicle, photo: null });
      this.form.controls.type.disable();
      this.form.controls.plate.disable();
    } finally {
      this.loading.set(false);
    }
  }

  private plateRule(control: AbstractControl): ValidationErrors | null {
    const value = normalizePlate(String(control.value ?? ''));
    if (!value) return null;
    const type = (control.parent?.get('type')?.value ?? 'car') as VehicleType;
    return PLATE_PATTERNS[type].test(value) ? null : { plate: true };
  }

  protected err(name: keyof typeof this.form.controls): string | null {
    const control = this.form.controls[name];
    if (control.errors?.['plate'] && (control.touched || this.submitted())) {
      return this.transloco.translate(`vehicles.plateError.${this.vehicleType()}`);
    }
    if (control.errors?.['min'] || control.errors?.['max']) {
      return this.transloco.translate('vehicles.yearError', { min: MIN_YEAR, max: this.maxYear });
    }
    return fieldError(this.transloco, control, this.submitted());
  }

  protected async submit(): Promise<void> {
    this.submitted.set(true);
    this.error.set(null);
    this.form.markAllAsTouched();
    if (this.form.invalid || this.busy()) return;
    this.busy.set(true);
    const value = this.form.getRawValue();
    try {
      const fields = {
        brand: value.brand.trim(),
        model: value.model.trim(),
        color: value.color.trim(),
        year: Number(value.year),
        capacity: value.capacity,
        luggage_space: value.luggage_space,
      };
      const existing = this.existing();
      const vehicle = existing
        ? await this.api.update(existing.id, fields)
        : await this.api.create({
            ...fields,
            type: value.type as VehicleType,
            plate: normalizePlate(value.plate),
          });
      if (value.photo) await this.api.uploadPhoto(vehicle.id, value.photo);
      await this.auth.reloadMe();
      this.toasts.show(
        this.transloco.translate(existing ? 'vehicles.saved' : 'vehicles.created'),
        'success',
      );
      await this.router.navigateByUrl('/vehiculos');
    } catch (error) {
      this.error.set(apiErrorMessage(this.transloco, error));
    } finally {
      this.busy.set(false);
    }
  }
}
