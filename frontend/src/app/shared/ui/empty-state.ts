import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { LucideDynamicIcon, LucideIcon, LucideInbox } from '@icons';

/** Estado vacio con explicacion y una accion principal opcional (contenido proyectado). */
@Component({
  selector: 'cp-empty-state',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [LucideDynamicIcon],
  host: { class: 'flex flex-col items-center gap-3 px-6 py-10 text-center' },
  template: `
    @if (image(); as src) {
      <img [src]="src" alt="" width="480" height="350" class="h-28 w-auto" loading="lazy" />
    } @else {
      <span class="grid size-16 place-items-center rounded-full bg-primary/15">
        <svg [lucideIcon]="icon()" class="size-8 text-primary" aria-hidden="true"></svg>
      </span>
    }
    <h3 class="text-lg font-bold">{{ title() }}</h3>
    @if (description()) {
      <p class="max-w-sm text-muted">{{ description() }}</p>
    }
    <div class="mt-2"><ng-content /></div>
  `,
})
export class EmptyState {
  readonly title = input.required<string>();
  readonly description = input<string | null>(null);
  readonly icon = input<LucideIcon>(LucideInbox);
  /** Ilustracion decorativa en lugar del icono (ruta dentro de public). */
  readonly image = input<string | null>(null);
}
