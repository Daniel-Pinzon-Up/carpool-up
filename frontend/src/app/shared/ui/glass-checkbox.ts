import { ChangeDetectionStrategy, Component, forwardRef, input } from '@angular/core';
import { NG_VALUE_ACCESSOR } from '@angular/forms';
import { LucideCheck } from '@icons';
import { FormControlBase, uniqueId } from './form-control';

/** Casilla nativa con estilo propio. El texto (con enlaces si hace falta) va proyectado. */
@Component({
  selector: 'cp-glass-checkbox',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [LucideCheck],
  providers: [
    { provide: NG_VALUE_ACCESSOR, useExisting: forwardRef(() => GlassCheckbox), multi: true },
  ],
  host: { class: 'block' },
  template: `
    <div class="flex items-start gap-3">
      <span class="relative mt-0.5 grid size-6 shrink-0 place-items-center">
        <input
          type="checkbox"
          [id]="id"
          class="peer absolute inset-0 size-6 cursor-pointer appearance-none rounded-lg border-2 border-muted bg-glass transition checked:border-accent checked:bg-accent focus-visible:outline-3 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
          [checked]="value() === true"
          [disabled]="disabled()"
          [attr.aria-invalid]="error() ? true : null"
          [attr.aria-describedby]="error() ? id + '-error' : null"
          (change)="update($any($event.target).checked)"
          (blur)="onTouched()"
        />
        <svg
          lucideCheck
          class="pointer-events-none relative size-4 text-on-accent opacity-0 peer-checked:opacity-100"
          aria-hidden="true"
        ></svg>
      </span>
      <label [for]="id" class="cursor-pointer text-sm leading-6"><ng-content /></label>
    </div>
    @if (error()) {
      <p [id]="id + '-error'" class="mt-1 ml-9 text-sm text-danger">{{ error() }}</p>
    }
  `,
})
export class GlassCheckbox extends FormControlBase<boolean> {
  readonly error = input<string | null>(null);
  protected readonly id = uniqueId('cp-checkbox');
}
