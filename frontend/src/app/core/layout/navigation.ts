import {
  LucideBell,
  LucideCalendarCheck,
  LucideCar,
  LucideCircleUser,
  LucideHouse,
  LucideIcon,
  LucideLayoutDashboard,
  LucideMessageCircle,
  LucideRoute,
  LucideSearch,
  LucideSettings,
  LucideShieldCheck,
  LucideSiren,
  LucideMessageSquareWarning,
  LucideSquarePlus,
  LucideUsers,
} from '@icons';
import { UserRole } from '../auth/auth.models';

export interface NavItem {
  /** Clave de traduccion bajo nav.* */
  key: string;
  path: string;
  icon: LucideIcon;
}

/** Destinos por rol (seccion 12.5). La barra inferior movil muestra como maximo 5. */
export const NAV_BY_ROLE: Record<UserRole, NavItem[]> = {
  passenger: [
    { key: 'search', path: '/buscar', icon: LucideSearch },
    { key: 'myTrips', path: '/mis-viajes', icon: LucideCalendarCheck },
    { key: 'messages', path: '/mensajes', icon: LucideMessageCircle },
    { key: 'notifications', path: '/notificaciones', icon: LucideBell },
    { key: 'profile', path: '/perfil', icon: LucideCircleUser },
  ],
  driver: [
    { key: 'home', path: '/inicio', icon: LucideHouse },
    { key: 'publish', path: '/publicar', icon: LucideSquarePlus },
    { key: 'myTrips', path: '/mis-viajes', icon: LucideCar },
    { key: 'messages', path: '/mensajes', icon: LucideMessageCircle },
    { key: 'profile', path: '/perfil', icon: LucideCircleUser },
  ],
  admin: [
    { key: 'dashboard', path: '/admin', icon: LucideLayoutDashboard },
    { key: 'approvals', path: '/admin/aprobaciones', icon: LucideShieldCheck },
    { key: 'users', path: '/admin/usuarios', icon: LucideUsers },
    { key: 'trips', path: '/admin/viajes', icon: LucideRoute },
    { key: 'emergencies', path: '/admin/emergencias', icon: LucideSiren },
    { key: 'moderation', path: '/admin/moderacion', icon: LucideMessageSquareWarning },
  ],
  superadmin: [
    { key: 'dashboard', path: '/admin', icon: LucideLayoutDashboard },
    { key: 'approvals', path: '/admin/aprobaciones', icon: LucideShieldCheck },
    { key: 'users', path: '/admin/usuarios', icon: LucideUsers },
    { key: 'trips', path: '/admin/viajes', icon: LucideRoute },
    { key: 'emergencies', path: '/admin/emergencias', icon: LucideSiren },
    { key: 'moderation', path: '/admin/moderacion', icon: LucideMessageSquareWarning },
    { key: 'settings', path: '/admin/configuracion', icon: LucideSettings },
  ],
};
