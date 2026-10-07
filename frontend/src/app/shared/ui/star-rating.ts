import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  computed,
  forwardRef,
  input,
  viewChildren,
} from '@angular/core';
import { NG_VALUE_ACCESSOR } from '@angular/forms';
import { TranslocoPipe } from '@jsverse/transloco';
import { LucideStar } from '@icons';
import { FormControlBase, uniqueId } from './form-control';

const STARS = [1, 2, 3, 4, 5] as const;

/**
 * Calificacion de 1 a 5 estrellas.
 * Entrada: grupo de radio con flechas del teclado. Lectura (readonly): imagen con texto alternativo.
 */
@Component({
  selector: 'cp-star-rating',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [LucideStar, TranslocoPipe],
  providers: [
    { provide: NG_VALUE_ACCESSOR, useExisting: forwardRef(() => StarRating), multi: true },
  ],
  host: { class: 'inline-block' },
  template: `
    @if (readonly()) {
      <span
        role="img"
        class="inline-flex items-center gap-0.5"
        [attr.aria-label]="'ui.rating.readLabel' | transloco: { value: display(), max: 5 }"
      >
        @for (star of stars; track star) {
          <svg
            lucideStar
            [class]="
              sizeClass() +
              ' ' +
              (star <= roundedDisplay() ? 'fill-warning text-warning' : 'text-muted/50')
            "
            aria-hidden="true"
          ></svg>
        }
      </span>
    } @else {
      <div role="radiogroup" [attr.aria-labelledby]="labelId" class="flex flex-col gap-1">
        <span [id]="labelId" class="text-sm font-medium">{{ label() }}</span>
        <div class="flex gap-1">
          @for (star of stars; track star; let i = $index) {
            <button
              #starButton
              type="button"
              role="radio"
              [attr.aria-checked]="value() === star"
              [attr.aria-label]="'ui.rating.starLabel' | transloco: { count: star }"
              [tabIndex]="tabIndexFor(star)"
              [disabled]="disabled()"
              (click)="select(star)"
              (keydown)="onKeydown($event, i)"
              class="grid size-11 place-items-center rounded-full transition hover:bg-glass"
            >
              <svg
                lucideStar
                [class]="
                  'size-7 ' + (star <= (value() ?? 0) ? 'fill-warning text-warning' : 'text-muted')
                "
                aria-hidden="true"
              ></svg>
            </button>
          }
        </div>
      </div>
    }
  `,
})
export class StarRating extends FormControlBase<number> {
  readonly label = input('');
  readonly readonly = input(false);
  /** Valor mostrado en modo lectura (puede tener decimales, p. ej. 4.6). */
  readonly display = input(0);
  readonly size = input<'sm' | 'md'>('sm');

  protected readonly stars = STARS;
  protected readonly labelId = uniqueId('cp-rating');
  protected readonly roundedDisplay = computed(() => Math.round(this.display()));
  protected readonly sizeClass = computed(() => (this.size() === 'sm' ? 'size-4' : 'size-5'));
  private readonly buttons = viewChildren<ElementRef<HTMLButtonElement>>('starButton');

  protected tabIndexFor(star: number): number {
    const current = this.value();
    return current ? (current === star ? 0 : -1) : star === 1 ? 0 : -1;
  }

  protected select(star: number): void {
    this.update(star);
    this.onTouched();
  }

  protected onKeydown(event: KeyboardEvent, index: number): void {
    const next: Record<string, number> = {
      ArrowRight: Math.min(index + 1, 4),
      ArrowUp: Math.min(index + 1, 4),
      ArrowLeft: Math.max(index - 1, 0),
      ArrowDown: Math.max(index - 1, 0),
      Home: 0,
      End: 4,
    };
    const target = next[event.key];
    if (target === undefined) return;
    event.preventDefault();
    this.select(STARS[target]);
    this.buttons()[target]?.nativeElement.focus();
  }
}
