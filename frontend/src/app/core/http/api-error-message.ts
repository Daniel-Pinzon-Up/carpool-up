import { TranslocoService } from '@jsverse/transloco';
import { ApiError, errorKey } from './api-error';

function asApiError(error: unknown): ApiError {
  if (error && typeof error === 'object' && 'code' in error) {
    const candidate = error as Partial<ApiError>;
    return {
      code: String(candidate.code),
      message: candidate.message ?? '',
      details: candidate.details ?? {},
    };
  }
  return { code: 'UNKNOWN_ERROR', message: String(error), details: {} };
}

/** Parametros que los textos de error pueden mostrar ({{minutes}}, {{min_length}}...). */
function params(details: Record<string, unknown>): Record<string, unknown> {
  const result: Record<string, unknown> = { ...details };
  const seconds = Number(details['retry_after_seconds']);
  if (Number.isFinite(seconds)) {
    result['seconds'] = Math.max(1, Math.ceil(seconds));
    result['minutes'] = Math.max(1, Math.ceil(seconds / 60));
  }
  return result;
}

/** Mensaje traducido para cualquier error de la API; nunca muestra textos tecnicos. */
export function apiErrorMessage(transloco: TranslocoService, error: unknown): string {
  const apiError = asApiError(error);
  const key = errorKey(apiError.code);
  const message = transloco.translate(key, params(apiError.details));
  return message === key ? transloco.translate('errors.UNKNOWN_ERROR') : message;
}

export function apiErrorCode(error: unknown): string {
  return asApiError(error).code;
}
