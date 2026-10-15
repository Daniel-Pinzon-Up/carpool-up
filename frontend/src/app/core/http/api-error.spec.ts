import { HttpErrorResponse } from '@angular/common/http';
import { errorKey, toApiError } from './api-error';

describe('toApiError', () => {
  it('conserva el formato de error de la API', () => {
    const error = new HttpErrorResponse({
      status: 409,
      error: { code: 'TRIP_FULL', message: 'No seats left', details: { available: 0 } },
    });
    expect(toApiError(error)).toEqual({
      code: 'TRIP_FULL',
      message: 'No seats left',
      details: { available: 0 },
      status: 409,
    });
  });

  it('identifica la falta de conexion', () => {
    expect(toApiError(new HttpErrorResponse({ status: 0 })).code).toBe('NETWORK_ERROR');
  });

  it('usa UNKNOWN_ERROR para respuestas sin formato', () => {
    expect(toApiError(new HttpErrorResponse({ status: 502, error: '<html>' })).code).toBe(
      'UNKNOWN_ERROR',
    );
  });

  it('genera la clave de traduccion', () => {
    expect(errorKey('TRIP_FULL')).toBe('errors.TRIP_FULL');
  });
});
