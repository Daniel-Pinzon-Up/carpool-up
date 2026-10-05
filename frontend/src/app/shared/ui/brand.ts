import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { TranslocoPipe } from '@jsverse/transloco';

/**
 * Marca de Carpool UP: el logo y, si cabe, el nombre. Con wordmark muestra el nombre
 * dibujado (imagen con texto alternativo) en lugar del texto.
 */
@Component({
  selector: 'cp-brand',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [TranslocoPipe],
  host: { class: 'inline-flex items-center gap-2' },
  template: `
    <img
      src="brand/logo-small.webp"
      [width]="size()"
      [height]="size()"
      class="shrink-0 object-contain"
      [style.width.px]="size()"
      [style.height.px]="size()"
      [alt]="showName() || wordmark() ? '' : ('app.name' | transloco)"
    />
    @if (wordmark()) {
      <img
        src="brand/wordmark.webp"
        width="480"
        height="278"
        class="h-10 w-auto"
        [alt]="'app.name' | transloco"
      />
    } @else if (showName()) {
      <span class="text-lg leading-tight font-bold">{{ 'app.name' | transloco }}</span>
    }
  `,
})
export class Brand {
  readonly size = input(40);
  readonly showName = input(true);
  readonly wordmark = input(false);
}
