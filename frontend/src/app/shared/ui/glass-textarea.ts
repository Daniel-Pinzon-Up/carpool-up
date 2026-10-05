import { ChangeDetectionStrategy, Component, computed, forwardRef, input } from '@angular/core';
import { NG_VALUE_ACCESSOR } from '@angular/forms';
import { FIELD_CLASSES, FormControlBase, uniqueId } from './form-control';

/** Texto de varias lineas con contador visible y anunciado. */
@Component({
  selector: 'cp-glass-textarea',
  changeDetection: ChangeDetectionStrategy.OnPush,
  providers: [
    { provide: NG_VALUE_ACCESSOR, useExisting: forwardRef(() => GlassTextarea), multi: true },
  ],
  host: { class: 'block' },
  template: `
    <label [for]="id" class="mb-1.5 block text-sm font-medium">{{ label() }}</label>
    <textarea
      [id]="id"
      [rows]="rows()"
      [class]="classes()"
      [value]="value() ?? ''"
      [disabled]="disabled()"
      [attr.maxlength]="maxlength()"
      [attr.aria-invalid]="error() ? true : null"
      [attr.aria-describedby]="id + '-meta'"
      (input)="update($any($event.target).value)"
      (blur)="onTouched()"
    ></textarea>
    <div [id]="id + '-meta'" class="mt-1.5 flex justify-between gap-3 text-sm">
      <span [class]="error() ? 'text-danger' : 'text-muted'">{{ error() ?? hint() }}</span>
      <span class="shrink-0 text-muted">{{ (value() ?? '').length }}/{{ maxlength() }}</span>
    </div>
  `,
})
export class GlassTextarea extends FormControlBase<string> {
  readonly label = input.required<string>();
  readonly hint = input('');
  readonly error = input<string | null>(null);
  readonly rows = input(4);
  readonly maxlength = input(300);

  protected readonly id = uniqueId('cp-textarea');
  protected readonly classes = computed(
    () => `${FIELD_CLASSES} !min-h-24 resize-y ${this.error() ? '!border-danger' : ''}`,
  );
}
