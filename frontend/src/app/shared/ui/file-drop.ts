import {
  ChangeDetectionStrategy,
  Component,
  computed,
  forwardRef,
  input,
  signal,
} from '@angular/core';
import { NG_VALUE_ACCESSOR } from '@angular/forms';
import { TranslocoPipe } from '@jsverse/transloco';
import { LucideFileCheck, LucideUpload, LucideX } from '@lucide/angular';
import { FormControlBase, uniqueId } from './form-control';

export const DOCUMENT_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'application/pdf'];

/**
 * Seleccion de archivo por clic, teclado o arrastrar y soltar.
 * Valida tipo y tamano antes de enviar; el servidor vuelve a validar por contenido.
 */
@Component({
  selector: 'cp-file-drop',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [TranslocoPipe, LucideUpload, LucideFileCheck, LucideX],
  providers: [{ provide: NG_VALUE_ACCESSOR, useExisting: forwardRef(() => FileDrop), multi: true }],
  host: { class: 'block' },
  template: `
    <span [id]="id + '-label'" class="mb-1.5 block text-sm font-medium">{{ label() }}</span>
    @if (value(); as file) {
      <div class="glass-1 !rounded-2xl flex items-center gap-3 p-4">
        <span class="grid size-11 shrink-0 place-items-center rounded-xl bg-accent/15">
          <svg lucideFileCheck class="size-6 text-accent" aria-hidden="true"></svg>
        </span>
        <div class="min-w-0 flex-1">
          <p class="truncate font-medium">{{ file.name }}</p>
          <p class="text-sm text-muted">{{ sizeLabel(file.size) }}</p>
        </div>
        <button
          type="button"
          class="grid size-11 place-items-center rounded-full text-muted transition hover:bg-glass hover:text-text"
          [attr.aria-label]="'ui.file.remove' | transloco: { name: file.name }"
          [disabled]="disabled()"
          (click)="clear()"
        >
          <svg lucideX class="size-5" aria-hidden="true"></svg>
        </button>
      </div>
    } @else {
      <label
        [for]="id"
        class="flex cursor-pointer flex-col items-center gap-2 rounded-2xl border-2 border-dashed p-6 text-center transition focus-within:outline-3 focus-within:outline-offset-2 focus-within:outline-[var(--focus-ring)]"
        [class]="
          dragging()
            ? 'border-accent bg-accent/10'
            : 'border-glass-border bg-glass hover:bg-glass-strong'
        "
        (dragover)="onDragOver($event)"
        (dragleave)="dragging.set(false)"
        (drop)="onDrop($event)"
      >
        <svg lucideUpload class="size-8 text-primary" aria-hidden="true"></svg>
        <span class="font-semibold">{{ 'ui.file.choose' | transloco }}</span>
        <span class="text-sm text-muted">
          {{ 'ui.file.rules' | transloco: { types: typesLabel(), max: maxMb() } }}
        </span>
        <input
          [id]="id"
          type="file"
          class="sr-only"
          [accept]="accept().join(',')"
          [disabled]="disabled()"
          [attr.aria-labelledby]="id + '-label'"
          [attr.aria-describedby]="shownError() ? id + '-error' : null"
          [attr.aria-invalid]="shownError() ? true : null"
          (change)="onPick($event)"
        />
      </label>
    }
    @if (shownError()) {
      <p [id]="id + '-error'" role="alert" class="mt-1.5 text-sm text-danger">{{ shownError() }}</p>
    }
  `,
})
export class FileDrop extends FormControlBase<File> {
  readonly label = input.required<string>();
  readonly accept = input<string[]>(DOCUMENT_TYPES);
  readonly maxMb = input(5);
  /** Error externo (por ejemplo, el de la API). */
  readonly error = input<string | null>(null);
  /** Textos ya traducidos para los errores locales. */
  readonly typeError = input('');
  readonly sizeError = input('');

  protected readonly id = uniqueId('cp-file');
  protected readonly dragging = signal(false);
  private readonly localError = signal<string | null>(null);
  protected readonly shownError = computed(() => this.localError() ?? this.error());
  protected readonly typesLabel = computed(() =>
    this.accept()
      .map((type) => (type === 'application/pdf' ? 'PDF' : type.split('/')[1].toUpperCase()))
      .map((type) => (type === 'JPEG' ? 'JPG' : type))
      .join(', '),
  );

  protected sizeLabel(bytes: number): string {
    return bytes < 1024 * 1024
      ? `${Math.max(1, Math.round(bytes / 1024))} KB`
      : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  protected onPick(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.select(input.files?.[0] ?? null);
    input.value = '';
  }

  protected onDragOver(event: DragEvent): void {
    event.preventDefault();
    this.dragging.set(true);
  }

  protected onDrop(event: DragEvent): void {
    event.preventDefault();
    this.dragging.set(false);
    if (!this.disabled()) this.select(event.dataTransfer?.files?.[0] ?? null);
  }

  protected clear(): void {
    this.localError.set(null);
    this.update(null);
    this.onTouched();
  }

  select(file: File | null): void {
    this.onTouched();
    if (!file) return;
    if (!this.accept().includes(file.type)) {
      this.localError.set(this.typeError());
      this.update(null);
      return;
    }
    if (file.size > this.maxMb() * 1024 * 1024) {
      this.localError.set(this.sizeError());
      this.update(null);
      return;
    }
    this.localError.set(null);
    this.update(file);
  }
}
