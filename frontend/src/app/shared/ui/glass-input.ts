import { ChangeDetectionStrategy, Component, computed, forwardRef, input } from '@angular/core';
import { NG_VALUE_ACCESSOR } from '@angular/forms';
import { LucideCircleAlert, LucideDynamicIcon, LucideIcon } from '@lucide/angular';
import { FIELD_CLASSES, FormControlBase, uniqueId } from './form-control';

/** Campo de texto con etiqueta, ayuda y error accesibles. */
@Component({
  selector: 'cp-glass-input',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [LucideDynamicIcon, LucideCircleAlert],
  providers: [
    { provide: NG_VALUE_ACCESSOR, useExisting: forwardRef(() => GlassInput), multi: true },
  ],
  host: { class: 'block' },
  template: `
    <label [for]="id" class="mb-1.5 block text-sm font-medium">
      {{ label() }}
      @if (required()) {
        <span aria-hidden="true" class="text-danger">*</span>
      }
    </label>
    <div class="relative">
      @if (icon(); as leading) {
        <svg
          [lucideIcon]="leading"
          class="pointer-events-none absolute top-1/2 left-3.5 size-5 -translate-y-1/2 text-muted"
          aria-hidden="true"
        ></svg>
      }
      <input
        [id]="id"
        [type]="type()"
        [class]="fieldClasses()"
        [value]="value() ?? ''"
        [placeholder]="placeholder()"
        [disabled]="disabled()"
        [required]="required()"
        [attr.autocomplete]="autocomplete()"
        [attr.inputmode]="inputmode()"
        [attr.aria-invalid]="error() ? true : null"
        [attr.aria-describedby]="describedBy()"
        (input)="update($any($event.target).value)"
        (blur)="onTouched()"
      />
    </div>
    @if (error()) {
      <p [id]="id + '-error'" class="mt-1.5 flex items-center gap-1.5 text-sm text-danger">
        <svg lucideCircleAlert class="size-4 shrink-0" aria-hidden="true"></svg>
        {{ error() }}
      </p>
    } @else if (hint()) {
      <p [id]="id + '-hint'" class="mt-1.5 text-sm text-muted">{{ hint() }}</p>
    }
  `,
})
export class GlassInput extends FormControlBase<string> {
  readonly label = input.required<string>();
  readonly type = input<
    'text' | 'email' | 'password' | 'tel' | 'number' | 'date' | 'time' | 'search'
  >('text');
  readonly placeholder = input('');
  readonly hint = input<string | null>(null);
  readonly error = input<string | null>(null);
  readonly required = input(false);
  readonly autocomplete = input<string | null>(null);
  readonly inputmode = input<string | null>(null);
  readonly icon = input<LucideIcon | null>(null);

  protected readonly id = uniqueId('cp-input');
  protected readonly fieldClasses = computed(
    () => `${FIELD_CLASSES} ${this.icon() ? 'pl-11' : ''} ${this.error() ? '!border-danger' : ''}`,
  );
  protected readonly describedBy = computed(() => {
    if (this.error()) return `${this.id}-error`;
    return this.hint() ? `${this.id}-hint` : null;
  });
}
