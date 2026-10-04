import { DIALOG_DATA, DialogRef } from '@angular/cdk/dialog';
import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { GlassButton } from './glass-button';
import { GlassModal } from './glass-modal';

export interface ConfirmDialogData {
  title: string;
  message: string;
  confirmLabel: string;
  cancelLabel: string;
  danger?: boolean;
}

@Component({
  selector: 'cp-confirm-dialog',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [GlassModal, GlassButton],
  template: `
    <cp-glass-modal [title]="data.title">
      <p class="text-muted">{{ data.message }}</p>
      <ng-container actions>
        <button cp-button variant="secondary" type="button" (click)="ref.close(false)">
          {{ data.cancelLabel }}
        </button>
        <button
          cp-button
          [variant]="data.danger ? 'danger' : 'primary'"
          type="button"
          (click)="ref.close(true)"
        >
          {{ data.confirmLabel }}
        </button>
      </ng-container>
    </cp-glass-modal>
  `,
})
export class ConfirmDialog {
  protected readonly data = inject<ConfirmDialogData>(DIALOG_DATA);
  protected readonly ref = inject<DialogRef<boolean>>(DialogRef);
}
