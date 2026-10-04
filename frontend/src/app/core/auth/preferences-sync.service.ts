import { Injectable, effect, inject, untracked } from '@angular/core';
import { LanguageService, isLanguage } from '../i18n/language.service';
import { ThemeService } from '../theme/theme.service';
import { AuthService } from './auth.service';

/**
 * Mantiene idioma y tema alineados con el perfil.
 * Al iniciar sesion manda el perfil; despues, cada cambio local se guarda en el perfil.
 */
@Injectable({ providedIn: 'root' })
export class PreferencesSyncService {
  private readonly auth = inject(AuthService);
  private readonly language = inject(LanguageService);
  private readonly theme = inject(ThemeService);
  private lastUserId: string | null = null;

  start(): void {
    // Perfil -> dispositivo, una vez por inicio de sesion.
    effect(() => {
      const user = this.auth.user();
      const userId = user?.id ?? null;
      if (!user || userId === this.lastUserId) {
        this.lastUserId = userId;
        return;
      }
      this.lastUserId = userId;
      untracked(() => {
        if (isLanguage(user.preferred_language)) this.language.set(user.preferred_language);
        this.theme.setPreference(user.theme_preference);
      });
    });

    // Dispositivo -> perfil, cuando el usuario cambia algo con la sesion abierta.
    effect(() => {
      const lang = this.language.current();
      const theme = this.theme.preference();
      const user = untracked(() => this.auth.user());
      // Hasta aplicar el perfil del usuario recien conectado no se escribe nada en el.
      if (!user || user.id !== this.lastUserId) return;
      if (user.preferred_language === lang && user.theme_preference === theme) return;
      void this.auth.updateMe({ preferred_language: lang, theme_preference: theme }).catch(() => {
        // Sin conexion la preferencia queda en el dispositivo y se reintenta en el proximo cambio.
      });
    });
  }
}
