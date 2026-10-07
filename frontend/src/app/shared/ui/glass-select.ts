import { ChangeDetectionStrategy, Component, computed, forwardRef, input } from '@angular/core';
import { NG_VALUE_ACCESSOR } from '@angular/forms';
import { LucideChevronDown } from '@icons';
import { FIELD_CLASSES, FormControlBase, uniqueId } from './form-control';

export interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

/** Selector nativo con estilo de vidrio: conserva el teclado y los lectores de pantalla. */
@Component({
  selector: 'cp-glass-select',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [LucideChevronDown],
  providers: [
    { provide: NG_VALUE_ACCESSOR, useExisting: forwardRef(() => GlassSelect), multi: true },
  ],
  host: { class: 'block' },
  template: `
    <label [for]="id" class="mb-1.5 block text-sm font-medium">{{ label() }}</label>
    <div class="relative">
      <select
        [id]="id"
        [class]="fieldClasses()"
        [disabled]="disabled()"
        [attr.aria-invalid]="error() ? true : null"
        [attr.aria-describedby]="error() ? id + '-error' : null"
        (change)="update($any($event.target).value)"
        (blur)="onTouched()"
      >
        @if (placeholder()) {
          <option value="" disabled [selected]="!value()">{{ placeholder() }}</option>
        }
        @for (option of options(); track option.value) {
          <option
            [value]="option.value"
            [disabled]="option.disabled"
            [selected]="option.value === value()"
          >
            {{ option.label }}
          </option>
        }
      </select>
      <svg
        lucideChevronDown
        class="pointer-events-none absolute top-1/2 right-3.5 size-5 -translate-y-1/2 text-muted"
        aria-hidden="true"
      ></svg>
    </div>
    @if (error()) {
      <p [id]="id + '-error'" class="mt-1.5 text-sm text-danger">{{ error() }}</p>
    }
  `,
})
export class GlassSelect extends FormControlBase<string> {
  readonly label = input.required<string>();
  readonly options = input.required<SelectOption[]>();
  readonly placeholder = input<string | null>(null);
  readonly error = input<string | null>(null);

  protected readonly id = uniqueId('cp-select');
  protected readonly fieldClasses = computed(
    () => `${FIELD_CLASSES} appearance-none pr-11 ${this.error() ? '!border-danger' : ''}`,
  );
}
