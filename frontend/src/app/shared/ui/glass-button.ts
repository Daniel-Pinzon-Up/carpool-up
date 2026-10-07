import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { LucideLoaderCircle } from '@icons';

export type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'ghost';
export type ButtonSize = 'md' | 'lg';

const VARIANTS: Record<ButtonVariant, string> = {
  primary: 'bg-accent text-on-accent shadow-lg hover:brightness-110',
  secondary: 'glass-1 !rounded-full text-text hover:bg-glass-strong',
  danger: 'bg-danger text-on-danger hover:brightness-110',
  ghost: 'text-text hover:bg-glass',
};

/**
 * Boton del sistema. Se aplica sobre <button> o <a> para conservar la semantica nativa:
 * <button cp-button variant="primary">...</button>
 */
@Component({
  selector: 'button[cp-button], a[cp-button]',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [LucideLoaderCircle],
  host: {
    '[class]': 'classes()',
    '[attr.aria-busy]': 'loading() || null',
    '[attr.aria-disabled]': 'loading() || null',
  },
  template: `
    @if (loading()) {
      <svg lucideLoaderCircle class="size-5 animate-spin" aria-hidden="true"></svg>
    }
    <ng-content />
  `,
})
export class GlassButton {
  readonly variant = input<ButtonVariant>('primary');
  readonly size = input<ButtonSize>('md');
  readonly block = input(false);
  readonly loading = input(false);

  protected readonly classes = computed(() =>
    [
      'inline-flex items-center justify-center gap-2 rounded-full font-semibold select-none',
      'transition duration-200 ease-out active:scale-[0.98]',
      'disabled:cursor-not-allowed disabled:opacity-50 aria-disabled:pointer-events-none',
      this.size() === 'lg' ? 'min-h-12 px-6 text-base' : 'min-h-11 px-5 text-sm',
      this.block() ? 'w-full' : '',
      VARIANTS[this.variant()],
    ].join(' '),
  );
}
