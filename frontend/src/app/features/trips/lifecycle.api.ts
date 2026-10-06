import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { Booking } from '../bookings/bookings.api';
import { VehicleType } from '../vehicles/vehicles.api';
import { Trip, TripStatus } from './trips.api';

export interface LiveLocation {
  lat: number;
  lon: number;
  accuracy?: number | null;
  heading?: number | null;
  speed?: number | null;
  at: string;
}

export interface Ticket {
  id: string;
  booking_id: string;
  code: string;
  amount: number;
  seats: number;
  issued_at: string;
  paid_confirmed: boolean;
  paid_confirmed_at: string | null;
  trip_id: string;
  departs_at: string;
  origin: string;
  destination: string;
  driver_name: string;
  passenger_name: string;
}

export interface ShareLink {
  token: string;
  path: string;
  expires_at: string;
}

export interface TrustedContact {
  id: string;
  name: string;
  phone: string;
  relationship: string | null;
}

export type ContactInput = Omit<TrustedContact, 'id'>;

export interface PublicTrip {
  status: TripStatus;
  departs_at: string;
  started_at: string | null;
  finished_at: string | null;
  arrives_at: string;
  geometry: number[][];
  stops: { name: string; lat: number; lon: number; kind: 'origin' | 'stop' | 'destination' }[];
  vehicle: { type: VehicleType; brand: string; model: string; color: string; plate: string };
  location: LiveLocation | null;
  expires_at: string;
}

export interface EmergencyReport {
  emergency: { id: string; created_at: string };
  phone: string;
}

const API = '/api/v1';

/** Ciclo del viaje y seguridad: iniciar, abordaje, tickets, ubicacion, enlaces y emergencias. */
@Injectable({ providedIn: 'root' })
export class LifecycleApi {
  private readonly http = inject(HttpClient);

  private post<T>(url: string, body: unknown = {}): Promise<T> {
    return firstValueFrom(this.http.post<T>(`${API}${url}`, body));
  }

  start(tripId: string): Promise<Trip> {
    return this.post(`/trips/${tripId}/start`);
  }

  finish(tripId: string): Promise<Trip> {
    return this.post(`/trips/${tripId}/finish`);
  }

  boarded(bookingId: string): Promise<Booking> {
    return this.post(`/bookings/${bookingId}/boarded`);
  }

  noShow(bookingId: string): Promise<Booking> {
    return this.post(`/bookings/${bookingId}/no-show`);
  }

  location(tripId: string): Promise<LiveLocation | null> {
    return firstValueFrom(this.http.get<LiveLocation | null>(`${API}/trips/${tripId}/location`));
  }

  shareLink(tripId: string): Promise<ShareLink> {
    return this.post(`/trips/${tripId}/share-links`);
  }

  emergency(
    tripId: string,
    body: { lat?: number; lon?: number; note?: string },
  ): Promise<EmergencyReport> {
    return this.post(`/trips/${tripId}/emergency`, body);
  }

  tickets(role: 'passenger' | 'driver', tripId?: string): Promise<Ticket[]> {
    let params = new HttpParams().set('role', role);
    if (tripId) params = params.set('trip_id', tripId);
    return firstValueFrom(this.http.get<Ticket[]>(`${API}/tickets/mine`, { params }));
  }

  markPaid(ticketId: string, paid: boolean): Promise<Ticket> {
    return this.post(`/tickets/${ticketId}/paid`, { paid });
  }

  publicTrip(token: string): Promise<PublicTrip> {
    return firstValueFrom(this.http.get<PublicTrip>(`${API}/public/share/${token}`));
  }

  // --- Contactos de confianza -----------------------------------------------------------

  contacts(): Promise<TrustedContact[]> {
    return firstValueFrom(this.http.get<TrustedContact[]>(`${API}/me/trusted-contacts`));
  }

  addContact(body: ContactInput): Promise<TrustedContact> {
    return this.post('/me/trusted-contacts', body);
  }

  updateContact(id: string, body: Partial<ContactInput>): Promise<TrustedContact> {
    return firstValueFrom(
      this.http.patch<TrustedContact>(`${API}/me/trusted-contacts/${id}`, body),
    );
  }

  deleteContact(id: string): Promise<void> {
    return firstValueFrom(this.http.delete<void>(`${API}/me/trusted-contacts/${id}`));
  }
}
