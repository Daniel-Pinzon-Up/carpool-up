import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { BookingStatus } from '../bookings/bookings.api';
import { Page, TripStatus } from '../trips/trips.api';

export type TargetRole = 'driver' | 'passenger';
export type RatingState = 'none' | 'pending' | 'done' | 'closed';

export const CRITERIA: Record<TargetRole, string[]> = {
  driver: ['punctuality', 'safe_driving', 'courtesy', 'cleanliness'],
  passenger: ['punctuality', 'courtesy', 'compliance'],
};

export interface PendingRating {
  trip_id: string;
  departs_at: string;
  origin: string;
  destination: string;
  target_id: string;
  target_name: string;
  target_role: TargetRole;
  criteria: string[];
  closes_at: string;
}

export interface Rating {
  id: string;
  trip_id: string;
  target_role: TargetRole;
  scores: Record<string, number>;
  average: number;
  comment: string | null;
  hidden: boolean;
  created_at: string;
}

export interface RatingSummary {
  user_id: string;
  full_name: string;
  average: number | null;
  count: number;
  criteria: Record<string, number>;
  trips_as_driver: number;
  trips_as_passenger: number;
}

export interface RatingBlock {
  average: number | null;
  count: number;
  criteria: Record<string, number>;
}

export interface PassengerStats {
  trips: number;
  spent: number;
  no_shows: number;
  cancellations: number;
  rating: RatingBlock;
  top_origins: { name: string; count: number }[];
  by_month: { month: string; trips: number; spent: number }[];
}

export interface DriverStats {
  trips: number;
  passengers: number;
  occupancy: number | null;
  contributions: number;
  confirmed_contributions: number;
  cancellations: number;
  rating: RatingBlock;
  by_month: { month: string; trips: number; passengers: number }[];
}

export interface PassengerHistoryEntry {
  booking_id: string;
  trip_id: string;
  departs_at: string;
  origin: string;
  destination: string;
  driver_name: string;
  trip_status: TripStatus;
  booking_status: BookingStatus;
  seats: number;
  amount: number | null;
  ticket_code: string | null;
  paid_confirmed: boolean | null;
  rating: RatingState;
  rating_closes_at: string | null;
}

export interface DriverHistoryEntry {
  trip_id: string;
  departs_at: string;
  origin: string;
  destination: string;
  trip_status: TripStatus;
  seats_total: number;
  passengers: number;
  contributions: number;
  to_rate: number;
  rating: RatingState;
  rating_closes_at: string | null;
}

const API = '/api/v1';

/** Calificaciones, reputacion, historial y estadisticas. */
@Injectable({ providedIn: 'root' })
export class RatingsApi {
  private readonly http = inject(HttpClient);

  private get<T>(url: string, params?: HttpParams): Promise<T> {
    return firstValueFrom(this.http.get<T>(`${API}${url}`, { params }));
  }

  pending(): Promise<PendingRating[]> {
    return this.get('/ratings/pending');
  }

  rate(
    tripId: string,
    body: { target_id: string; scores: Record<string, number>; comment: string | null },
  ): Promise<Rating> {
    return firstValueFrom(this.http.post<Rating>(`${API}/trips/${tripId}/ratings`, body));
  }

  summary(userId: string): Promise<RatingSummary> {
    return this.get(`/users/${userId}/rating-summary`);
  }

  received(userId: string, cursor?: string | null): Promise<Page<Rating>> {
    let params = new HttpParams().set('limit', 10);
    if (cursor) params = params.set('cursor', cursor);
    return this.get(`/users/${userId}/ratings`, params);
  }

  passengerStats(): Promise<PassengerStats> {
    return this.get('/stats/passenger');
  }

  driverStats(): Promise<DriverStats> {
    return this.get('/stats/driver');
  }

  passengerHistory(cursor?: string | null): Promise<Page<PassengerHistoryEntry>> {
    let params = new HttpParams().set('limit', 20);
    if (cursor) params = params.set('cursor', cursor);
    return this.get('/history/passenger', params);
  }

  driverHistory(cursor?: string | null): Promise<Page<DriverHistoryEntry>> {
    let params = new HttpParams().set('limit', 20);
    if (cursor) params = params.set('cursor', cursor);
    return this.get('/history/driver', params);
  }
}

/** Meses del backend (YYYY-MM) como etiquetas cortas y largas del idioma activo. */
export function monthLabels(month: string, lang: string): { label: string; title: string } {
  const [year, value] = month.split('-').map(Number);
  const date = new Date(Date.UTC(year, value - 1, 15));
  return {
    label: date.toLocaleDateString(lang, { month: 'short', timeZone: 'UTC' }),
    title: date.toLocaleDateString(lang, { month: 'long', year: 'numeric', timeZone: 'UTC' }),
  };
}
