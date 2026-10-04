import { DIALOG_DATA, DialogRef } from '@angular/cdk/dialog';
import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { TranslocoPipe } from '@jsverse/transloco';
import { GlassButton } from '../../shared/ui/glass-button';
import { GlassModal } from '../../shared/ui/glass-modal';
import { SeatPicker } from '../../shared/ui/seat-picker';

/** Contenido de ejemplo para el modal y la hoja inferior del catalogo. */
@Component({
  selector: 'cp-sample-sheet',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [GlassModal, GlassButton, SeatPicker, ReactiveFormsModule, TranslocoPipe],
  template: `
    <cp-glass-modal [title]="'catalog.dialogs.sampleTitle' | transloco" [variant]="data.variant">
      <p class="mb-4 text-muted">{{ 'catalog.dialogs.sampleBody' | transloco }}</p>
      <cp-seat-picker [label]="'catalog.seats.label' | transloco" [formControl]="seats" [max]="3" />
      <ng-container actions>
        <button cp-button variant="secondary" type="button" (click)="ref.close()">
          {{ 'common.cancel' | transloco }}
        </button>
        <button cp-button type="button" (click)="ref.close()">
          {{ 'common.confirm' | transloco }}
        </button>
      </ng-container>
    </cp-glass-modal>
  `,
})
export class SampleSheet {
  protected readonly data = inject<{ variant: 'modal' | 'sheet' }>(DIALOG_DATA);
  protected readonly ref = inject(DialogRef);
  protected readonly seats = new FormControl(1, { nonNullable: true });
}
