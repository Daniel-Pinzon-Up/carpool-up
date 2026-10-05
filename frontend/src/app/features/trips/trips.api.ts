import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import type { BookingStatus, SubscriptionStatus, WaitlistStatus } from '../bookings/bookings.api';
import { VehicleType } from '../vehicles/vehicles.api';

export type TripStatus =
  | 'scheduled'
  | 'in_progress'
  | 'completed'
  | 'cancelled_by_driver'
  | 'cancelled_pico_placa'
  | 'not_held';
export type SeriesStatus = 'active' | 'cancelled' | 'finished';
export type RuleKind = 'women_only' | 'pets' | 'luggage' | 'smoking' | 'music' | 'custom';
export type SeriesWindow = number | 'semester';

export interface TripRule {
  kind: RuleKind;
  value: string;
}

export interface TripStop {
  position: number;
  kind: 'origin' | 'stop' | 'destination';
  place_id: string;
  name: string;
  lat: number;
  lon: number;
  eta: string | null;
}

export interface VehicleSummary {
  id: string;
  type: VehicleType;
  brand: string;
  model: string;
  color: string;
  has_photo: boolean;
  plate: string | null;
}

export interface TripSummary {
  id: string;
  series_id: string | null;
  status: TripStatus;
  departs_at: string;
  arrives_at: string;
  seats_total: number;
  price_per_seat: number;
  origin: string;
  destination: string;
  stop_count: number;
  vehicle: VehicleSummary;
  editable: boolean;
  seats_available: number;
  /** Solicitudes y cancelaciones por decidir (solo el conductor). */
  pending_requests: number;
}

export interface CoPassenger {
  id: string;
  full_name: string;
  seats: number;
  pickup_name: string | null;
  pickup_eta: string | null;
}

export interface MyBooking {
  id: string;
  status: BookingStatus;
  seats: number;
  pickup_name: string | null;
  pickup_eta: string;
  dropoff_name: string | null;
  dropoff_eta: string;
}

export interface MyWaitlist {
  id: string;
  status: WaitlistStatus;
  seats: number;
  offer_expires_at: string | null;
}

export interface Trip extends TripSummary {
  geometry: number[][];
  distance_m: number;
  est_duration_s: number;
  stops: TripStop[];
  rules: TripRule[];
  driver: { id: string; full_name: string };
  cancel_reason: string | null;
  cancelled_at: string | null;
  passengers: CoPassenger[];
  payment_note: string | null;
  my_booking: MyBooking | null;
  my_waitlist: MyWaitlist | null;
}

export interface OccurrenceCounts {
  total: number;
  scheduled: number;
  pico_placa: number;
  cancelled: number;
}

export interface SeriesSummary {
  id: string;
  status: SeriesStatus;
  weekdays: number[];
  departure_time: string;
  window_start: string;
  window_end: string;
  seats: number;
  price_per_seat: number;
  origin: string;
  destination: string;
  vehicle: VehicleSummary;
  next_departure: string | null;
  counts: OccurrenceCounts;
}

export interface Series extends SeriesSummary {
  stops: TripStop[];
  rules: TripRule[];
  driver: { id: string; full_name: string };
  cancel_reason: string | null;
  occurrences: TripSummary[];
  my_subscription: {
    id: string;
    status: SubscriptionStatus;
    from_date: string;
    to_date: string;
  } | null;
}

export interface Page<T> {
  items: T[];
  next_cursor: string | null;
}

interface TripTemplate {
  place_ids: string[];
  vehicle_id: string;
  seats: number;
  price_per_seat: number;
  rules: TripRule[];
}

export interface TripCreate extends TripTemplate {
  departs_at: string;
}

export interface SeriesCreate extends TripTemplate {
  weekdays: number[];
  departure_time: string;
  start_date: string;
  window: SeriesWindow;
}

export type TripUpdate = Partial<TripCreate>;
export type SeriesUpdate = Partial<Omit<SeriesCreate, 'start_date' | 'window'>> & {
  /** Confirma el cambio cuando hay reservas afectadas. */
  confirm?: boolean;
};

export interface Semester {
  id: string;
  name: string;
  starts_on: string;
  ends_on: string;
}

const API = '/api/v1';

@Injectable({ providedIn: 'root' })
export class TripsApi {
  private readonly http = inject(HttpClient);

  private get<T>(url: string, params?: HttpParams): Promise<T> {
    return firstValueFrom(this.http.get<T>(`${API}${url}`, { params }));
  }

  private post<T>(url: string, body: unknown): Promise<T> {
    return firstValueFrom(this.http.post<T>(`${API}${url}`, body));
  }

  private patch<T>(url: string, body: unknown): Promise<T> {
    return firstValueFrom(this.http.patch<T>(`${API}${url}`, body));
  }

  publishTrip(body: TripCreate): Promise<Trip> {
    return this.post('/trips', body);
  }

  publishSeries(body: SeriesCreate): Promise<Series> {
    return this.post('/series', body);
  }

  myTrips(scope: 'upcoming' | 'history', cursor?: string | null): Promise<Page<TripSummary>> {
    let params = new HttpParams().set('scope', scope).set('limit', 20);
    if (cursor) params = params.set('cursor', cursor);
    return this.get('/trips/mine', params);
  }

  mySeries(): Promise<SeriesSummary[]> {
    return this.get('/series/mine');
  }

  trip(id: string): Promise<Trip> {
    return this.get(`/trips/${id}`);
  }

  series(id: string): Promise<Series> {
    return this.get(`/series/${id}`);
  }

  updateTrip(id: string, body: TripUpdate): Promise<Trip> {
    return this.patch(`/trips/${id}`, body);
  }

  updateSeries(id: string, body: SeriesUpdate): Promise<Series> {
    return this.patch(`/series/${id}`, body);
  }

  cancelTrip(id: string, reason: string): Promise<Trip> {
    return this.post(`/trips/${id}/cancel`, { reason });
  }

  cancelSeries(id: string, reason: string): Promise<Series> {
    return this.post(`/series/${id}/cancel`, { reason });
  }

  duplicateTrip(id: string, departsAt: string): Promise<Trip> {
    return this.post(`/trips/${id}/duplicate`, { departs_at: departsAt });
  }

  duplicateSeries(id: string, startDate: string, window: SeriesWindow): Promise<Series> {
    return this.post(`/series/${id}/duplicate`, { start_date: startDate, window });
  }

  picoPlacaDates(vehicleId: string, from: string, to: string): Promise<string[]> {
    const params = new HttpParams().set('from', from).set('to', to);
    return this.get(`/vehicles/${vehicleId}/pico-placa`, params);
  }

  currentSemester(): Promise<Semester> {
    return this.get('/semesters/current');
  }
}

/** Fecha local (YYYY-MM-DD) de Pamplona para un instante. */
export function pamplonaDate(iso: string | Date): string {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'America/Bogota',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date(iso));
}

/** Hora local (HH:mm) de Pamplona para un instante. */
export function pamplonaTime(iso: string | Date): string {
  return new Intl.DateTimeFormat('en-GB', {
    timeZone: 'America/Bogota',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).format(new Date(iso));
}

/** Instante ISO para una fecha y hora locales de Pamplona (UTC-5, sin horario de verano). */
export function pamplonaInstant(date: string, time: string): string {
  return `${date}T${time}:00-05:00`;
}

/** Suma dias a una fecha YYYY-MM-DD sin pasar por zonas horarias. */
export function addDays(date: string, days: number): string {
  const [y, m, d] = date.split('-').map(Number);
  const result = new Date(Date.UTC(y, m - 1, d + days));
  return result.toISOString().slice(0, 10);
}

/** Dia de la semana de una fecha YYYY-MM-DD con 0 = lunes, como el backend. */
export function weekdayOf(date: string): number {
  const [y, m, d] = date.split('-').map(Number);
  return (new Date(Date.UTC(y, m - 1, d)).getUTCDay() + 6) % 7;
}

/**
 * Fechas que generaria una serie: dias elegidos dentro de la ventana, sin pasar del
 * fin del semestre. Es una vista previa; el servidor decide.
 */
export function seriesDates(
  start: string,
  window: SeriesWindow,
  weekdays: number[],
  semesterEnd: string | null,
): string[] {
  let end = window === 'semester' ? semesterEnd : addDays(start, window - 1);
  if (!end) return [];
  if (semesterEnd && end > semesterEnd) end = semesterEnd;
  const dates: string[] = [];
  for (let day = start; day <= end; day = addDays(day, 1)) {
    if (weekdays.includes(weekdayOf(day))) dates.push(day);
  }
  return dates;
}
