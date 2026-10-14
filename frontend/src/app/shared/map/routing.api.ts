import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';

export interface RoutePointInput {
  place_id?: string;
  lat?: number;
  lon?: number;
}

export interface RoutePreviewRequest {
  points: RoutePointInput[];
  departs_at?: string;
  vehicle_type?: 'car' | 'motorcycle';
  seats?: number;
}

export interface RoutePreview {
  geometry: number[][];
  distance_m: number;
  duration_s: number;
  points: {
    place_id: string | null;
    name: string | null;
    lat: number;
    lon: number;
    eta_offset_s: number;
    eta: string | null;
  }[];
  pricing_configured: boolean;
  suggested_price: number | null;
  max_price_per_seat: number | null;
}

@Injectable({ providedIn: 'root' })
export class RoutingApi {
  private readonly http = inject(HttpClient);

  preview(request: RoutePreviewRequest): Promise<RoutePreview> {
    return firstValueFrom(this.http.post<RoutePreview>('/api/v1/routing/preview', request));
  }
}

/** Pesos colombianos sin decimales, en el idioma activo. */
export function formatCop(value: number, lang: string): string {
  return new Intl.NumberFormat(lang === 'es' ? 'es-CO' : lang, {
    style: 'currency',
    currency: 'COP',
    maximumFractionDigits: 0,
  }).format(value);
}
