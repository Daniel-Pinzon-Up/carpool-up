import { Route, Routes } from '@angular/router';
import {
  activeGuard,
  guestGuard,
  homeRedirect,
  roleGuard,
  signedInGuard,
} from './core/auth/auth.guards';
import { devOnlyGuard } from './core/guards/dev-only.guard';
import { Shell } from './core/layout/shell';

/** Destino aun no construido; cada paso del plan lo reemplaza por su feature con carga diferida. */
const comingSoon = (path: string, section: string, extra: Partial<Route> = {}): Route => ({
  path,
  loadComponent: () => import('./features/placeholder/coming-soon'),
  data: { section },
  title: `nav.${section}`,
  ...extra,
});

const authLayout = () => import('./features/auth/auth-layout');

export const routes: Routes = [
  // La raiz solo decide a donde ir segun la sesion.
  { path: '', pathMatch: 'full', canActivate: [homeRedirect], children: [] },

  // Sin sesion
  {
    path: 'bienvenida',
    canMatch: [guestGuard],
    loadComponent: authLayout,
    children: [
      {
        path: '',
        loadComponent: () => import('./features/auth/onboarding'),
        title: 'onboarding.pageTitle',
      },
    ],
  },
  {
    path: '',
    canMatch: [guestGuard],
    loadComponent: authLayout,
    children: [
      {
        path: 'ingresar',
        loadComponent: () => import('./features/auth/login'),
        title: 'login.title',
      },
      {
        path: 'registro',
        loadComponent: () => import('./features/auth/register'),
        title: 'register.title',
      },
      {
        path: 'verificar',
        loadComponent: () => import('./features/auth/verify-code'),
        title: 'verify.pageTitle',
      },
      {
        path: 'recuperar',
        loadComponent: () => import('./features/auth/forgot-password'),
        title: 'forgot.title',
      },
      {
        path: 'restablecer',
        loadComponent: () => import('./features/auth/reset-password'),
        title: 'reset.title',
      },
    ],
  },

  // Publico para todos
  {
    path: 'legal/:kind',
    loadComponent: () => import('./features/legal/legal-page'),
    title: 'legal.pageTitle',
  },

  // Cualquier sesion, aunque la cuenta no este activa
  {
    path: 'cuenta',
    canMatch: [signedInGuard],
    loadComponent: authLayout,
    children: [
      {
        path: 'estado',
        loadComponent: () => import('./features/account/account-status'),
        title: 'account.pageTitle',
      },
      {
        path: 'terminos',
        loadComponent: () => import('./features/account/accept-terms'),
        title: 'acceptTerms.title',
      },
    ],
  },

  // App completa: cuenta activa
  {
    path: '',
    component: Shell,
    canMatch: [activeGuard],
    children: [
      {
        path: 'perfil',
        loadComponent: () => import('./features/profile/profile'),
        title: 'nav.profile',
      },
      comingSoon('mis-viajes', 'myTrips'),
      comingSoon('mensajes', 'messages'),
      comingSoon('notificaciones', 'notifications'),
      comingSoon('buscar', 'search', { canMatch: [roleGuard('passenger')] }),
      comingSoon('inicio', 'home', { canMatch: [roleGuard('driver')] }),
      comingSoon('publicar', 'publish', { canMatch: [roleGuard('driver')] }),
      {
        path: 'admin',
        canMatch: [roleGuard('admin', 'superadmin')],
        children: [
          comingSoon('', 'dashboard', { pathMatch: 'full' }),
          comingSoon('aprobaciones', 'approvals'),
          comingSoon('usuarios', 'users'),
          comingSoon('viajes', 'trips'),
          comingSoon('emergencias', 'emergencies'),
          comingSoon('configuracion', 'settings', { canMatch: [roleGuard('superadmin')] }),
        ],
      },
    ],
  },

  // Herramienta de desarrollo: no exige sesion
  {
    path: 'catalogo',
    canMatch: [devOnlyGuard],
    loadComponent: () => import('./features/catalog/catalog-page'),
    title: 'nav.catalog',
  },

  { path: '**', redirectTo: '' },
];
