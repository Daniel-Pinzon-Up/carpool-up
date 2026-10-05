import { HttpClient } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { readPref, writePref } from '../../core/storage/local-preferences';

export type PlaceKind = 'campus' | 'sector' | 'landmark' | 'custom';

export interface Place {
  id: string;
  name: string;
  kind: PlaceKind;
  lat: number;
  lon: number;
  is_active: boolean;
}

/** Valor que entrega el selector de lugares. */
export interface PlaceValue {
  place_id: string;
  name: string;
  kind: PlaceKind;
  lat: number;
  lon: number;
}

const RECENT_KEY = 'cp.recentPlaces';
const RECENT_LIMIT = 5;

export function toPlaceValue(place: Place): PlaceValue {
  return { place_id: place.id, name: place.name, kind: place.kind, lat: place.lat, lon: place.lon };
}

@Injectable({ providedIn: 'root' })
export class PlacesApi {
  private readonly http = inject(HttpClient);
  private catalogRequest: Promise<Place[]> | null = null;
  readonly recent = signal<PlaceValue[]>(this.readRecent());

  /** Catalogo publico; se pide una vez por sesion de la app. */
  catalog(): Promise<Place[]> {
    this.catalogRequest ??= firstValueFrom(this.http.get<Place[]>('/api/v1/places')).catch(
      (error: unknown) => {
        this.catalogRequest = null;
        throw error;
      },
    );
    return this.catalogRequest;
  }

  async createCustom(name: string, lat: number, lon: number): Promise<PlaceValue> {
    const place = await firstValueFrom(
      this.http.post<Place>('/api/v1/places/custom', { name, lat, lon }),
    );
    return toPlaceValue(place);
  }

  /** Lugares usados hace poco en este dispositivo (reconocer antes que recordar). */
  remember(place: PlaceValue): void {
    const list = [place, ...this.recent().filter((p) => p.place_id !== place.place_id)].slice(
      0,
      RECENT_LIMIT,
    );
    this.recent.set(list);
    writePref(RECENT_KEY, JSON.stringify(list));
  }

  private readRecent(): PlaceValue[] {
    try {
      const parsed = JSON.parse(readPref(RECENT_KEY) ?? '[]') as PlaceValue[];
      return Array.isArray(parsed) ? parsed.slice(0, RECENT_LIMIT) : [];
    } catch {
      return [];
    }
  }
}
