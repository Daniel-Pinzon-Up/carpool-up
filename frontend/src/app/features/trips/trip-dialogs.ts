import { DIALOG_DATA, DialogRef } from '@angular/cdk/dialog';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { TranslocoPipe, TranslocoService } from '@jsverse/transloco';
import { fieldError } from '../../shared/forms/validation';
import { GlassButton } from '../../shared/ui/glass-button';
import { GlassInput } from '../../shared/ui/glass-input';
import { GlassModal } from '../../shared/ui/glass-modal';
import { GlassTextarea } from '../../shared/ui/glass-textarea';
import { addDays, pamplonaDate, pamplonaInstant } from './trips.api';

export interface CancelDialogData {
  title: string;
  message: string;
}

/** Pide el motivo de la cancelacion (obligatorio, lo veran los pasajeros). */
@Component({
  selector: 'cp-cancel-trip-dialog',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, TranslocoPipe, GlassModal, GlassButton, GlassTextarea],
  template: `
    <cp-glass-modal [title]="data.title">
      <form
        id="cancel-trip-form"
        class="flex flex-col gap-3"
        (submit)="$event.preventDefault(); submit()"
        novalidate
      >
        <p class="text-muted">{{ data.message }}</p>
        <cp-glass-textarea
          [formControl]="reason"
          [label]="'trips.cancel.reason' | transloco"
          [hint]="'trips.cancel.hint' | transloco"
          [error]="error()"
        />
      </form>
      <ng-container actions>
        <button cp-button variant="secondary" type="button" (click)="ref.close()">
          {{ 'trips.cancel.keep' | transloco }}
        </button>
        <button cp-button variant="danger" type="submit" form="cancel-trip-form">
          {{ 'trips.cancel.confirm' | transloco }}
        </button>
      </ng-container>
    </cp-glass-modal>
  `,
})
export class CancelTripDialog {
  protected readonly data = inject<CancelDialogData>(DIALOG_DATA);
  protected readonly ref = inject<DialogRef<string>>(DialogRef);
  private readonly transloco = inject(TranslocoService);
  private readonly submitted = signal(false);

  protected readonly reason = new FormControl('', {
    nonNullable: true,
    validators: [Validators.required, Validators.minLength(5), Validators.maxLength(500)],
  });

  protected error(): string | null {
    return fieldError(this.transloco, this.reason, this.submitted());
  }

  protected submit(): void {
    this.submitted.set(true);
    this.reason.markAsTouched();
    if (this.reason.valid) this.ref.close(this.reason.value.trim());
  }
}

/** Nueva fecha y hora para duplicar un viaje; devuelve el instante de salida. */
@Component({
  selector: 'cp-duplicate-dialog',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, TranslocoPipe, GlassModal, GlassButton, GlassInput],
  template: `
    <cp-glass-modal [title]="'trips.duplicate.title' | transloco">
      <form
        id="duplicate-form"
        class="flex flex-col gap-4"
        [formGroup]="form"
        (ngSubmit)="submit()"
        novalidate
      >
        <p class="text-muted">{{ 'trips.duplicate.tripHint' | transloco }}</p>
        <cp-glass-input
          formControlName="date"
          type="date"
          [label]="'publish.when.date' | transloco"
        />
        <cp-glass-input
          formControlName="time"
          type="time"
          [label]="'publish.when.time' | transloco"
        />
        @if (invalid()) {
          <p role="alert" class="text-sm text-danger">
            {{ 'trips.duplicate.invalid' | transloco }}
          </p>
        }
      </form>
      <ng-container actions>
        <button cp-button variant="secondary" type="button" (click)="ref.close()">
          {{ 'common.cancel' | transloco }}
        </button>
        <button cp-button type="submit" form="duplicate-form">
          {{ 'trips.duplicate.confirm' | transloco }}
        </button>
      </ng-container>
    </cp-glass-modal>
  `,
})
export class DuplicateDialog {
  protected readonly data = inject<{ time: string }>(DIALOG_DATA);
  protected readonly ref = inject<DialogRef<string>>(DialogRef);
  protected readonly invalid = signal(false);

  protected readonly form = new FormGroup({
    date: new FormControl(addDays(pamplonaDate(new Date()), 1), { nonNullable: true }),
    time: new FormControl(this.data.time, { nonNullable: true }),
  });

  protected submit(): void {
    const { date, time } = this.form.getRawValue();
    const ok = !!date && !!time && date >= pamplonaDate(new Date());
    this.invalid.set(!ok);
    if (ok) this.ref.close(pamplonaInstant(date, time));
  }
}
