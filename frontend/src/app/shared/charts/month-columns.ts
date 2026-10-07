import { ChangeDetectionStrategy, Component, computed, input, signal } from '@angular/core';
import { TranslocoPipe } from '@jsverse/transloco';

export interface MonthValue {
  /** Etiqueta corta del eje (por ejemplo "oct"). */
  label: string;
  /** Mes completo para el tooltip y la tabla ("octubre de 2026"). */
  title: string;
  value: number;
  /** Valor ya formateado (moneda, unidades). */
  display: string;
}

/**
 * Columnas por mes de una sola serie (un tono, magnitud). Columnas de 24 px como minimo
 * con extremo redondeado y base recta, sin cuadricula; el maximo lleva etiqueta directa
 * y cada columna muestra su valor al pasar o al recibir foco. La tabla da el detalle sin
 * depender del color ni del mouse.
 */
@Component({
  selector: 'cp-month-columns',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [TranslocoPipe],
  host: { class: 'block' },
  template: `
    <figure class="flex flex-col gap-2">
      <figcaption class="text-sm font-semibold">{{ title() }}</figcaption>
      <!-- Cada columna mide al menos 24 px (WCAG 2.2, tamano de objetivo); si no caben,
           el grafico se desplaza en horizontal en lugar de encoger las columnas. -->
      <div class="overflow-x-auto" (pointerleave)="active.set(null)">
        <div class="relative" [style.min-width.px]="items().length * 26">
          @if (activeItem(); as item) {
            <div
              class="pointer-events-none absolute top-0 z-10 -translate-x-1/2 rounded-lg bg-[var(--surface-2-solid)] px-2 py-1 text-xs whitespace-nowrap shadow-md"
              [style.left.%]="activeLeft()"
              role="status"
            >
              <span class="font-semibold text-text">{{ item.display }}</span>
              <span class="text-muted"> · {{ item.title }}</span>
            </div>
          }
          <div class="flex h-44 items-end gap-0.5 border-b border-glass-border pt-10">
            @for (item of items(); track item.title; let i = $index) {
              <button
                type="button"
                class="group flex h-full min-w-6 flex-1 flex-col items-center justify-end focus-visible:outline-2 focus-visible:outline-primary"
                [attr.aria-label]="item.title + ': ' + item.display"
                (pointerenter)="active.set(i)"
                (focus)="active.set(i)"
                (blur)="active.set(null)"
              >
                @if (i === peak() && item.value > 0) {
                  <span class="mb-1 text-[0.7rem] font-semibold text-text">{{ item.display }}</span>
                }
                <span
                  class="block w-full max-w-6 rounded-t bg-chart transition-opacity"
                  [class.opacity-60]="active() !== null && active() !== i"
                  [style.height.%]="height(item.value)"
                  [style.min-height.px]="item.value > 0 ? 2 : 0"
                ></span>
              </button>
            }
          </div>
          <div class="mt-1 flex gap-0.5" aria-hidden="true">
            @for (item of items(); track item.title; let i = $index) {
              <span class="min-w-6 flex-1 truncate text-center text-[0.65rem] text-muted">
                {{ i % 2 === items().length % 2 ? item.label : '' }}
              </span>
            }
          </div>
        </div>
      </div>
      <details class="text-sm">
        <summary class="cursor-pointer text-primary">{{ 'charts.table' | transloco }}</summary>
        <table class="mt-2 w-full text-left">
          <thead>
            <tr class="text-muted">
              <th scope="col" class="py-1 font-medium">
                {{ keyLabel() ?? ('charts.month' | transloco) }}
              </th>
              <th scope="col" class="py-1 text-right font-medium">{{ valueLabel() }}</th>
            </tr>
          </thead>
          <tbody>
            @for (item of items(); track item.title) {
              <tr class="border-t border-glass-border">
                <th scope="row" class="py-1 font-normal">{{ item.title }}</th>
                <td class="py-1 text-right">{{ item.display }}</td>
              </tr>
            }
          </tbody>
        </table>
      </details>
    </figure>
  `,
})
export class MonthColumns {
  readonly title = input.required<string>();
  readonly valueLabel = input.required<string>();
  /** Encabezado de la primera columna de la tabla (por defecto, Mes). */
  readonly keyLabel = input<string | null>(null);
  readonly items = input.required<MonthValue[]>();

  protected readonly active = signal<number | null>(null);
  private readonly max = computed(() => Math.max(0, ...this.items().map((i) => i.value)));
  /** Solo el maximo lleva etiqueta directa (la del ultimo si hay empate). */
  protected readonly peak = computed(() => {
    const max = this.max();
    return this.items()
      .map((i) => i.value)
      .lastIndexOf(max);
  });
  protected readonly activeItem = computed(() => {
    const index = this.active();
    return index === null ? null : this.items()[index];
  });
  protected readonly activeLeft = computed(() => {
    const index = this.active() ?? 0;
    const center = ((index + 0.5) / Math.max(1, this.items().length)) * 100;
    // El globo se centra en la columna, sin salirse por los bordes del grafico.
    return Math.min(85, Math.max(15, center));
  });

  protected height(value: number): number {
    const max = this.max();
    return max > 0 ? (value / max) * 100 : 0;
  }
}
