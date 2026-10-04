import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { LucideDynamicIcon, LucideIcon, LucideInbox } from '@lucide/angular';

/** Estado vacio con explicacion y una accion principal opcional (contenido proyectado). */
@Component({
  selector: 'cp-empty-state',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [LucideDynamicIcon],
  host: { class: 'flex flex-col items-center gap-3 px-6 py-10 text-center' },
  template: `
    <span class="grid size-16 place-items-center rounded-full bg-primary/15">
      <svg [lucideIcon]="icon()" class="size-8 text-primary" aria-hidden="true"></svg>
    </span>
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
}
