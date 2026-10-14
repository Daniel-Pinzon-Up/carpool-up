import { BadgeTone } from '../../shared/ui/status-badge';
import { TripStatus } from './trips.api';

export const TRIP_STATUS_TONE: Record<TripStatus, BadgeTone> = {
  scheduled: 'info',
  in_progress: 'pending',
  completed: 'success',
  cancelled_by_driver: 'danger',
  cancelled_pico_placa: 'warning',
  not_held: 'neutral',
};

/** Fecha y hora cortas en la zona de Pamplona e idioma activo. */
export function formatDeparture(iso: string, lang: string): string {
  return new Date(iso).toLocaleString(lang, {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    hour: 'numeric',
    minute: '2-digit',
    timeZone: 'America/Bogota',
  });
}

export function formatTime(iso: string, lang: string): string {
  return new Date(iso).toLocaleTimeString(lang, {
    hour: 'numeric',
    minute: '2-digit',
    timeZone: 'America/Bogota',
  });
}
