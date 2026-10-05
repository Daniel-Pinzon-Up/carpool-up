import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';

export interface LoadedFile {
  url: string; // object URL local; liberar con release()
  type: string;
  isPdf: boolean;
}

/**
 * Descarga archivos privados con el token de acceso y los expone como object URL.
 * Asi nunca se pone el token en una URL ni el archivo queda en la cache del navegador.
 */
@Injectable({ providedIn: 'root' })
export class SecureFileService {
  private readonly http = inject(HttpClient);

  async load(path: string): Promise<LoadedFile> {
    const blob = await firstValueFrom(this.http.get(path, { responseType: 'blob' }));
    return {
      url: URL.createObjectURL(blob),
      type: blob.type,
      isPdf: blob.type === 'application/pdf',
    };
  }

  release(file: LoadedFile | null): void {
    if (file) URL.revokeObjectURL(file.url);
  }
}
