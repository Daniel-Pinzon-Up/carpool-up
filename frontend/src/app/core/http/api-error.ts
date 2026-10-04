import { HttpErrorResponse } from '@angular/common/http';

/** Formato unico de error de la API: { code, message, details }. */
export interface ApiError {
  code: string;
  message: string;
  details: Record<string, unknown>;
}

export function toApiError(error: unknown): ApiError {
  if (error instanceof HttpErrorResponse) {
    const body = error.error as Partial<ApiError> | null;
    if (body && typeof body.code === 'string') {
      return { code: body.code, message: body.message ?? '', details: body.details ?? {} };
    }
    return {
      code: error.status === 0 ? 'NETWORK_ERROR' : 'UNKNOWN_ERROR',
      message: error.message,
      details: {},
    };
  }
  return { code: 'UNKNOWN_ERROR', message: String(error), details: {} };
}

/** Clave de traduccion para un codigo de error estable. */
export function errorKey(code: string): string {
  return `errors.${code}`;
}
