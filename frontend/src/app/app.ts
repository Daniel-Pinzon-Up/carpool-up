import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { PreferencesSyncService } from './core/auth/preferences-sync.service';
import { ThemeService } from './core/theme/theme.service';
import { ToastHost } from './shared/ui/toast-host';

@Component({
  selector: 'cp-root',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterOutlet, ToastHost],
  template: `
    <div class="app-backdrop" aria-hidden="true"><span></span></div>
    <router-outlet />
    <cp-toast-host />
  `,
})
export class App {
  constructor() {
    // Instancia el servicio de tema al arrancar para que siga los cambios del sistema.
    inject(ThemeService);
    inject(PreferencesSyncService).start();
  }
}
