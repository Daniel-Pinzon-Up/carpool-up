import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { TranslocoPipe } from '@jsverse/transloco';
import { LucideDynamicIcon, LucideMonitor, LucideMoon, LucideSun } from '@icons';
import { ThemePreference, ThemeService } from '../../core/theme/theme.service';

const ORDER: ThemePreference[] = ['system', 'light', 'dark'];
const ICONS = { system: LucideMonitor, light: LucideSun, dark: LucideMoon };

/** Boton que rota entre tema del sistema, claro y oscuro. */
@Component({
  selector: 'cp-theme-toggle',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [LucideDynamicIcon, TranslocoPipe],
  template: `
    <button
      type="button"
      (click)="next()"
      class="glass-1 !rounded-full grid size-11 place-items-center text-text transition hover:bg-glass-strong"
      [attr.aria-label]="
        ('layout.theme.label' | transloco) +
        ': ' +
        ('layout.theme.' + theme.preference() | transloco)
      "
      [title]="'layout.theme.' + theme.preference() | transloco"
    >
      <svg [lucideIcon]="icon()" class="size-5" aria-hidden="true"></svg>
    </button>
  `,
})
export class ThemeToggle {
  protected readonly theme = inject(ThemeService);
  protected readonly icon = computed(() => ICONS[this.theme.preference()]);

  protected next(): void {
    const index = ORDER.indexOf(this.theme.preference());
    this.theme.setPreference(ORDER[(index + 1) % ORDER.length]);
  }
}
