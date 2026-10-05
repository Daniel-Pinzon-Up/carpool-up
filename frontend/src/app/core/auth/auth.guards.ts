import { inject } from '@angular/core';
import { CanActivateFn, CanMatchFn, Router, UrlTree } from '@angular/router';
import { readPref } from '../storage/local-preferences';
import { UserRole } from './auth.models';
import { AuthService } from './auth.service';

export const ONBOARDED_KEY = 'cp.onboarded';

const HOME_BY_ROLE: Record<UserRole, string> = {
  passenger: '/buscar',
  driver: '/inicio',
  admin: '/admin',
  superadmin: '/admin',
};

/** A donde va cada quien segun su estado: el unico lugar con esta decision. */
export function homeFor(auth: AuthService, router: Router): UrlTree {
  const user = auth.user();
  if (!user) {
    return router.parseUrl(readPref(ONBOARDED_KEY) === 'true' ? '/ingresar' : '/bienvenida');
  }
  if (user.pending_legal.length > 0) return router.parseUrl('/cuenta/terminos');
  if (user.status !== 'active') return router.parseUrl('/cuenta/estado');
  return router.parseUrl(HOME_BY_ROLE[user.role]);
}

/** Ruta raiz: redirige siempre. */
export const homeRedirect: CanActivateFn = () => homeFor(inject(AuthService), inject(Router));

/**
 * Pantallas de acceso: solo sin sesion. Con sesion devuelve false (no redirige): el grupo
 * tiene path '' y se evalua en cada navegacion, asi que redirigir a casa volveria a pasar
 * por aqui sin fin. Sin coincidencia, la URL cae en '**' -> '' -> homeRedirect.
 */
export const guestGuard: CanMatchFn = () => !inject(AuthService).isAuthenticated();

/** Cualquier sesion, incluso pendiente o suspendida (estado de cuenta, terminos). */
export const signedInGuard: CanMatchFn = () =>
  inject(AuthService).isAuthenticated() || inject(Router).parseUrl('/ingresar');

/** App completa: cuenta activa y terminos vigentes aceptados. */
export const activeGuard: CanMatchFn = () => {
  const auth = inject(AuthService);
  return (auth.isActive() && !auth.needsLegal()) || homeFor(auth, inject(Router));
};

/** Publicar exige licencia aprobada y vigente y un vehiculo activo; si no, al inicio. */
export const canPublishGuard: CanMatchFn = () =>
  inject(AuthService).user()?.can_publish === true || inject(Router).parseUrl('/inicio');

/**
 * Restringe una seccion a ciertos roles (se usa junto con activeGuard). Devuelve false en
 * lugar de redirigir: la misma ruta puede existir para otro rol mas abajo (Mis viajes del
 * conductor y del pasajero). Si ninguna coincide, '**' lleva a casa.
 */
export function roleGuard(...roles: UserRole[]): CanMatchFn {
  return () => {
    const role = inject(AuthService).user()?.role;
    return role !== undefined && roles.includes(role);
  };
}
