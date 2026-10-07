import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { TranslocoPipe } from '@jsverse/transloco';
import { LucideCheck } from '@lucide/angular';

/** Indicador de progreso de un asistente en pasos. current es base 0. */
@Component({
  selector: 'cp-stepper',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [LucideCheck, TranslocoPipe],
  host: { class: 'block' },
  template: `
    <ol class="flex items-center gap-2" [attr.aria-label]="'ui.stepper.label' | transloco">
      @for (step of steps(); track $index; let i = $index, last = $last) {
        <li
          class="flex flex-1 items-center gap-2 last:flex-none"
          [attr.aria-current]="i === current() ? 'step' : null"
        >
          <span
            class="grid size-9 shrink-0 place-items-center rounded-full text-sm font-bold transition"
            [class]="
              i < current()
                ? 'bg-accent text-on-accent'
                : i === current()
                  ? 'bg-primary text-on-primary ring-4 ring-primary/25'
                  : 'border border-glass-border bg-glass text-muted'
            "
          >
            @if (i < current()) {
              <svg lucideCheck class="size-4" aria-hidden="true"></svg>
              <span class="sr-only">{{ 'ui.stepper.done' | transloco }}</span>
            } @else {
              {{ i + 1 }}
            }
          </span>
          <span class="hidden text-sm font-medium md:inline" [class.text-muted]="i !== current()">{{
            step
          }}</span>
          @if (!last) {
            <span
              class="h-0.5 flex-1 rounded-full"
              [class]="i < current() ? 'bg-accent' : 'bg-glass-border'"
              aria-hidden="true"
            ></span>
          }
        </li>
      }
    </ol>
    <p class="mt-2 text-sm text-muted md:hidden">
      {{ 'ui.stepper.progress' | transloco: { current: current() + 1, total: steps().length } }}:
      <span class="font-semibold text-text">{{ steps()[current()] }}</span>
    </p>
  `,
})
export class Stepper {
  readonly steps = input.required<string[]>();
  readonly current = input(0);
}
