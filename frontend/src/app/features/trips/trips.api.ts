import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import type { BookingStatus } from '../bookings/bookings.api';
import { VehicleType } from '../vehicles/vehicles.api';

export type TripStatus =
  | 'scheduled'
  | 'in_progress'
  | 'completed'
  | 'cancelled_by_driver'
  | 'cancelled_pico_placa'
  | 'not_held';
export type RuleKind = 'women_only' | 'pets' | 'luggage' | 'smoking' | 'music' | 'custom';

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
  /** Chat grupal del viaje si quien consulta participa. */
  chat_id: string | null;
}

export interface Page<T> {
  items: T[];
  next_cursor: string | null;
}

export interface TripCreate {
  departs_at: string;
  place_ids: string[];
  vehicle_id: string;
  seats: number;
  price_per_seat: number;
  rules: TripRule[];
}

export type TripUpdate = Partial<TripCreate>;

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

  myTrips(scope: 'upcoming' | 'history', cursor?: string | null): Promise<Page<TripSummary>> {
    let params = new HttpParams().set('scope', scope).set('limit', 20);
    if (cursor) params = params.set('cursor', cursor);
    return this.get('/trips/mine', params);
  }

  trip(id: string): Promise<Trip> {
    return this.get(`/trips/${id}`);
  }

  updateTrip(id: string, body: TripUpdate): Promise<Trip> {
    return this.patch(`/trips/${id}`, body);
  }

  cancelTrip(id: string, reason: string): Promise<Trip> {
    return this.post(`/trips/${id}/cancel`, { reason });
  }

  duplicateTrip(id: string, departsAt: string): Promise<Trip> {
    return this.post(`/trips/${id}/duplicate`, { departs_at: departsAt });
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
