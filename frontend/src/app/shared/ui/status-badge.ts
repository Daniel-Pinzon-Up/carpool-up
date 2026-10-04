import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import {
  LucideCircleAlert,
  LucideCircleCheck,
  LucideCircleDot,
  LucideClock,
  LucideDynamicIcon,
  LucideIcon,
  LucideTriangleAlert,
} from '@lucide/angular';

export type BadgeTone = 'neutral' | 'info' | 'success' | 'warning' | 'danger' | 'pending';

const TONES: Record<BadgeTone, { icon: LucideIcon; classes: string }> = {
  neutral: { icon: LucideCircleDot, classes: 'bg-muted/15 text-text' },
  info: { icon: LucideCircleDot, classes: 'bg-primary/15 text-primary' },
  success: { icon: LucideCircleCheck, classes: 'bg-success/15 text-success' },
  warning: { icon: LucideTriangleAlert, classes: 'bg-warning/15 text-warning' },
  danger: { icon: LucideCircleAlert, classes: 'bg-danger/15 text-danger' },
  pending: { icon: LucideClock, classes: 'bg-primary/15 text-primary' },
};

/** Estado con icono y texto: nunca depende solo del color. */
@Component({
  selector: 'cp-status-badge',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [LucideDynamicIcon],
  host: {
    '[class]':
      'tone().classes + " inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold"',
  },
  template: `
    <svg [lucideIcon]="tone().icon" class="size-3.5" aria-hidden="true"></svg>
    <ng-content />
  `,
})
export class StatusBadge {
  readonly variant = input<BadgeTone>('neutral');
  protected readonly tone = computed(() => TONES[this.variant()]);
}
