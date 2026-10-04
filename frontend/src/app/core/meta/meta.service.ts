import { HttpClient } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';

/** Parametros publicos que la interfaz usa para validar antes de enviar. */
export interface PublicSettings {
  allowed_email_suffix: string;
  password_min_length: number;
  max_upload_mb: number;
  auth_code_minutes: number;
  [key: string]: unknown;
}

const FALLBACK: PublicSettings = {
  allowed_email_suffix: '.edu.co',
  password_min_length: 10,
  max_upload_mb: 5,
  auth_code_minutes: 10,
};

@Injectable({ providedIn: 'root' })
export class MetaService {
  private readonly http = inject(HttpClient);
  private loading: Promise<PublicSettings> | null = null;

  /** Valores por defecto hasta que llega la respuesta; la API siempre valida de nuevo. */
  readonly settings = signal<PublicSettings>(FALLBACK);

  load(): Promise<PublicSettings> {
    this.loading ??= firstValueFrom(this.http.get<PublicSettings>('/api/v1/meta/settings/public'))
      .then((settings) => {
        this.settings.set({ ...FALLBACK, ...settings });
        return this.settings();
      })
      .catch(() => {
        this.loading = null;
        return this.settings();
      });
    return this.loading;
  }
}
