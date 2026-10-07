import { HttpErrorResponse, HttpInterceptorFn, HttpRequest } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, from, switchMap, throwError } from 'rxjs';
import { AuthService, isSessionRejected } from './auth.service';

/** Endpoints de /auth que no deben disparar una renovacion al recibir 401. */
const NO_RETRY = ['/api/v1/auth/login', '/api/v1/auth/refresh', '/api/v1/auth/logout'];

/**
 * Adjunta el token de acceso a /api y, si caduco (401), renueva una vez con la cookie
 * y repite la peticion. Si el servidor rechaza la renovacion, cierra la sesion y va a /ingresar.
 */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  if (!req.url.startsWith('/api/')) return next(req);
  const auth = inject(AuthService);
  const router = inject(Router);

  const withToken = (request: HttpRequest<unknown>) => {
    const token = auth.accessToken();
    return token ? request.clone({ setHeaders: { Authorization: `Bearer ${token}` } }) : request;
  };

  return next(withToken(req)).pipe(
    catchError((error: unknown) => {
      const canRetry =
        error instanceof HttpErrorResponse &&
        error.status === 401 &&
        auth.accessToken() !== null &&
        !NO_RETRY.some((path) => req.url.startsWith(path));
      if (!canRetry) return throwError(() => error);
      return from(auth.refresh()).pipe(
        catchError((refreshError: unknown) => {
          // Solo se cierra la sesion si el servidor la rechazo; un fallo pasajero de la
          // renovacion (sin red, 429, 5xx) deja la sesion y devuelve el error original.
          if (isSessionRejected(refreshError)) {
            auth.clearSession();
            void router.navigate(['/ingresar']);
          }
          return throwError(() => error);
        }),
        switchMap(() => next(withToken(req))),
      );
    }),
  );
};
