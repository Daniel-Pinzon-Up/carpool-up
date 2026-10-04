import { TestBed } from '@angular/core/testing';
import { PREF_KEYS } from '../storage/local-preferences';
import { ThemeService } from './theme.service';

describe('ThemeService', () => {
  const root = document.documentElement;

  beforeEach(() => {
    localStorage.clear();
    root.classList.remove('dark', 'reduce-transparency');
    TestBed.resetTestingModule();
  });

  it('usa el tema del sistema por defecto', () => {
    const service = TestBed.inject(ThemeService);
    expect(service.preference()).toBe('system');
  });

  it('aplica la clase dark en <html> y persiste la preferencia', () => {
    const service = TestBed.inject(ThemeService);
    service.setPreference('dark');
    TestBed.tick();
    expect(root.classList.contains('dark')).toBe(true);
    expect(localStorage.getItem(PREF_KEYS.theme)).toBe('dark');

    service.setPreference('light');
    TestBed.tick();
    expect(root.classList.contains('dark')).toBe(false);
  });

  it('lee la preferencia guardada al iniciar', () => {
    localStorage.setItem(PREF_KEYS.theme, 'dark');
    const service = TestBed.inject(ThemeService);
    expect(service.isDark()).toBe(true);
  });

  it('ignora valores guardados invalidos', () => {
    localStorage.setItem(PREF_KEYS.theme, 'neon');
    expect(TestBed.inject(ThemeService).preference()).toBe('system');
  });

  it('activa y persiste la reduccion de transparencia', () => {
    const service = TestBed.inject(ThemeService);
    service.setReduceTransparency(true);
    TestBed.tick();
    expect(root.classList.contains('reduce-transparency')).toBe(true);
    expect(localStorage.getItem(PREF_KEYS.reduceTransparency)).toBe('true');
  });
});
