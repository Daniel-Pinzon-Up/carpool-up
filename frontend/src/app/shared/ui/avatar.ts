import { ChangeDetectionStrategy, Component, computed, input, signal } from '@angular/core';

const SIZES = { sm: 'size-9 text-xs', md: 'size-12 text-sm', lg: 'size-20 text-xl' } as const;

/** Foto de perfil o iniciales si no hay foto o falla la carga. */
@Component({
  selector: 'cp-avatar',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { class: 'inline-block shrink-0' },
  template: `
    @if (src() && !failed()) {
      <img
        [src]="src()"
        [alt]="name()"
        (error)="failed.set(true)"
        [class]="sizeClass() + ' rounded-full object-cover ring-2 ring-glass-border'"
      />
    } @else {
      <span
        role="img"
        [attr.aria-label]="name()"
        [class]="
          sizeClass() +
          ' grid place-items-center rounded-full bg-primary/20 font-bold text-text ring-2 ring-glass-border'
        "
      >
        <span aria-hidden="true">{{ initials() }}</span>
      </span>
    }
  `,
})
export class Avatar {
  readonly name = input.required<string>();
  readonly src = input<string | null>(null);
  readonly size = input<keyof typeof SIZES>('md');

  protected readonly failed = signal(false);
  protected readonly sizeClass = computed(() => SIZES[this.size()]);
  protected readonly initials = computed(() =>
    this.name()
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase())
      .join(''),
  );
}
