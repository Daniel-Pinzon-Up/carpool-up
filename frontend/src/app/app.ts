import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';
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
export class App {}
