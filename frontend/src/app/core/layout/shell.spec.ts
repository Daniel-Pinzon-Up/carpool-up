import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
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

  it('ningun rol tiene mas de cinco destinos en la barra inferior movil', () => {
    for (const items of [NAV_BY_ROLE.passenger, NAV_BY_ROLE.driver, NAV_BY_ROLE.admin]) {
      expect(items.length).toBeLessThanOrEqual(5);
    }
  });
});
