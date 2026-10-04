import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

/** Marcador de carga. Lo anuncia el contenedor con aria-busy; aqui queda oculto. */
@Component({
  selector: 'cp-skeleton',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { 'aria-hidden': 'true', class: 'block' },
  styles: `
    .bar {
      background: linear-gradient(
        90deg,
        color-mix(in srgb, var(--text) 8%, transparent) 25%,
        color-mix(in srgb, var(--text) 16%, transparent) 50%,
        color-mix(in srgb, var(--text) 8%, transparent) 75%
      );
      background-size: 200% 100%;
      animation: cp-shimmer 1.6s linear infinite;
    }
  `,
  template: `
    @if (shape() === 'circle') {
      <div class="bar size-12 rounded-full"></div>
    } @else {
      <div class="flex flex-col gap-2.5">
        @for (line of lineList(); track $index) {
          <div class="bar h-3.5 rounded-full" [style.width]="line"></div>
        }
      </div>
    }
  `,
})
export class Skeleton {
  readonly shape = input<'text' | 'circle'>('text');
  readonly lines = input(3);
  protected readonly lineList = computed(() =>
    Array.from({ length: this.lines() }, (_, i) => (i === this.lines() - 1 ? '60%' : '100%')),
  );
}
