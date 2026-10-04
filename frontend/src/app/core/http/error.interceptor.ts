import { HttpInterceptorFn } from '@angular/common/http';
import { catchError, throwError } from 'rxjs';
import { toApiError } from './api-error';

/**
 * Normaliza los errores de la API al formato { code, message, details } para que cada
 * pantalla los traduzca con errorKey(code). No muestra toasts por su cuenta.
 */
export const errorInterceptor: HttpInterceptorFn = (req, next) =>
  next(req).pipe(catchError((error: unknown) => throwError(() => toApiError(error))));
