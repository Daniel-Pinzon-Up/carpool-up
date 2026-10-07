import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { TranslocoPipe } from '@jsverse/transloco';
import {
  LucideCircleAlert,
  LucideCircleCheck,
  LucideDynamicIcon,
  LucideIcon,
  LucideInfo,
  LucideTriangleAlert,
  LucideX,
} from '@icons';
import { ToastService, ToastTone } from './toast.service';

const TONE_ICONS: Record<ToastTone, LucideIcon> = {
  info: LucideInfo,
  success: LucideCircleCheck,
  warning: LucideTriangleAlert,
  danger: LucideCircleAlert,
};

const TONE_COLORS: Record<ToastTone, string> = {
  info: 'text-primary',
  success: 'text-success',
  warning: 'text-warning',
  danger: 'text-danger',
};

/** Region aria-live para avisos. Se monta una vez en la raiz de la app. */
@Component({
  selector: 'cp-toast-host',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [LucideDynamicIcon, LucideX, TranslocoPipe],
  template: `
    <div
      aria-live="polite"
      aria-atomic="false"
      class="pointer-events-none fixed inset-x-4 bottom-24 z-[1100] flex flex-col items-center gap-2 lg:bottom-6 lg:left-auto lg:items-end"
    >
      @for (toast of service.toasts(); track toast.id) {
        <div
          [attr.role]="toast.tone === 'danger' ? 'alert' : 'status'"
          class="glass-2 pointer-events-auto flex w-full max-w-sm items-start gap-3 !rounded-2xl p-4"
          style="animation: cp-fade-in 200ms ease-out"
        >
          <svg
            [lucideIcon]="icons[toast.tone]"
            [class]="'mt-0.5 size-5 shrink-0 ' + colors[toast.tone]"
            aria-hidden="true"
          ></svg>
          <p class="flex-1 text-sm font-medium">{{ toast.message }}</p>
          <button
            type="button"
            (click)="service.dismiss(toast.id)"
            class="-m-2 grid size-9 shrink-0 place-items-center rounded-full text-muted hover:text-text"
            [attr.aria-label]="'common.close' | transloco"
          >
            <svg lucideX class="size-4" aria-hidden="true"></svg>
          </button>
        </div>
      }
    </div>
  `,
})
export class ToastHost {
  protected readonly service = inject(ToastService);
  protected readonly icons = TONE_ICONS;
  protected readonly colors = TONE_COLORS;
}
