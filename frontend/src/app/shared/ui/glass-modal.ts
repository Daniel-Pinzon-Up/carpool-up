import { CdkDialogContainer, DialogRef } from '@angular/cdk/dialog';
import { ChangeDetectionStrategy, Component, inject, input } from '@angular/core';
import { TranslocoPipe } from '@jsverse/transloco';
import { LucideX } from '@lucide/angular';
import { uniqueId } from './form-control';

/**
 * Marco visual de un dialogo abierto con DialogService. variant="sheet" lo ancla abajo
 * como hoja inferior (moviles) con su asa de arrastre visual.
 */
@Component({
  selector: 'cp-glass-modal',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [LucideX, TranslocoPipe],
  host: {
    class: 'glass-2 block max-h-[90dvh] overflow-y-auto p-6 text-text',
    '[class.cp-sheet]': 'variant() === "sheet"',
    '[class.cp-modal]': 'variant() === "modal"',
  },
  styles: `
    :host.cp-modal {
      animation: cp-fade-in 200ms ease-out;
    }
    :host.cp-sheet {
      border-bottom-left-radius: 0;
      border-bottom-right-radius: 0;
      padding-bottom: calc(1.5rem + env(safe-area-inset-bottom));
      animation: cp-sheet-in 250ms cubic-bezier(0.2, 0.8, 0.2, 1);
    }
  `,
  template: `
    @if (variant() === 'sheet') {
      <div class="mx-auto -mt-2 mb-4 h-1.5 w-12 rounded-full bg-muted/40" aria-hidden="true"></div>
    }
    <div class="mb-4 flex items-start justify-between gap-4">
      <h2 [id]="titleId" class="text-lg font-bold">{{ title() }}</h2>
      <button
        type="button"
        (click)="ref.close()"
        class="-m-2 grid size-11 shrink-0 place-items-center rounded-full text-muted transition hover:bg-glass hover:text-text"
        [attr.aria-label]="'common.close' | transloco"
      >
        <svg lucideX class="size-5" aria-hidden="true"></svg>
      </button>
    </div>
    <ng-content />
    <div class="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
      <ng-content select="[actions]" />
    </div>
  `,
})
export class GlassModal {
  readonly title = input.required<string>();
  readonly variant = input<'modal' | 'sheet'>('modal');

  protected readonly ref = inject(DialogRef);
  protected readonly titleId = uniqueId('cp-dialog-title');

  constructor() {
    // El contenedor de CDK tiene role="dialog"; se le asocia el titulo visible.
    inject(CdkDialogContainer, { optional: true })?._addAriaLabelledBy(this.titleId);
  }
}
