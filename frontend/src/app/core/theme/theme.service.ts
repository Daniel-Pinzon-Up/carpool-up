import { DOCUMENT } from '@angular/common';
import { DestroyRef, Injectable, computed, effect, inject, signal } from '@angular/core';
import { PREF_KEYS, readPref, writePref } from '../storage/local-preferences';

export type ThemePreference = 'system' | 'light' | 'dark';

const THEMES: readonly ThemePreference[] = ['system', 'light', 'dark'];

/**
 * Tema y transparencia. La clase inicial la pone el script de index.html;
 * este servicio la mantiene sincronizada. La sincronizacion con el perfil llega en el paso 2.
 */
@Injectable({ providedIn: 'root' })
export class ThemeService {
  private readonly document = inject(DOCUMENT);
  private readonly media = this.document.defaultView?.matchMedia?.('(prefers-color-scheme: dark)');
  private readonly systemDark = signal(this.media?.matches ?? false);

  readonly preference = signal<ThemePreference>(parseTheme(readPref(PREF_KEYS.theme)));
  readonly reduceTransparency = signal(readPref(PREF_KEYS.reduceTransparency) === 'true');
  readonly isDark = computed(() => {
    const pref = this.preference();
    return pref === 'dark' || (pref === 'system' && this.systemDark());
  });

  constructor() {
    const onChange = (event: MediaQueryListEvent) => this.systemDark.set(event.matches);
    this.media?.addEventListener('change', onChange);
    inject(DestroyRef).onDestroy(() => this.media?.removeEventListener('change', onChange));

    effect(() => {
      const root = this.document.documentElement;
      root.classList.toggle('dark', this.isDark());
      root.classList.toggle('reduce-transparency', this.reduceTransparency());
    });
  }

  setPreference(pref: ThemePreference): void {
    this.preference.set(pref);
    writePref(PREF_KEYS.theme, pref);
  }

  setReduceTransparency(value: boolean): void {
    this.reduceTransparency.set(value);
    writePref(PREF_KEYS.reduceTransparency, String(value));
  }
}

function parseTheme(value: string | null): ThemePreference {
  return THEMES.includes(value as ThemePreference) ? (value as ThemePreference) : 'system';
}
