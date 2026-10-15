import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { Me } from '../auth/auth.models';
import { AuthService } from '../auth/auth.service';
import { getTranslocoTestingModule } from '../../../testing/transloco-testing';
import { NAV_BY_ROLE } from './navigation';
import { Shell } from './shell';

describe('Shell', () => {
  it('muestra los destinos del pasajero en la barra lateral y la inferior', () => {
    TestBed.configureTestingModule({
      imports: [Shell, getTranslocoTestingModule()],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    });
    const fixture = TestBed.createComponent(Shell);
    fixture.detectChanges();

    const navs = fixture.nativeElement.querySelectorAll('nav[aria-label="Navegación principal"]');
    expect(navs).toHaveLength(2);
    const bottomLinks = navs[1].querySelectorAll('a');
    expect(bottomLinks).toHaveLength(NAV_BY_ROLE.passenger.length);
    expect(bottomLinks[0].textContent).toContain('Buscar');
  });

  it('con mas de cinco destinos la barra inferior muestra cuatro y el menu Mas', () => {
    TestBed.configureTestingModule({
      imports: [Shell, getTranslocoTestingModule()],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    });
    TestBed.inject(AuthService).user.set({ id: 'u1', role: 'superadmin' } as Me);
    const fixture = TestBed.createComponent(Shell);
    fixture.detectChanges();

    const bottom = fixture.nativeElement.querySelectorAll(
      'nav[aria-label="Navegación principal"]',
    )[1];
    expect(bottom.querySelectorAll('a')).toHaveLength(4);
    const more = bottom.querySelector('button[aria-controls="cp-more-menu"]') as HTMLButtonElement;
    expect(more.getAttribute('aria-expanded')).toBe('false');

    more.click();
    fixture.detectChanges();
    const menu = fixture.nativeElement.querySelector('#cp-more-menu') as HTMLElement;
    const links = [...menu.querySelectorAll('a')].map((a) => a.getAttribute('href'));
    expect(links).toEqual(NAV_BY_ROLE.superadmin.slice(4).map((item) => item.path));
    expect(links).toContain('/admin/configuracion');

    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('#cp-more-menu')).toBeNull();
  });

  it('todos los roles llegan al perfil, donde se cierra la sesion', () => {
    for (const items of Object.values(NAV_BY_ROLE)) {
      expect(items.map((item) => item.path)).toContain('/perfil');
    }
  });

  it('solo el superadmin ve la configuracion en la navegacion', () => {
    expect(NAV_BY_ROLE.admin.some((item) => item.key === 'settings')).toBe(false);
    expect(NAV_BY_ROLE.superadmin.some((item) => item.key === 'settings')).toBe(true);
  });
});
