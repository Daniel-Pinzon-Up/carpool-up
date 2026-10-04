import { ChangeDetectionStrategy, Component, input } from '@angular/core';

/** Superficie de vidrio. Nivel 1 para tarjetas, nivel 2 para barras, modales y hojas. */
@Component({
  selector: 'cp-glass-card',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    class: 'block p-5',
    '[class.glass-1]': 'level() === 1',
    '[class.glass-2]': 'level() === 2',
    '[class.glass-interactive]': 'interactive()',
  },
  template: `<ng-content />`,
})
export class GlassCard {
  readonly level = input<1 | 2>(1);
  readonly interactive = input(false);
}
