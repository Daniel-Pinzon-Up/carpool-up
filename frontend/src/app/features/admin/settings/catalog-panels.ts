import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { TranslocoPipe, TranslocoService } from '@jsverse/transloco';
import { LucidePencil, LucidePlus, LucideTrash2, LucideX } from '@icons';
import { apiErrorMessage } from '../../../core/http/api-error-message';
import { LOCALE } from '../../../core/i18n/locale';
import { DialogService } from '../../../shared/ui/dialog.service';
import { GlassButton } from '../../../shared/ui/glass-button';
import { GlassCard } from '../../../shared/ui/glass-card';
import { GlassCheckbox } from '../../../shared/ui/glass-checkbox';
import { GlassInput } from '../../../shared/ui/glass-input';
import { GlassSelect } from '../../../shared/ui/glass-select';
import { StatusBadge } from '../../../shared/ui/status-badge';
import { ToastService } from '../../../shared/ui/toast.service';
import { VehicleType } from '../../vehicles/vehicles.api';
import { AdminApi, CatalogKind, CatalogPlace, PicoPlacaRule, Semester } from '../admin.api';

/** Base comun: lista, formulario de alta o edicion y mensajes. */
abstract class CatalogPanel<T extends { id: string }> {
  protected readonly api = inject(AdminApi);
  protected readonly dialogs = inject(DialogService);
  protected readonly transloco = inject(TranslocoService);
  protected readonly toast = inject(ToastService);

  protected readonly items = signal<T[]>([]);
  protected readonly editing = signal<string | null>(null);
  protected readonly submitted = signal(false);

  protected abstract fetch(): Promise<T[]>;

  protected async load(): Promise<void> {
    try {
      this.items.set(await this.fetch());
    } catch (error) {
      this.fail(error);
    }
  }

  protected fail(error: unknown): void {
    this.toast.show(apiErrorMessage(this.transloco, error), 'danger');
  }

  protected done(key: string): void {
    this.toast.show(this.transloco.translate(key), 'success');
  }

  protected async confirmDelete(name: string): Promise<boolean> {
    return this.dialogs.confirm({
      title: this.transloco.translate('admin.settings.deleteTitle', { name }),
      message: this.transloco.translate('admin.settings.deleteMessage'),
      confirmLabel: this.transloco.translate('admin.settings.delete'),
      cancelLabel: this.transloco.translate('common.cancel'),
      danger: true,
    });
  }

  protected date(iso: string | null): string {
    if (!iso) return '-';
    const [y, m, d] = iso.split('-').map(Number);
    return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString(LOCALE, {
      dateStyle: 'medium',
      timeZone: 'UTC',
    });
  }
}

const SHARED = [
  ReactiveFormsModule,
  TranslocoPipe,
  GlassButton,
  GlassCard,
  GlassInput,
  LucidePencil,
  LucidePlus,
  LucideX,
];

/** Semestres academicos: definen la vigencia de los documentos. */
@Component({
  selector: 'cp-semesters-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [...SHARED, LucideTrash2],
  template: `
    <div class="flex flex-col gap-3">
      <cp-glass-card>
        <form [formGroup]="form" class="grid gap-3 sm:grid-cols-2" (ngSubmit)="save()" novalidate>
          <cp-glass-input
            formControlName="name"
            [label]="'admin.semesters.name' | transloco"
            hint="2026-1"
            [error]="error('name')"
          />
          <cp-glass-input
            formControlName="revalidation_deadline"
            type="date"
            [label]="'admin.semesters.deadline' | transloco"
            [hint]="'admin.semesters.deadlineHint' | transloco"
          />
          <cp-glass-input
            formControlName="starts_on"
            type="date"
            [label]="'admin.semesters.starts' | transloco"
            [error]="error('starts_on')"
          />
          <cp-glass-input
            formControlName="ends_on"
            type="date"
            [label]="'admin.semesters.ends' | transloco"
            [error]="error('ends_on')"
          />
          <div class="flex gap-2 sm:col-span-2">
            <button cp-button type="submit">
              <svg lucidePlus class="size-4" aria-hidden="true"></svg>
              {{ (editing() ? 'admin.settings.update' : 'admin.semesters.add') | transloco }}
            </button>
            @if (editing()) {
              <button cp-button variant="ghost" type="button" (click)="reset()">
                <svg lucideX class="size-4" aria-hidden="true"></svg>
                {{ 'common.cancel' | transloco }}
              </button>
            }
          </div>
        </form>
      </cp-glass-card>
      @for (s of items(); track s.id) {
        <cp-glass-card class="flex flex-wrap items-center gap-3">
          <div class="min-w-0 flex-1">
            <p class="font-semibold">{{ s.name }}</p>
            <p class="text-sm text-muted">
              {{ date(s.starts_on) }} → {{ date(s.ends_on) }} ·
              {{
                'admin.semesters.deadlineShort' | transloco: { date: date(s.revalidation_deadline) }
              }}
            </p>
          </div>
          <button
            cp-button
            variant="ghost"
            type="button"
            [attr.aria-label]="'admin.settings.edit' | transloco"
            (click)="edit(s)"
          >
            <svg lucidePencil class="size-4" aria-hidden="true"></svg>
          </button>
          <button
            cp-button
            variant="ghost"
            type="button"
            [attr.aria-label]="'admin.settings.delete' | transloco"
            (click)="remove(s)"
          >
            <svg lucideTrash2 class="size-4" aria-hidden="true"></svg>
          </button>
        </cp-glass-card>
      }
    </div>
  `,
})
export class SemestersPanel extends CatalogPanel<Semester> {
  protected readonly form = new FormGroup({
    name: new FormControl('', {
      nonNullable: true,
      validators: [Validators.required, Validators.pattern(/^[0-9A-Za-z][0-9A-Za-z _-]{2,19}$/)],
    }),
    starts_on: new FormControl('', { nonNullable: true, validators: Validators.required }),
    ends_on: new FormControl('', { nonNullable: true, validators: Validators.required }),
    revalidation_deadline: new FormControl('', { nonNullable: true }),
  });

  constructor() {
    super();
    void this.load();
  }

  protected fetch(): Promise<Semester[]> {
    return this.api.semesters();
  }

  protected error(name: keyof typeof this.form.controls): string | null {
    const control = this.form.controls[name];
    return this.submitted() && control.invalid
      ? this.transloco.translate('admin.settings.required')
      : null;
  }

  protected edit(s: Semester): void {
    this.editing.set(s.id);
    this.form.setValue({
      name: s.name,
      starts_on: s.starts_on,
      ends_on: s.ends_on,
      revalidation_deadline: s.revalidation_deadline,
    });
  }

  protected reset(): void {
    this.editing.set(null);
    this.submitted.set(false);
    this.form.reset();
  }

  protected async save(): Promise<void> {
    this.submitted.set(true);
    if (this.form.invalid) return;
    const value = this.form.getRawValue();
    try {
      await this.api.saveSemester(
        {
          ...value,
          revalidation_deadline: value.revalidation_deadline || (null as unknown as string),
        },
        this.editing() ?? undefined,
      );
      this.done('admin.settings.savedItem');
      this.reset();
      await this.load();
    } catch (error) {
      this.fail(error);
    }
  }

  protected async remove(s: Semester): Promise<void> {
    if (!(await this.confirmDelete(s.name))) return;
    try {
      await this.api.deleteSemester(s.id);
      this.done('admin.settings.deleted');
      await this.load();
    } catch (error) {
      this.fail(error);
    }
  }
}

/** Lugares del catalogo: sedes, barrios y puntos de referencia del buscador. */
@Component({
  selector: 'cp-places-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [...SHARED, GlassSelect, StatusBadge],
  template: `
    <div class="flex flex-col gap-3">
      <cp-glass-card>
        <form [formGroup]="form" class="grid gap-3 sm:grid-cols-2" (ngSubmit)="save()" novalidate>
          <cp-glass-input
            formControlName="name"
            [label]="'admin.places.name' | transloco"
            [error]="error('name')"
          />
          <cp-glass-select
            formControlName="kind"
            [label]="'admin.places.kind' | transloco"
            [options]="kinds()"
          />
          <cp-glass-input
            formControlName="lat"
            type="number"
            inputmode="decimal"
            [label]="'admin.places.lat' | transloco"
            [error]="error('lat')"
          />
          <cp-glass-input
            formControlName="lon"
            type="number"
            inputmode="decimal"
            [label]="'admin.places.lon' | transloco"
            [error]="error('lon')"
          />
          <div class="flex gap-2 sm:col-span-2">
            <button cp-button type="submit">
              <svg lucidePlus class="size-4" aria-hidden="true"></svg>
              {{ (editing() ? 'admin.settings.update' : 'admin.places.add') | transloco }}
            </button>
            @if (editing()) {
              <button cp-button variant="ghost" type="button" (click)="reset()">
                <svg lucideX class="size-4" aria-hidden="true"></svg>
                {{ 'common.cancel' | transloco }}
              </button>
            }
          </div>
        </form>
      </cp-glass-card>
      @for (p of items(); track p.id) {
        <cp-glass-card class="flex flex-wrap items-center gap-3" [class.opacity-60]="!p.is_active">
          <div class="min-w-0 flex-1">
            <p class="font-semibold">{{ p.name }}</p>
            <p class="text-sm text-muted">
              {{ 'places.groups.' + p.kind | transloco }} · {{ p.lat }}, {{ p.lon }}
            </p>
          </div>
          <cp-status-badge [variant]="p.is_active ? 'success' : 'neutral'">{{
            (p.is_active ? 'vehicles.active' : 'vehicles.inactive') | transloco
          }}</cp-status-badge>
          <button
            cp-button
            variant="ghost"
            type="button"
            [attr.aria-label]="'admin.settings.edit' | transloco"
            (click)="edit(p)"
          >
            <svg lucidePencil class="size-4" aria-hidden="true"></svg>
          </button>
          <button cp-button variant="secondary" type="button" (click)="toggle(p)">
            {{ (p.is_active ? 'vehicles.deactivate' : 'vehicles.activate') | transloco }}
          </button>
        </cp-glass-card>
      }
    </div>
  `,
})
export class PlacesPanel extends CatalogPanel<CatalogPlace> {
  protected readonly form = new FormGroup({
    name: new FormControl('', {
      nonNullable: true,
      validators: [Validators.required, Validators.minLength(2)],
    }),
    kind: new FormControl<CatalogKind>('landmark', { nonNullable: true }),
    lat: new FormControl('', { nonNullable: true, validators: Validators.required }),
    lon: new FormControl('', { nonNullable: true, validators: Validators.required }),
  });
  protected readonly kinds = computed(() => {
    return (['campus', 'sector', 'landmark'] as const).map((value) => ({
      value,
      label: this.transloco.translate(`places.groups.${value}`),
    }));
  });

  constructor() {
    super();
    void this.load();
  }

  protected async fetch(): Promise<CatalogPlace[]> {
    return (await this.api.places()).filter((p) => p.kind !== 'custom');
  }

  protected error(name: keyof typeof this.form.controls): string | null {
    const control = this.form.controls[name];
    return this.submitted() && control.invalid
      ? this.transloco.translate('admin.settings.required')
      : null;
  }

  protected edit(p: CatalogPlace): void {
    this.editing.set(p.id);
    this.form.setValue({
      name: p.name,
      kind: p.kind as CatalogKind,
      lat: String(p.lat),
      lon: String(p.lon),
    });
  }

  protected reset(): void {
    this.editing.set(null);
    this.submitted.set(false);
    this.form.reset();
  }

  protected async save(): Promise<void> {
    this.submitted.set(true);
    if (this.form.invalid) return;
    const { name, kind, lat, lon } = this.form.getRawValue();
    try {
      await this.api.savePlace(
        { name: name.trim(), kind, lat: Number(lat), lon: Number(lon) },
        this.editing() ?? undefined,
      );
      this.done('admin.settings.savedItem');
      this.reset();
      await this.load();
    } catch (error) {
      this.fail(error);
    }
  }

  protected async toggle(p: CatalogPlace): Promise<void> {
    try {
      if (p.is_active) await this.api.deactivatePlace(p.id);
      else await this.api.savePlace({ is_active: true }, p.id);
      this.done('admin.settings.savedItem');
      await this.load();
    } catch (error) {
      this.fail(error);
    }
  }
}

/** Reglas de pico y placa por tipo de vehiculo, dia de la semana y vigencia. */
@Component({
  selector: 'cp-pico-placa-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [...SHARED, GlassCheckbox, GlassSelect, StatusBadge, LucideTrash2],
  template: `
    <div class="flex flex-col gap-3">
      <cp-glass-card>
        <form [formGroup]="form" class="grid gap-3 sm:grid-cols-2" (ngSubmit)="save()" novalidate>
          <cp-glass-select
            formControlName="vehicle_type"
            [label]="'admin.picoPlaca.vehicle' | transloco"
            [options]="types()"
          />
          <cp-glass-select
            formControlName="weekday"
            [label]="'admin.picoPlaca.weekday' | transloco"
            [options]="weekdays()"
          />
          <cp-glass-input
            formControlName="digits"
            inputmode="numeric"
            [label]="'admin.picoPlaca.digits' | transloco"
            [hint]="'admin.picoPlaca.digitsHint' | transloco"
            [error]="error('digits')"
          />
          <cp-glass-checkbox formControlName="is_active" class="self-center">{{
            'vehicles.active' | transloco
          }}</cp-glass-checkbox>
          <cp-glass-input
            formControlName="valid_from"
            type="date"
            [label]="'admin.picoPlaca.from' | transloco"
            [error]="error('valid_from')"
          />
          <cp-glass-input
            formControlName="valid_to"
            type="date"
            [label]="'admin.picoPlaca.to' | transloco"
            [hint]="'admin.picoPlaca.toHint' | transloco"
          />
          <div class="flex gap-2 sm:col-span-2">
            <button cp-button type="submit">
              <svg lucidePlus class="size-4" aria-hidden="true"></svg>
              {{ (editing() ? 'admin.settings.update' : 'admin.picoPlaca.add') | transloco }}
            </button>
            @if (editing()) {
              <button cp-button variant="ghost" type="button" (click)="reset()">
                <svg lucideX class="size-4" aria-hidden="true"></svg>
                {{ 'common.cancel' | transloco }}
              </button>
            }
          </div>
        </form>
      </cp-glass-card>
      @for (r of items(); track r.id) {
        <cp-glass-card class="flex flex-wrap items-center gap-3" [class.opacity-60]="!r.is_active">
          <div class="min-w-0 flex-1">
            <p class="font-semibold">
              {{ 'vehicles.types.' + r.vehicle_type | transloco }} · {{ weekday(r.weekday) }} ·
              {{ r.restricted_digits.join(', ') }}
            </p>
            <p class="text-sm text-muted">
              {{ date(r.valid_from) }} →
              {{ r.valid_to ? date(r.valid_to) : ('admin.picoPlaca.open' | transloco) }}
            </p>
          </div>
          <cp-status-badge [variant]="r.is_active ? 'success' : 'neutral'">{{
            (r.is_active ? 'vehicles.active' : 'vehicles.inactive') | transloco
          }}</cp-status-badge>
          <button
            cp-button
            variant="ghost"
            type="button"
            [attr.aria-label]="'admin.settings.edit' | transloco"
            (click)="edit(r)"
          >
            <svg lucidePencil class="size-4" aria-hidden="true"></svg>
          </button>
          <button
            cp-button
            variant="ghost"
            type="button"
            [attr.aria-label]="'admin.settings.delete' | transloco"
            (click)="remove(r)"
          >
            <svg lucideTrash2 class="size-4" aria-hidden="true"></svg>
          </button>
        </cp-glass-card>
      }
    </div>
  `,
})
export class PicoPlacaPanel extends CatalogPanel<PicoPlacaRule> {
  protected readonly form = new FormGroup({
    vehicle_type: new FormControl<VehicleType>('car', { nonNullable: true }),
    weekday: new FormControl('0', { nonNullable: true }),
    digits: new FormControl('', {
      nonNullable: true,
      validators: [Validators.required, Validators.pattern(/^\s*\d(\s*,\s*\d)*\s*$/)],
    }),
    valid_from: new FormControl('', { nonNullable: true, validators: Validators.required }),
    valid_to: new FormControl('', { nonNullable: true }),
    is_active: new FormControl(true, { nonNullable: true }),
  });
  protected readonly types = computed(() => {
    return (['car', 'motorcycle'] as const).map((value) => ({
      value,
      label: this.transloco.translate(`vehicles.types.${value}`),
    }));
  });
  protected readonly weekdays = computed(() =>
    [0, 1, 2, 3, 4, 5, 6].map((value) => ({ value: String(value), label: this.weekday(value) })),
  );

  constructor() {
    super();
    void this.load();
  }

  protected fetch(): Promise<PicoPlacaRule[]> {
    return this.api.picoPlaca();
  }

  /** 0 es lunes, como en el backend (date.weekday()). 2024-01-01 fue lunes. */
  protected weekday(day: number): string {
    return new Date(Date.UTC(2024, 0, 1 + day)).toLocaleDateString(LOCALE, {
      weekday: 'long',
      timeZone: 'UTC',
    });
  }

  protected error(name: keyof typeof this.form.controls): string | null {
    const control = this.form.controls[name];
    return this.submitted() && control.invalid
      ? this.transloco.translate('admin.settings.required')
      : null;
  }

  protected edit(r: PicoPlacaRule): void {
    this.editing.set(r.id);
    this.form.setValue({
      vehicle_type: r.vehicle_type,
      weekday: String(r.weekday),
      digits: r.restricted_digits.join(', '),
      valid_from: r.valid_from,
      valid_to: r.valid_to ?? '',
      is_active: r.is_active,
    });
  }

  protected reset(): void {
    this.editing.set(null);
    this.submitted.set(false);
    this.form.reset();
  }

  protected async save(): Promise<void> {
    this.submitted.set(true);
    if (this.form.invalid) return;
    const v = this.form.getRawValue();
    try {
      await this.api.savePicoPlaca(
        {
          vehicle_type: v.vehicle_type,
          weekday: Number(v.weekday),
          restricted_digits: v.digits.split(',').map((d) => Number(d.trim())),
          valid_from: v.valid_from,
          valid_to: v.valid_to || null,
          is_active: v.is_active,
        },
        this.editing() ?? undefined,
      );
      this.done('admin.settings.savedItem');
      this.reset();
      await this.load();
    } catch (error) {
      this.fail(error);
    }
  }

  protected async remove(r: PicoPlacaRule): Promise<void> {
    if (!(await this.confirmDelete(this.weekday(r.weekday)))) return;
    try {
      await this.api.deletePicoPlaca(r.id);
      this.done('admin.settings.deleted');
      await this.load();
    } catch (error) {
      this.fail(error);
    }
  }
}
