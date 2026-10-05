import { DIALOG_DATA, DialogRef } from '@angular/cdk/dialog';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormControl, ReactiveFormsModule, Validators } from '@angular/forms';
import { TranslocoPipe, TranslocoService } from '@jsverse/transloco';
import { fieldError } from '../../shared/forms/validation';
import { GlassButton } from '../../shared/ui/glass-button';
import { GlassModal } from '../../shared/ui/glass-modal';
import { GlassTextarea } from '../../shared/ui/glass-textarea';

export interface ReasonDialogData {
  title: string;
  message: string;
  confirmLabel: string;
  /** Si es falso, el motivo es opcional. */
  required: boolean;
  danger?: boolean;
}

/** Resultado: el motivo (null si se dejo vacio y era opcional); undefined si se cerro. */
export interface ReasonResult {
  reason: string | null;
}

/** Confirma una decision con un motivo opcional u obligatorio (5 a 500 caracteres). */
@Component({
  selector: 'cp-reason-dialog',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, TranslocoPipe, GlassModal, GlassButton, GlassTextarea],
  template: `
    <cp-glass-modal [title]="data.title">
      <form
        id="reason-form"
        class="flex flex-col gap-3"
        (submit)="$event.preventDefault(); submit()"
        novalidate
      >
        <p class="text-muted">{{ data.message }}</p>
        <cp-glass-textarea
          [formControl]="reason"
          [label]="
            (data.required ? 'bookings.reason.label' : 'bookings.reason.optional') | transloco
          "
          [error]="error()"
        />
      </form>
      <ng-container actions>
        <button cp-button variant="secondary" type="button" (click)="ref.close()">
          {{ 'bookings.reason.back' | transloco }}
        </button>
        <button
          cp-button
          [variant]="data.danger ? 'danger' : 'primary'"
          type="submit"
          form="reason-form"
        >
          {{ data.confirmLabel }}
        </button>
      </ng-container>
    </cp-glass-modal>
  `,
})
export class ReasonDialog {
  protected readonly data = inject<ReasonDialogData>(DIALOG_DATA);
  protected readonly ref = inject<DialogRef<ReasonResult>>(DialogRef);
  private readonly transloco = inject(TranslocoService);
  private readonly submitted = signal(false);

  protected readonly reason = new FormControl('', {
    nonNullable: true,
    validators: [
      ...(this.data.required ? [Validators.required] : []),
      Validators.minLength(5),
      Validators.maxLength(500),
    ],
  });

  protected error(): string | null {
    return fieldError(this.transloco, this.reason, this.submitted());
  }

  protected submit(): void {
    this.submitted.set(true);
    this.reason.markAsTouched();
    if (this.reason.invalid) return;
    const text = this.reason.value.trim();
    this.ref.close({ reason: text || null });
  }
}
