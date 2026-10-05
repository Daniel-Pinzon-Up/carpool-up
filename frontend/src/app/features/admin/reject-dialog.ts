import { DIALOG_DATA, DialogRef } from '@angular/cdk/dialog';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormControl, ReactiveFormsModule, Validators } from '@angular/forms';
import { TranslocoPipe, TranslocoService } from '@jsverse/transloco';
import { fieldError } from '../../shared/forms/validation';
import { GlassButton } from '../../shared/ui/glass-button';
import { GlassModal } from '../../shared/ui/glass-modal';
import { GlassTextarea } from '../../shared/ui/glass-textarea';

/** Pide el motivo del rechazo; el usuario lo vera tal cual. Devuelve el texto o nada. */
@Component({
  selector: 'cp-reject-dialog',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, TranslocoPipe, GlassModal, GlassButton, GlassTextarea],
  template: `
    <cp-glass-modal [title]="'approvals.reject.title' | transloco: { name: data.name }">
      <form id="reject-form" (submit)="$event.preventDefault(); submit()" novalidate>
        <cp-glass-textarea
          [formControl]="reason"
          [label]="'approvals.reject.reason' | transloco"
          [hint]="'approvals.reject.hint' | transloco"
          [error]="error()"
        />
      </form>
      <ng-container actions>
        <button cp-button variant="secondary" type="button" (click)="ref.close()">
          {{ 'common.cancel' | transloco }}
        </button>
        <button cp-button variant="danger" type="submit" form="reject-form">
          {{ 'approvals.reject.confirm' | transloco }}
        </button>
      </ng-container>
    </cp-glass-modal>
  `,
})
export class RejectDialog {
  protected readonly data = inject<{ name: string }>(DIALOG_DATA);
  protected readonly ref = inject<DialogRef<string>>(DialogRef);
  private readonly transloco = inject(TranslocoService);
  private readonly submitted = signal(false);

  protected readonly reason = new FormControl('', {
    nonNullable: true,
    validators: [Validators.required, Validators.minLength(5), Validators.maxLength(300)],
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
