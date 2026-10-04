import { DOCUMENT } from '@angular/common';
import { Injectable, inject, signal } from '@angular/core';
import { TranslocoService } from '@jsverse/transloco';
import { PREF_KEYS, readPref, writePref } from '../storage/local-preferences';

export const LANGUAGES = ['es', 'en', 'pt', 'fr'] as const;
export type Language = (typeof LANGUAGES)[number];
export const DEFAULT_LANGUAGE: Language = 'es';

export function isLanguage(value: unknown): value is Language {
  return LANGUAGES.includes(value as Language);
}

/** Idioma inicial: preferencia guardada, luego el navegador, luego espanol. */
export function initialLanguage(): Language {
  const saved = readPref(PREF_KEYS.lang);
  if (isLanguage(saved)) return saved;
  const browser = globalThis.navigator?.language?.slice(0, 2);
  return isLanguage(browser) ? browser : DEFAULT_LANGUAGE;
}

@Injectable({ providedIn: 'root' })
export class LanguageService {
  private readonly transloco = inject(TranslocoService);
  private readonly document = inject(DOCUMENT);

  readonly current = signal<Language>(this.transloco.getActiveLang() as Language);

  set(lang: Language): void {
    this.transloco.setActiveLang(lang);
    this.current.set(lang);
    this.document.documentElement.lang = lang;
    writePref(PREF_KEYS.lang, lang);
  }
}
