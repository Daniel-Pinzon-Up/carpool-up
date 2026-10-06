import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

/**
 * Proporcion contra un tope (ocupacion, estrellas sobre 5): barra del mismo tono sobre una
 * pista tenue del mismo tono. El valor va en texto al lado, nunca solo en el color.
 */
@Component({
  selector: 'cp-meter',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { class: 'block' },
  template: `
    <div class="flex items-baseline justify-between gap-3 text-sm">
      <span>{{ label() }}</span>
      <span class="font-semibold">{{ display() }}</span>
    </div>
    <div
      class="mt-1 h-2 w-full overflow-hidden rounded-full bg-chart/20"
      role="meter"
      [attr.aria-label]="label()"
      [attr.aria-valuenow]="value() ?? 0"
      aria-valuemin="0"
      [attr.aria-valuemax]="max()"
      [attr.aria-valuetext]="display()"
    >
      <div class="h-full rounded-full bg-chart" [style.width.%]="percent()"></div>
    </div>
  `,
})
export class Meter {
  readonly label = input.required<string>();
  readonly value = input.required<number | null>();
  readonly max = input(1);
  readonly display = input.required<string>();

  protected readonly percent = computed(() => {
    const value = this.value();
    return value === null ? 0 : Math.max(0, Math.min(100, (value / this.max()) * 100));
  });
}
