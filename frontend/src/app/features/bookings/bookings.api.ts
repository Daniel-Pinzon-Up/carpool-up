import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { BadgeTone } from '../../shared/ui/status-badge';
import { Page, TripStatus, VehicleSummary } from '../trips/trips.api';

export type BookingStatus =
  | 'requested'
  | 'accepted'
  | 'rejected'
  | 'cancel_requested'
  | 'cancelled_by_passenger'
  | 'cancelled_by_driver'
  | 'auto_cancelled_late'
  | 'auto_cancelled_pico_placa'
  | 'expired'
  | 'no_show'
  | 'completed';
export type SubscriptionStatus =
  'requested' | 'active' | 'rejected' | 'cancelled' | 'finished' | 'expired';
export type WaitlistStatus = 'waiting' | 'offered' | 'converted' | 'expired' | 'left';
export type SubscriptionOption = number | 'series';

export const BOOKING_STATUS_TONE: Record<BookingStatus, BadgeTone> = {
  requested: 'pending',
  accepted: 'success',
  rejected: 'danger',
  cancel_requested: 'warning',
  cancelled_by_passenger: 'neutral',
  cancelled_by_driver: 'danger',
  auto_cancelled_late: 'warning',
  auto_cancelled_pico_placa: 'warning',
  expired: 'neutral',
  no_show: 'danger',
  completed: 'success',
};

export const SUBSCRIPTION_STATUS_TONE: Record<SubscriptionStatus, BadgeTone> = {
  requested: 'pending',
  active: 'success',
  rejected: 'danger',
  cancelled: 'neutral',
  finished: 'neutral',
  expired: 'neutral',
};

/** Estados en los que la reserva sigue viva (cuenta para el viaje). */
export const ACTIVE_BOOKING: BookingStatus[] = ['requested', 'accepted', 'cancel_requested'];

export interface BookingPreferences {
  pets: boolean;
  luggage: boolean;
  no_smoking: boolean;
  music: boolean;
}

export const BOOKING_PREFERENCE_KEYS: (keyof BookingPreferences)[] = [
  'pets',
  'luggage',
  'no_smoking',
  'music',
];

export interface PointsRequest {
  seats: number;
  pickup_place_id: string;
  dropoff_place_id: string;
  preferences: BookingPreferences;
}

export interface SubscriptionRequest extends PointsRequest {
  option: SubscriptionOption;
  start_date: string;
}

export interface PassengerCard {
  id: string;
  full_name: string;
  program: string | null;
  rating: number | null;
  trips_as_passenger: number;
}

export interface MeetingPoint {
  place_id: string;
  place_name: string;
  kind: 'stop' | 'route';
  name: string | null;
  lat: number;
  lon: number;
  eta: string;
  walk_m: number;
}

export interface TripBrief {
  id: string;
  series_id: string | null;
  status: TripStatus;
  departs_at: string;
  arrives_at: string;
  origin: string;
  destination: string;
  price_per_seat: number;
  driver: { id: string; full_name: string };
  vehicle: VehicleSummary;
}

export interface Cancellation {
  id: string;
  reason: string;
  status: 'pending' | 'accepted' | 'rejected';
  created_at: string;
  resolved_at: string | null;
}

export interface Booking {
  id: string;
  trip: TripBrief;
  passenger: PassengerCard;
  subscription_id: string | null;
  seats: number;
  amount: number;
  status: BookingStatus;
  pickup: MeetingPoint;
  dropoff: MeetingPoint;
  preferences: BookingPreferences;
  expires_at: string;
  penalty_free: boolean;
  free_cancel: boolean;
  created_at: string;
  decided_at: string | null;
  cancelled_at: string | null;
  cancel_reason: string | null;
  cancellation: Cancellation | null;
  payment_note: string | null;
}

export interface Subscription {
  id: string;
  series: {
    id: string;
    origin: string;
    destination: string;
    weekdays: number[];
    departure_time: string;
    window_end: string;
    price_per_seat: number;
    driver: { id: string; full_name: string };
  };
  passenger: PassengerCard;
  from_date: string;
  to_date: string;
  seats: number;
  pickup_place: string;
  dropoff_place: string;
  preferences: BookingPreferences;
  status: SubscriptionStatus;
  expires_at: string;
  created_at: string;
  decided_at: string | null;
  reject_reason: string | null;
  booked_dates: string[];
  skipped_dates: string[];
}

export interface AvailabilityDay {
  trip_id: string;
  date: string;
  departs_at: string;
  status: TripStatus;
  seats_available: number;
  bookable: boolean;
}

export interface SeriesAvailability {
  series_id: string;
  options: SubscriptionOption[];
  days: AvailabilityDay[];
}

export interface WaitlistEntry {
  id: string;
  trip: TripBrief;
  seats: number;
  status: WaitlistStatus;
  ahead: number;
  offered_at: string | null;
  offer_expires_at: string | null;
  booking_id: string | null;
  created_at: string;
}

export interface Inbox {
  bookings: Booking[];
  cancellations: Booking[];
  subscriptions: Subscription[];
}

const API = '/api/v1';

@Injectable({ providedIn: 'root' })
export class BookingsApi {
  private readonly http = inject(HttpClient);

  private get<T>(url: string, params?: HttpParams): Promise<T> {
    return firstValueFrom(this.http.get<T>(`${API}${url}`, { params }));
  }

  private post<T>(url: string, body: unknown = {}): Promise<T> {
    return firstValueFrom(this.http.post<T>(`${API}${url}`, body));
  }

  // --- Reservas -----------------------------------------------------------------------

  request(tripId: string, body: PointsRequest): Promise<Booking> {
    return this.post(`/trips/${tripId}/bookings`, body);
  }

  mine(scope: 'upcoming' | 'history', cursor?: string | null): Promise<Page<Booking>> {
    let params = new HttpParams().set('scope', scope).set('limit', 20);
    if (cursor) params = params.set('cursor', cursor);
    return this.get('/bookings/mine', params);
  }

  booking(id: string): Promise<Booking> {
    return this.get(`/bookings/${id}`);
  }

  forTrip(tripId: string): Promise<Booking[]> {
    return this.get(`/trips/${tripId}/bookings`);
  }

  inbox(): Promise<Inbox> {
    return this.get('/bookings/inbox');
  }

  accept(id: string): Promise<Booking> {
    return this.post(`/bookings/${id}/accept`);
  }

  reject(id: string, reason: string | null): Promise<Booking> {
    return this.post(`/bookings/${id}/reject`, { reason });
  }

  cancel(id: string, reason: string | null): Promise<Booking> {
    return this.post(`/bookings/${id}/cancel`, { reason });
  }

  resolveCancellation(requestId: string, accept: boolean): Promise<Booking> {
    return this.post(`/cancellation-requests/${requestId}/${accept ? 'accept' : 'reject'}`);
  }

  // --- Suscripciones ------------------------------------------------------------------

  availability(seriesId: string, seats: number): Promise<SeriesAvailability> {
    return this.get(`/series/${seriesId}/availability`, new HttpParams().set('seats', seats));
  }

  subscribe(seriesId: string, body: SubscriptionRequest): Promise<Subscription> {
    return this.post(`/series/${seriesId}/subscriptions`, body);
  }

  mySubscriptions(): Promise<Subscription[]> {
    return this.get('/subscriptions/mine');
  }

  acceptSubscription(id: string): Promise<Subscription> {
    return this.post(`/subscriptions/${id}/accept`);
  }

  rejectSubscription(id: string, reason: string | null): Promise<Subscription> {
    return this.post(`/subscriptions/${id}/reject`, { reason });
  }

  cancelSubscription(id: string, reason: string | null): Promise<Subscription> {
    return this.post(`/subscriptions/${id}/cancel`, { reason });
  }

  // --- Lista de espera ----------------------------------------------------------------

  joinWaitlist(tripId: string, body: PointsRequest): Promise<WaitlistEntry> {
    return this.post(`/trips/${tripId}/waitlist`, body);
  }

  leaveWaitlist(tripId: string): Promise<void> {
    return firstValueFrom(this.http.delete<void>(`${API}/trips/${tripId}/waitlist`));
  }

  myWaitlist(): Promise<WaitlistEntry[]> {
    return this.get('/waitlist/mine');
  }

  confirmOffer(id: string): Promise<WaitlistEntry> {
    return this.post(`/waitlist/${id}/confirm`);
  }

  declineOffer(id: string): Promise<WaitlistEntry> {
    return this.post(`/waitlist/${id}/decline`);
  }
}

export function noPreferences(): BookingPreferences {
  return { pets: false, luggage: false, no_smoking: false, music: false };
}
