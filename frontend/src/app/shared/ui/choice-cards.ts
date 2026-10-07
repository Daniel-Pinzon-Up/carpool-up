import { ChangeDetectionStrategy, Component, forwardRef, input } from '@angular/core';
import { NG_VALUE_ACCESSOR } from '@angular/forms';
import { LucideCircleCheck, LucideDynamicIcon, LucideIcon } from '@icons';
import { FormControlBase, uniqueId } from './form-control';

export interface Choice {
  value: string;
  title: string;
  description: string;
  icon: LucideIcon;
}

/** Grupo de opciones grandes (radio) para decisiones importantes, como el rol. */
@Component({
  selector: 'cp-choice-cards',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [LucideDynamicIcon, LucideCircleCheck],
  providers: [
    { provide: NG_VALUE_ACCESSOR, useExisting: forwardRef(() => ChoiceCards), multi: true },
  ],
  host: { class: 'block' },
  template: `
    <fieldset>
      <legend class="mb-2 text-sm font-medium">{{ label() }}</legend>
      <div class="grid gap-3" [class.sm:grid-cols-2]="choices().length > 1">
        @for (choice of choices(); track choice.value) {
          <label
            class="glass-1 !rounded-2xl relative flex cursor-pointer gap-3 p-4 transition focus-within:outline-3 focus-within:outline-offset-2 focus-within:outline-[var(--focus-ring)]"
            [class]="
              value() === choice.value
                ? '!border-accent ring-2 ring-accent'
                : 'hover:bg-glass-strong'
            "
          >
            <input
              type="radio"
              class="sr-only"
              [name]="name"
              [value]="choice.value"
              [checked]="value() === choice.value"
              [disabled]="disabled()"
              (change)="update(choice.value)"
              (blur)="onTouched()"
            />
            <span class="grid size-11 shrink-0 place-items-center rounded-xl bg-primary/15">
              <svg [lucideIcon]="choice.icon" class="size-6 text-primary" aria-hidden="true"></svg>
            </span>
            <span class="min-w-0 flex-1">
              <span class="block font-semibold">{{ choice.title }}</span>
              <span class="block text-sm text-muted">{{ choice.description }}</span>
            </span>
            @if (value() === choice.value) {
              <svg lucideCircleCheck class="size-5 shrink-0 text-accent" aria-hidden="true"></svg>
            }
          </label>
        }
      </div>
      @if (error()) {
        <p class="mt-1.5 text-sm text-danger" role="alert">{{ error() }}</p>
      }
    </fieldset>
  `,
})
export class ChoiceCards extends FormControlBase<string> {
  readonly label = input.required<string>();
  readonly choices = input.required<Choice[]>();
  readonly error = input<string | null>(null);
  protected readonly name = uniqueId('cp-choice');
}
