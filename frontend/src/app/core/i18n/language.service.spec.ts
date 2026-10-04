import { TestBed } from '@angular/core/testing';
import { TranslocoService } from '@jsverse/transloco';
import { getTranslocoTestingModule } from '../../../testing/transloco-testing';
import { PREF_KEYS } from '../storage/local-preferences';
import { LanguageService, initialLanguage, isLanguage } from './language.service';

describe('LanguageService', () => {
  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({ imports: [getTranslocoTestingModule()] });
  });

  it('cambia el idioma activo, el atributo lang y lo persiste', () => {
    const service = TestBed.inject(LanguageService);
    service.set('en');
    expect(TestBed.inject(TranslocoService).getActiveLang()).toBe('en');
    expect(document.documentElement.lang).toBe('en');
    expect(localStorage.getItem(PREF_KEYS.lang)).toBe('en');
    expect(service.current()).toBe('en');
  });

  it('prefiere el idioma guardado', () => {
    localStorage.setItem(PREF_KEYS.lang, 'fr');
    expect(initialLanguage()).toBe('fr');
  });

  it('solo acepta los cuatro idiomas soportados', () => {
    expect(isLanguage('pt')).toBe(true);
    expect(isLanguage('de')).toBe(false);
  });
});
