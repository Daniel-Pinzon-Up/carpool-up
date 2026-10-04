import { signal } from '@angular/core';
import { ControlValueAccessor } from '@angular/forms';

let nextId = 0;

/** Identificador unico para enlazar label, ayuda y error con aria-describedby. */
export function uniqueId(prefix: string): string {
  nextId += 1;
  return `${prefix}-${nextId}`;
}

/** Base comun para controles con formularios reactivos. */
export abstract class FormControlBase<T> implements ControlValueAccessor {
  protected readonly value = signal<T | null>(null);
  protected readonly disabled = signal(false);
  private onChange: (value: T | null) => void = () => undefined;
  protected onTouched: () => void = () => undefined;

  writeValue(value: T | null): void {
    this.value.set(value);
  }

  registerOnChange(fn: (value: T | null) => void): void {
    this.onChange = fn;
  }

  registerOnTouched(fn: () => void): void {
    this.onTouched = fn;
  }

  setDisabledState(isDisabled: boolean): void {
    this.disabled.set(isDisabled);
  }

  protected update(value: T | null): void {
    this.value.set(value);
    this.onChange(value);
  }
}

export const FIELD_CLASSES =
  'glass-1 !rounded-2xl w-full min-h-11 px-4 py-2.5 text-text placeholder:text-muted ' +
  'transition focus:outline-none focus-visible:outline-3 focus-visible:outline-offset-2 ' +
  'disabled:opacity-60 disabled:cursor-not-allowed';
