import { TestBed } from '@angular/core/testing';
import { provideRouter, Router, UrlTree } from '@angular/router';
import { canPublishGuard } from '../../core/auth/auth.guards';
import { Me, PublishBlocker } from '../../core/auth/auth.models';
import { AuthService } from '../../core/auth/auth.service';
import { ME } from '../../core/auth/auth.service.spec';
import { getTranslocoTestingModule } from '../../../testing/transloco-testing';
import DriverHome from './driver-home';

function setup(blockers: PublishBlocker[]) {
  TestBed.configureTestingModule({
    imports: [DriverHome, getTranslocoTestingModule()],
    providers: [provideRouter([])],
  });
  const user: Me = {
    ...ME,
    role: 'driver',
    can_publish: blockers.length === 0,
    publish_blockers: blockers,
  };
  TestBed.inject(AuthService).user.set(user);
  const fixture = TestBed.createComponent(DriverHome);
  fixture.detectChanges();
  return fixture;
}

describe('DriverHome', () => {
  it('lista lo que falta y deja Publicar deshabilitado', () => {
    const fixture = setup(['license_pending', 'no_active_vehicle']);
    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Un administrador la está revisando.');
    expect(text).toContain('Agrega tu carro o moto');
    const publish = fixture.nativeElement.querySelector('button[disabled]') as HTMLButtonElement;
    expect(publish.textContent).toContain('Publicar');
    expect(publish.getAttribute('aria-describedby')).toBe('publish-locked');
  });

  it('con todo listo ofrece el enlace a publicar', () => {
    const fixture = setup([]);
    const link = fixture.nativeElement.querySelector('a[href="/publicar"]');
    expect(link).toBeTruthy();
  });
});

describe('canPublishGuard', () => {
  function run(canPublish: boolean): boolean | UrlTree {
    TestBed.configureTestingModule({ providers: [provideRouter([])] });
    TestBed.inject(AuthService).user.set({ ...ME, role: 'driver', can_publish: canPublish });
    return TestBed.runInInjectionContext(() => canPublishGuard({}, [], {} as never)) as
      boolean | UrlTree;
  }

  it('deja pasar si puede publicar', () => {
    expect(run(true)).toBe(true);
  });

  it('si no puede publicar lo lleva a su inicio', () => {
    const result = run(false);
    expect(TestBed.inject(Router).serializeUrl(result as UrlTree)).toBe('/inicio');
  });
});
