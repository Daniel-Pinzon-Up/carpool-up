import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { ReviewStatus, UserRole, UserStatus } from '../../core/auth/auth.models';
import { BookingStatus } from '../bookings/bookings.api';
import { Page, TripStatus } from '../trips/trips.api';
import { VehicleType } from '../vehicles/vehicles.api';

export interface AdminOverview {
  days: number;
  users: { key: string; count: number }[];
  trips_completed: number;
  trips_per_day: { day: string; count: number }[];
  trips_per_hour: number[];
  occupancy: number | null;
  driver_cancellations: number;
  passenger_cancellations: number;
  no_shows: number;
  top_routes: { origin: string; destination: string; count: number }[];
  rating_distribution: number[];
  pending_approvals: number;
  open_emergencies: number;
}

export interface AdminUserRow {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  status: UserStatus;
  program: string | null;
  created_at: string;
  last_login_at: string | null;
}

export interface AdminUserDetail extends AdminUserRow {
  sex: 'female' | 'male';
  document_status: ReviewStatus | null;
  license_status: ReviewStatus | null;
  license_expires_on: string | null;
  rating: number | null;
  rating_count: number;
  trips_as_driver: number;
  trips_as_passenger: number;
  driver_cancellations: number;
  passenger_no_shows: number;
  active_bookings: number;
  upcoming_trips: number;
  /** Fin de la suspension de la cuenta (nulo con la cuenta suspendida: indefinida). */
  suspended_until: string | null;
  suspension_reason: string | null;
  /** Reservas suspendidas por ausencias hasta esta fecha. */
  booking_ban_until: string | null;
}

export interface AdminTripRow {
  id: string;
  status: TripStatus;
  departs_at: string;
  origin: string;
  destination: string;
  driver_id: string;
  driver_name: string;
  seats_total: number;
  seats_booked: number;
  open_emergencies: number;
  deleted: boolean;
}

export interface Emergency {
  id: string;
  trip_id: string;
  trip_status: TripStatus;
  route: string;
  user_id: string;
  user_name: string;
  lat: number | null;
  lon: number | null;
  note: string | null;
  created_at: string;
  handled_at: string | null;
  resolution: string | null;
}

export interface AdminTripDetail extends AdminTripRow {
  vehicle: string;
  plate: string;
  price_per_seat: number;
  started_at: string | null;
  finished_at: string | null;
  cancel_reason: string | null;
  bookings: {
    id: string;
    passenger_id: string;
    passenger_name: string;
    status: BookingStatus;
    seats: number;
    boarded_at: string | null;
    created_at: string;
  }[];
  emergencies: Emergency[];
  has_chat: boolean;
}

export interface AdminMessage {
  id: string;
  sender_id: string;
  sender_name: string;
  body: string;
  sent_at: string;
  hidden: boolean;
}

export interface AdminRating {
  id: string;
  trip_id: string;
  author_name: string;
  target_name: string;
  target_role: string;
  average: number;
  comment: string | null;
  hidden: boolean;
  created_at: string;
}

// --- Configuracion del superadmin ----------------------------------------------------

export interface SystemSetting {
  key: string;
  value: unknown;
  description: string;
  updated_at: string | null;
  updated_by: string | null;
}

export interface Semester {
  id: string;
  name: string;
  starts_on: string;
  ends_on: string;
  revalidation_deadline: string;
}

export type CatalogKind = 'campus' | 'sector' | 'landmark';

export interface CatalogPlace {
  id: string;
  name: string;
  kind: CatalogKind | 'custom';
  lat: number;
  lon: number;
  is_active: boolean;
}

export interface PicoPlacaRule {
  id: string;
  vehicle_type: VehicleType;
  weekday: number;
  restricted_digits: number[];
  valid_from: string;
  valid_to: string | null;
  is_active: boolean;
}

export interface AuditEntry {
  id: string;
  actor_id: string | null;
  actor_name: string | null;
  action: string;
  entity: string;
  entity_id: string | null;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  ip: string | null;
  created_at: string;
}

const BASE = '/api/v1/admin';

function params(values: Record<string, string | number | boolean | null | undefined>): HttpParams {
  let result = new HttpParams();
  for (const [key, value] of Object.entries(values)) {
    if (value !== null && value !== undefined && value !== '')
      result = result.set(key, String(value));
  }
  return result;
}

/** Panel de administracion y configuracion del superadmin. */
@Injectable({ providedIn: 'root' })
export class AdminApi {
  private readonly http = inject(HttpClient);

  private get<T>(
    url: string,
    query: Record<string, string | number | boolean | null | undefined> = {},
  ): Promise<T> {
    return firstValueFrom(this.http.get<T>(`${BASE}${url}`, { params: params(query) }));
  }

  private post<T>(url: string, body: unknown = {}): Promise<T> {
    return firstValueFrom(this.http.post<T>(`${BASE}${url}`, body));
  }

  private patch<T>(url: string, body: unknown): Promise<T> {
    return firstValueFrom(this.http.patch<T>(`${BASE}${url}`, body));
  }

  private remove(url: string): Promise<void> {
    return firstValueFrom(this.http.delete<void>(`${BASE}${url}`));
  }

  overview(days = 30): Promise<AdminOverview> {
    return this.get('/stats', { days });
  }

  // Usuarios
  users(filters: {
    q?: string;
    role?: string;
    status?: string;
    cursor?: string | null;
  }): Promise<Page<AdminUserRow>> {
    return this.get('/users', { ...filters, limit: 30 });
  }
  user(id: string): Promise<AdminUserDetail> {
    return this.get(`/users/${id}`);
  }
  suspend(id: string, reason: string, days: number | null): Promise<AdminUserDetail> {
    return this.post(`/users/${id}/suspend`, { reason, days });
  }
  reinstate(id: string, reason: string | null): Promise<AdminUserDetail> {
    return this.post(`/users/${id}/reinstate`, { reason });
  }
  block(id: string, reason: string): Promise<AdminUserDetail> {
    return this.post(`/users/${id}/block`, { reason });
  }
  liftBan(id: string, reason: string | null): Promise<AdminUserDetail> {
    return this.post(`/users/${id}/lift-ban`, { reason });
  }
  changeRole(id: string, role: UserRole): Promise<unknown> {
    return this.patch(`/users/${id}/role`, { role });
  }
  createAdmin(body: {
    email: string;
    full_name: string;
    sex: 'female' | 'male';
    password: string;
  }): Promise<unknown> {
    return this.post('/admins', body);
  }

  // Viajes y moderacion
  trips(filters: {
    status?: string;
    day?: string;
    q?: string;
    cursor?: string | null;
  }): Promise<Page<AdminTripRow>> {
    return this.get('/trips', { ...filters, limit: 30 });
  }
  trip(id: string): Promise<AdminTripDetail> {
    return this.get(`/trips/${id}`);
  }
  cancelTrip(id: string, reason: string): Promise<AdminTripDetail> {
    return this.post(`/trips/${id}/cancel`, { reason });
  }
  tripMessages(id: string): Promise<AdminMessage[]> {
    return this.get(`/trips/${id}/messages`);
  }
  hideMessage(id: string, hidden: boolean): Promise<AdminMessage> {
    return this.post(`/messages/${id}/hide`, { hidden });
  }
  ratings(hidden: boolean | null, cursor?: string | null): Promise<Page<AdminRating>> {
    return this.get('/ratings', { hidden, cursor, limit: 30 });
  }
  hideRating(id: string, hidden: boolean): Promise<AdminRating> {
    return this.post(`/ratings/${id}/hide`, { hidden });
  }
  emergencies(includeHandled: boolean): Promise<Emergency[]> {
    return this.get('/emergencies', { include_handled: includeHandled });
  }
  handleEmergency(id: string, resolution: string): Promise<Emergency> {
    return this.post(`/emergencies/${id}/handle`, { resolution });
  }

  // Configuracion (superadmin)
  settings(): Promise<SystemSetting[]> {
    return this.get('/settings');
  }
  updateSetting(key: string, value: unknown): Promise<SystemSetting> {
    return this.patch(`/settings/${key}`, { value });
  }
  semesters(): Promise<Semester[]> {
    return this.get('/semesters');
  }
  saveSemester(body: Omit<Semester, 'id'>, id?: string): Promise<Semester> {
    return id ? this.patch(`/semesters/${id}`, body) : this.post('/semesters', body);
  }
  deleteSemester(id: string): Promise<void> {
    return this.remove(`/semesters/${id}`);
  }
  places(): Promise<CatalogPlace[]> {
    return this.get('/places');
  }
  savePlace(body: Partial<Omit<CatalogPlace, 'id'>>, id?: string): Promise<CatalogPlace> {
    return id ? this.patch(`/places/${id}`, body) : this.post('/places', body);
  }
  deactivatePlace(id: string): Promise<void> {
    return this.remove(`/places/${id}`);
  }
  picoPlaca(): Promise<PicoPlacaRule[]> {
    return this.get('/pico-placa');
  }
  savePicoPlaca(body: Omit<PicoPlacaRule, 'id'>, id?: string): Promise<PicoPlacaRule> {
    return id ? this.patch(`/pico-placa/${id}`, body) : this.post('/pico-placa', body);
  }
  deletePicoPlaca(id: string): Promise<void> {
    return this.remove(`/pico-placa/${id}`);
  }
  audit(filters: {
    action?: string;
    entity?: string;
    cursor?: string | null;
  }): Promise<Page<AuditEntry>> {
    return this.get('/audit', { ...filters, limit: 50 });
  }
}
