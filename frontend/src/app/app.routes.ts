import { Routes } from '@angular/router';
import { devOnlyGuard } from './core/guards/dev-only.guard';
import { Shell } from './core/layout/shell';

/** Destino aun no construido; cada paso del plan lo reemplaza por su feature con carga diferida. */
const comingSoon = (path: string, section: string) => ({
  path,
  loadComponent: () => import('./features/placeholder/coming-soon'),
  data: { section },
  title: `nav.${section}`,
});

export const routes: Routes = [
  {
    path: '',
    component: Shell,
    children: [
      { path: '', pathMatch: 'full', redirectTo: 'buscar' },
      comingSoon('buscar', 'search'),
      comingSoon('mis-viajes', 'myTrips'),
      comingSoon('mensajes', 'messages'),
      comingSoon('notificaciones', 'notifications'),
      comingSoon('perfil', 'profile'),
      {
        path: 'catalogo',
        canMatch: [devOnlyGuard],
        loadComponent: () => import('./features/catalog/catalog'),
        title: 'nav.catalog',
      },
    ],
  },
  { path: '**', redirectTo: '' },
];
