import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { TripRule, TripStatus } from '../trips/trips.api';
import { VehicleType } from '../vehicles/vehicles.api';

export interface SearchPreferences {
  pets: boolean;
  luggage: boolean;
  no_smoking: boolean;
  music: boolean;
  women_only: boolean;
}

export const PREFERENCE_KEYS: (keyof SearchPreferences)[] = [
  'pets',
  'luggage',
  'no_smoking',
  'music',
  'women_only',
];

export interface SearchRequest extends SearchPreferences {
  origin_place_id: string;
  destination_place_id: string;
  date: string;
  time: string;
  seats: number;
}

export interface MatchPoint {
  kind: 'stop' | 'route';
  name: string | null;
  lat: number;
  lon: number;
  eta: string;
  walk_m: number;
}

export interface SearchResult {
  trip_id: string;
  status: TripStatus;
  departs_at: string;
  arrives_at: string;
  origin: string;
  destination: string;
  price_per_seat: number;
  seats_available: number;
  pickup: MatchPoint;
  dropoff: MatchPoint;
  minutes_from_requested: number;
  driver: { id: string; full_name: string; rating: number | null; trips_as_driver: number };
  vehicle: {
    vehicle_id: string;
    type: VehicleType;
    brand: string;
    model: string;
    color: string;
    has_photo: boolean;
  };
  rules: TripRule[];
}

@Injectable({ providedIn: 'root' })
export class SearchApi {
  private readonly http = inject(HttpClient);

  search(request: SearchRequest): Promise<SearchResult[]> {
    let params = new HttpParams();
    for (const [key, value] of Object.entries(request)) {
      // Las preferencias apagadas no se envian.
      if (value !== false) params = params.set(key, String(value));
    }
    return firstValueFrom(this.http.get<SearchResult[]>('/api/v1/search/trips', { params }));
  }
}
