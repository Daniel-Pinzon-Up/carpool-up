import { DIALOG_DATA, DialogRef } from '@angular/cdk/dialog';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { TranslocoPipe, TranslocoService } from '@jsverse/transloco';
import { fieldError } from '../../shared/forms/validation';
import { GlassButton } from '../../shared/ui/glass-button';
import { GlassModal } from '../../shared/ui/glass-modal';
import { GlassSelect } from '../../shared/ui/glass-select';
import { GlassTextarea } from '../../shared/ui/glass-textarea';

export interface SuspendResult {
  reason: string;
  days: number | null;
}

/** Suspender una cuenta: motivo obligatorio y duracion (o hasta reactivarla). */
@Component({
  selector: 'cp-suspend-dialog',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    ReactiveFormsModule,
    TranslocoPipe,
    GlassButton,
    GlassModal,
    GlassSelect,
    GlassTextarea,
  ],
  template: `
    <cp-glass-modal [title]="'admin.users.suspendTitle' | transloco: { name: data.name }">
      <form
        id="suspend-form"
        class="flex flex-col gap-4"
        [formGroup]="form"
        (ngSubmit)="submit()"
        novalidate
      >
        <p class="text-muted">{{ 'admin.users.suspendHelp' | transloco }}</p>
        <cp-glass-select
          formControlName="days"
          [label]="'admin.users.duration' | transloco"
          [options]="durations"
        />
        <cp-glass-textarea
          formControlName="reason"
          [label]="'bookings.reason.label' | transloco"
          [error]="error()"
        />
      </form>
      <ng-container actions>
        <button cp-button variant="secondary" type="button" (click)="ref.close()">
          {{ 'common.cancel' | transloco }}
        </button>
        <button cp-button variant="danger" type="submit" form="suspend-form">
          {{ 'admin.users.suspend' | transloco }}
        </button>
      </ng-container>
    </cp-glass-modal>
  `,
})
export class SuspendDialog {
  protected readonly data = inject<{ name: string }>(DIALOG_DATA);
  protected readonly ref = inject<DialogRef<SuspendResult>>(DialogRef);
  private readonly transloco = inject(TranslocoService);
  private readonly submitted = signal(false);

  protected readonly durations = ['1', '3', '7', '30', ''].map((value) => ({
    value,
    label: value
      ? this.transloco.translate('admin.users.days', { count: value })
      : this.transloco.translate('admin.users.untilReinstated'),
  }));
  protected readonly form = new FormGroup({
    days: new FormControl('7', { nonNullable: true }),
    reason: new FormControl('', {
      nonNullable: true,
      validators: [Validators.required, Validators.minLength(5), Validators.maxLength(300)],
    }),
  });

  protected error(): string | null {
    return fieldError(this.transloco, this.form.controls.reason, this.submitted());
  }

  protected submit(): void {
    this.submitted.set(true);
    this.form.markAllAsTouched();
    if (this.form.invalid) return;
    const { days, reason } = this.form.getRawValue();
    this.ref.close({ reason: reason.trim(), days: days ? Number(days) : null });
  }
}

/** Atender una emergencia: que se hizo (queda en la auditoria). */
@Component({
  selector: 'cp-resolution-dialog',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, TranslocoPipe, GlassButton, GlassModal, GlassTextarea],
  template: `
    <cp-glass-modal [title]="'admin.emergencies.handleTitle' | transloco">
      <form
        id="resolution-form"
        class="flex flex-col gap-3"
        (submit)="$event.preventDefault(); submit()"
        novalidate
      >
        <cp-glass-textarea
          [formControl]="resolution"
          [label]="'admin.emergencies.resolution' | transloco"
          [error]="error()"
        />
      </form>
      <ng-container actions>
        <button cp-button variant="secondary" type="button" (click)="ref.close()">
          {{ 'common.cancel' | transloco }}
        </button>
        <button cp-button type="submit" form="resolution-form">
          {{ 'admin.emergencies.handle' | transloco }}
        </button>
      </ng-container>
    </cp-glass-modal>
  `,
})
export class ResolutionDialog {
  protected readonly ref = inject<DialogRef<string>>(DialogRef);
  private readonly transloco = inject(TranslocoService);
  private readonly submitted = signal(false);
  protected readonly resolution = new FormControl('', {
    nonNullable: true,
    validators: [Validators.required, Validators.minLength(5), Validators.maxLength(500)],
  });

  protected error(): string | null {
    return fieldError(this.transloco, this.resolution, this.submitted());
  }

  protected submit(): void {
    this.submitted.set(true);
    this.resolution.markAsTouched();
    if (this.resolution.valid) this.ref.close(this.resolution.value.trim());
  }
}
