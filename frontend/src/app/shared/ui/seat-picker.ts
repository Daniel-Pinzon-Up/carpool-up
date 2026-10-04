import { ChangeDetectionStrategy, Component, computed, forwardRef, input } from '@angular/core';
import { NG_VALUE_ACCESSOR } from '@angular/forms';
import { TranslocoPipe } from '@jsverse/transloco';
import { LucideMinus, LucidePlus } from '@lucide/angular';
import { FormControlBase, uniqueId } from './form-control';

/** Selector de puestos con botones grandes. El rango lo dicta la capacidad del vehiculo. */
@Component({
  selector: 'cp-seat-picker',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [LucideMinus, LucidePlus, TranslocoPipe],
  providers: [
    { provide: NG_VALUE_ACCESSOR, useExisting: forwardRef(() => SeatPicker), multi: true },
  ],
  host: { class: 'block' },
  template: `
    <span [id]="labelId" class="mb-1.5 block text-sm font-medium">{{ label() }}</span>
    <div
      class="glass-1 !rounded-full inline-flex items-center gap-2 p-1"
      role="group"
      [attr.aria-labelledby]="labelId"
    >
      <button
        type="button"
        class="grid size-11 place-items-center rounded-full transition hover:bg-glass-strong disabled:opacity-40"
        [disabled]="disabled() || current() <= min()"
        [attr.aria-label]="'ui.seats.decrease' | transloco"
        (click)="change(-1)"
      >
        <svg lucideMinus class="size-5" aria-hidden="true"></svg>
      </button>
      <output class="min-w-10 text-center text-lg font-bold" aria-live="polite">{{
        current()
      }}</output>
      <button
        type="button"
        class="grid size-11 place-items-center rounded-full transition hover:bg-glass-strong disabled:opacity-40"
        [disabled]="disabled() || current() >= max()"
        [attr.aria-label]="'ui.seats.increase' | transloco"
        (click)="change(1)"
      >
        <svg lucidePlus class="size-5" aria-hidden="true"></svg>
      </button>
    </div>
    <p class="mt-1.5 text-sm text-muted">
      {{ 'ui.seats.range' | transloco: { min: min(), max: max() } }}
    </p>
  `,
})
export class SeatPicker extends FormControlBase<number> {
  readonly label = input.required<string>();
  readonly min = input(1);
  readonly max = input(4);

  protected readonly labelId = uniqueId('cp-seats');
  protected readonly current = computed(() => this.value() ?? this.min());

  protected change(delta: number): void {
    const next = Math.min(this.max(), Math.max(this.min(), this.current() + delta));
    this.update(next);
    this.onTouched();
  }
}
