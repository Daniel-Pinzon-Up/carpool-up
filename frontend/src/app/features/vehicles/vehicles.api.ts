import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';

export type VehicleType = 'car' | 'motorcycle';

export interface Vehicle {
  id: string;
  type: VehicleType;
  plate: string;
  brand: string;
  model: string;
  color: string;
  year: number;
  capacity: number;
  luggage_space: boolean;
  is_active: boolean;
  has_photo: boolean;
  created_at: string;
}

export type VehicleInput = Omit<Vehicle, 'id' | 'is_active' | 'has_photo' | 'created_at'>;
export type VehicleChanges = Partial<
  Pick<Vehicle, 'brand' | 'model' | 'color' | 'year' | 'capacity' | 'luggage_space' | 'is_active'>
>;

/** Mismas reglas que el backend: placa de carro ABC123, de moto ABC12D. */
export const PLATE_PATTERNS: Record<VehicleType, RegExp> = {
  car: /^[A-Z]{3}\d{3}$/,
  motorcycle: /^[A-Z]{3}\d{2}[A-Z]$/,
};
export const CAPACITY: Record<VehicleType, [number, number]> = { car: [2, 8], motorcycle: [2, 2] };
export const MIN_YEAR = 1980;

export function normalizePlate(value: string): string {
  return value.replace(/[\s-]/g, '').toUpperCase();
}

const BASE = '/api/v1/vehicles';

@Injectable({ providedIn: 'root' })
export class VehiclesApi {
  private readonly http = inject(HttpClient);

  list(): Promise<Vehicle[]> {
    return firstValueFrom(this.http.get<Vehicle[]>(BASE));
  }

  create(input: VehicleInput): Promise<Vehicle> {
    return firstValueFrom(this.http.post<Vehicle>(BASE, input));
  }

  update(id: string, changes: VehicleChanges): Promise<Vehicle> {
    return firstValueFrom(this.http.patch<Vehicle>(`${BASE}/${id}`, changes));
  }

  remove(id: string): Promise<void> {
    return firstValueFrom(this.http.delete<void>(`${BASE}/${id}`));
  }

  uploadPhoto(id: string, photo: File): Promise<Vehicle> {
    const data = new FormData();
    data.append('photo', photo);
    return firstValueFrom(this.http.put<Vehicle>(`${BASE}/${id}/photo`, data));
  }

  photoPath(id: string): string {
    return `${BASE}/${id}/photo`;
  }
}
