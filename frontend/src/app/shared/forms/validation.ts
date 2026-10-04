import { AbstractControl, ValidationErrors, ValidatorFn } from '@angular/forms';
import { TranslocoService } from '@jsverse/transloco';

/** El correo debe terminar en el sufijo institucional configurado (por defecto .edu.co). */
export function institutionalEmail(suffix: () => string): ValidatorFn {
  return (control: AbstractControl): ValidationErrors | null => {
    const value = String(control.value ?? '')
      .trim()
      .toLowerCase();
    if (!value) return null;
    return value.endsWith(suffix().toLowerCase()) ? null : { institutional: { suffix: suffix() } };
  };
}

/** Longitud minima leida de los parametros publicos en el momento de validar. */
export function dynamicMinLength(min: () => number): ValidatorFn {
  return (control: AbstractControl): ValidationErrors | null => {
    const value = String(control.value ?? '');
    return value && value.length < min() ? { minlength: { requiredLength: min() } } : null;
  };
}

/** Valida en el grupo que dos campos coincidan; el error queda en el segundo. */
export function matchFields(field: string, confirmation: string): ValidatorFn {
  return (group: AbstractControl): ValidationErrors | null => {
    const confirm = group.get(confirmation);
    if (!confirm) return null;
    const mismatch = group.get(field)?.value !== confirm.value && !!confirm.value;
    const others = { ...(confirm.errors ?? {}) };
    delete others['mismatch'];
    confirm.setErrors(
      mismatch ? { ...others, mismatch: true } : Object.keys(others).length ? others : null,
    );
    return null;
  };
}

/** Primer error del campo traducido; solo cuando el usuario ya interactuo o intento enviar. */
export function fieldError(
  transloco: TranslocoService,
  control: AbstractControl | null,
  submitted: boolean,
): string | null {
  if (!control || !control.errors || !(control.touched || submitted)) return null;
  const errors = control.errors;
  if (errors['required']) return transloco.translate('form.required');
  if (errors['email']) return transloco.translate('form.email');
  if (errors['institutional'])
    return transloco.translate('form.institutional', errors['institutional']);
  if (errors['minlength'])
    return transloco.translate('form.minLength', { min: errors['minlength'].requiredLength });
  if (errors['maxlength'])
    return transloco.translate('form.maxLength', { max: errors['maxlength'].requiredLength });
  if (errors['mismatch']) return transloco.translate('form.passwordMismatch');
  if (errors['pattern']) return transloco.translate('form.code');
  return transloco.translate('form.invalid');
}
