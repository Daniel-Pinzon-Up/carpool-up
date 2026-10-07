import { ChangeDetectionStrategy, Component, input, model } from '@angular/core';
import { LucideCheck, LucideDynamicIcon, LucideIcon } from '@icons';

/** Chip conmutable para filtros y preferencias. Usa aria-pressed. */
@Component({
  selector: 'cp-glass-chip',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [LucideDynamicIcon, LucideCheck],
  template: `
    <button
      type="button"
      [attr.aria-pressed]="selected()"
      [disabled]="disabled()"
      (click)="selected.set(!selected())"
      class="inline-flex min-h-11 items-center gap-2 rounded-full border px-4 text-sm font-medium transition duration-200 disabled:opacity-50"
      [class]="
        selected()
          ? 'border-accent bg-accent/15 text-text'
          : 'border-glass-border bg-glass text-text hover:bg-glass-strong'
      "
    >
      @if (selected()) {
        <svg lucideCheck class="size-4 text-accent" aria-hidden="true"></svg>
      } @else if (icon(); as chipIcon) {
        <svg [lucideIcon]="chipIcon" class="size-4 text-muted" aria-hidden="true"></svg>
      }
      <ng-content />
    </button>
  `,
})
export class GlassChip {
  readonly selected = model(false);
  readonly disabled = input(false);
  readonly icon = input<LucideIcon | null>(null);
}
