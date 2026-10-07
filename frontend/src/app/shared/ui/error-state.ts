import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';
import { TranslocoPipe } from '@jsverse/transloco';
import { LucideCircleAlert, LucideRotateCcw } from '@lucide/angular';
import { GlassButton } from './glass-button';

/**
 * Estado de error de una carga: dice que fallo, por que (mensaje traducido de la API) y
 * ofrece reintentar. Reemplaza el estado vacio cuando la lista no se pudo cargar, para que un
 * error nunca parezca "no hay datos".
 */
@Component({
  selector: 'cp-error-state',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [TranslocoPipe, GlassButton, LucideCircleAlert, LucideRotateCcw],
  host: { role: 'alert', class: 'flex flex-col items-center gap-3 px-6 py-10 text-center' },
  template: `
    <span class="grid size-16 place-items-center rounded-full bg-danger/15">
      <svg lucideCircleAlert class="size-8 text-danger" aria-hidden="true"></svg>
    </span>
    <h3 class="text-lg font-bold">{{ title() ?? ('ui.loadError.title' | transloco) }}</h3>
    @if (message()) {
      <p class="max-w-sm text-muted">{{ message() }}</p>
    }
    <button cp-button variant="secondary" type="button" class="mt-2" (click)="retry.emit()">
      <svg lucideRotateCcw class="size-4" aria-hidden="true"></svg>
      {{ 'ui.loadError.retry' | transloco }}
    </button>
  `,
})
export class ErrorState {
  /** Mensaje ya traducido (normalmente apiErrorMessage). */
  readonly message = input<string | null>(null);
  readonly title = input<string | null>(null);
  readonly retry = output<void>();
}
