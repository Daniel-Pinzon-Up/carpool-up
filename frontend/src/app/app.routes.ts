import { Routes } from '@angular/router';
import {
  activeGuard,
  canPublishGuard,
  guestGuard,
  homeRedirect,
  roleGuard,
  signedInGuard,
} from './core/auth/auth.guards';
import { devOnlyGuard } from './core/guards/dev-only.guard';
import { Shell } from './core/layout/shell';

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
  {
    // Enlace compartido de un viaje: publico y de solo lectura.
    path: 'compartido/:token',
    loadComponent: () => import('./features/share/shared-trip'),
    title: 'shared.title',
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
      {
        path: 'mis-viajes',
        canMatch: [roleGuard('driver')],
        loadComponent: () => import('./features/trips/driver-trips'),
        title: 'nav.myTrips',
      },
      {
        path: 'mis-viajes',
        canMatch: [roleGuard('passenger')],
        loadComponent: () => import('./features/bookings/passenger-trips'),
        title: 'nav.myTrips',
      },
      {
        path: 'calificar',
        loadComponent: () => import('./features/ratings/rate-page'),
        title: 'ratings.title',
      },
      {
        path: 'calificar/:tripId',
        loadComponent: () => import('./features/ratings/rate-page'),
        title: 'ratings.title',
      },
      {
        path: 'estadisticas',
        canMatch: [roleGuard('driver')],
        loadComponent: () => import('./features/stats/stats-views'),
        title: 'stats.driverTitle',
      },
      {
        path: 'solicitudes',
        canMatch: [roleGuard('driver')],
        loadComponent: () => import('./features/bookings/driver-inbox'),
        title: 'bookings.inbox.title',
      },
      {
        path: 'viajes/:id',
        loadComponent: () => import('./features/trips/trip-detail'),
        title: 'trips.detailTitle',
      },
      {
        path: 'viajes/:id/editar',
        canMatch: [roleGuard('driver')],
        loadComponent: () => import('./features/publish/publish-wizard'),
        data: { mode: 'edit-trip' },
        title: 'publish.editTripTitle',
      },
      {
        path: 'series/:id',
        loadComponent: () => import('./features/trips/series-detail'),
        title: 'trips.seriesTitle',
      },
      {
        path: 'series/:id/editar',
        canMatch: [roleGuard('driver')],
        loadComponent: () => import('./features/publish/publish-wizard'),
        data: { mode: 'edit-series' },
        title: 'publish.editSeriesTitle',
      },
      {
        path: 'mensajes',
        loadComponent: () => import('./features/chat/messages-page'),
        title: 'nav.messages',
      },
      {
        path: 'mensajes/:id',
        loadComponent: () => import('./features/chat/messages-page'),
        title: 'nav.messages',
      },
      {
        path: 'notificaciones',
        loadComponent: () => import('./features/notifications/notifications-page'),
        title: 'nav.notifications',
      },
      {
        path: 'licencia',
        canMatch: [roleGuard('driver')],
        loadComponent: () => import('./features/license/license-page'),
        title: 'license.title',
      },
      {
        path: 'buscar',
        canMatch: [roleGuard('passenger')],
        loadComponent: () => import('./features/search/search-page'),
        title: 'nav.search',
      },
      {
        path: 'inicio',
        canMatch: [roleGuard('driver')],
        loadComponent: () => import('./features/driver/driver-home'),
        title: 'nav.home',
      },
      {
        path: 'publicar',
        canMatch: [roleGuard('driver'), canPublishGuard],
        loadComponent: () => import('./features/publish/publish-wizard'),
        title: 'nav.publish',
      },
      {
        path: 'vehiculos',
        canMatch: [roleGuard('driver')],
        children: [
          {
            path: '',
            loadComponent: () => import('./features/vehicles/vehicles-page'),
            title: 'vehicles.title',
          },
          {
            path: 'nuevo',
            loadComponent: () => import('./features/vehicles/vehicle-form'),
            title: 'vehicles.newTitle',
          },
          {
            path: ':id',
            loadComponent: () => import('./features/vehicles/vehicle-form'),
            title: 'vehicles.editTitle',
          },
        ],
      },
      {
        path: 'admin',
        canMatch: [roleGuard('admin', 'superadmin')],
        children: [
          {
            path: '',
            pathMatch: 'full',
            loadComponent: () => import('./features/admin/dashboard'),
            title: 'nav.dashboard',
          },
          {
            path: 'aprobaciones',
            loadComponent: () => import('./features/admin/approvals'),
            title: 'nav.approvals',
          },
          {
            path: 'usuarios',
            loadComponent: () => import('./features/admin/users'),
            title: 'nav.users',
          },
          {
            path: 'usuarios/:id',
            loadComponent: () =>
              import('./features/admin/users').then((m) => m.AdminUserDetailPage),
            title: 'nav.users',
          },
          {
            path: 'viajes',
            loadComponent: () => import('./features/admin/trips'),
            title: 'nav.trips',
          },
          {
            path: 'viajes/:id',
            loadComponent: () =>
              import('./features/admin/trips').then((m) => m.AdminTripDetailPage),
            title: 'nav.trips',
          },
          {
            path: 'emergencias',
            loadComponent: () => import('./features/admin/emergencies'),
            title: 'nav.emergencies',
          },
          {
            path: 'moderacion',
            loadComponent: () => import('./features/admin/moderation'),
            title: 'nav.moderation',
          },
          {
            path: 'configuracion',
            canMatch: [roleGuard('superadmin')],
            loadComponent: () => import('./features/admin/settings/settings-page'),
            title: 'nav.settings',
          },
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
