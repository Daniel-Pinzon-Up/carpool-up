import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { TranslocoPipe } from '@jsverse/transloco';
import {
  LucideCar,
  LucideCircle,
  LucideCircleCheck,
  LucideClock,
  LucideDynamicIcon,
  LucideIcon,
  LucideIdCard,
  LucideInbox,
  LucideSquarePlus,
  LucideTriangleAlert,
} from '@lucide/angular';
import { PublishBlocker } from '../../core/auth/auth.models';
import { AuthService } from '../../core/auth/auth.service';
import { GlassButton } from '../../shared/ui/glass-button';
import { GlassCard } from '../../shared/ui/glass-card';

type StepState = 'done' | 'waiting' | 'todo' | 'problem';

interface Requirement {
  key: 'license' | 'vehicle';
  state: StepState;
  detail: string; // clave de traduccion
  link: string;
  icon: LucideIcon;
}

const LICENSE_STATE: Partial<Record<PublishBlocker, [StepState, string]>> = {
  license_missing: ['todo', 'driverHome.license.missing'],
  license_pending: ['waiting', 'driverHome.license.pending'],
  license_rejected: ['problem', 'driverHome.license.rejected'],
  license_expired: ['problem', 'driverHome.license.expired'],
};

const STATE_ICON: Record<StepState, LucideIcon> = {
  done: LucideCircleCheck,
  waiting: LucideClock,
  todo: LucideCircle,
  problem: LucideTriangleAlert,
};

const STATE_TONE: Record<StepState, string> = {
  done: 'text-success',
  waiting: 'text-primary',
  todo: 'text-muted',
  problem: 'text-danger',
};

/** Inicio del conductor: que le falta para publicar y acceso directo a publicar. */
@Component({
  selector: 'cp-driver-home',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    RouterLink,
    TranslocoPipe,
    GlassButton,
    GlassCard,
    LucideDynamicIcon,
    LucideInbox,
    LucideSquarePlus,
  ],
  template: `
    <div class="mx-auto flex max-w-3xl flex-col gap-6 py-2">
      <header>
        <p class="text-muted">{{ 'account.hello' | transloco: { name: firstName() } }}</p>
        <h1 class="text-2xl font-bold sm:text-3xl">{{ 'driverHome.title' | transloco }}</h1>
      </header>

      <cp-glass-card [level]="2">
        @if (canPublish()) {
          <h2 class="mb-1 text-lg font-bold">{{ 'driverHome.ready.title' | transloco }}</h2>
          <p class="mb-5 text-muted">{{ 'driverHome.ready.body' | transloco }}</p>
          <div class="flex flex-wrap gap-3">
            <a cp-button size="lg" routerLink="/publicar">
              <svg lucideSquarePlus class="size-5" aria-hidden="true"></svg>
              {{ 'nav.publish' | transloco }}
            </a>
            <a cp-button size="lg" variant="secondary" routerLink="/solicitudes">
              <svg lucideInbox class="size-5" aria-hidden="true"></svg>
              {{ 'bookings.inbox.title' | transloco }}
            </a>
          </div>
        } @else {
          <h2 class="mb-1 text-lg font-bold">{{ 'driverHome.setup.title' | transloco }}</h2>
          <p class="mb-5 text-muted">{{ 'driverHome.setup.body' | transloco }}</p>
          <ol class="flex flex-col gap-3">
            @for (item of requirements(); track item.key) {
              <li>
                <a
                  [routerLink]="item.link"
                  class="glass-1 !rounded-2xl flex items-center gap-4 p-4 transition hover:bg-glass-strong"
                >
                  <span class="grid size-11 shrink-0 place-items-center rounded-xl bg-primary/15">
                    <svg
                      [lucideIcon]="item.icon"
                      class="size-6 text-primary"
                      aria-hidden="true"
                    ></svg>
                  </span>
                  <span class="min-w-0 flex-1">
                    <span class="block font-semibold">{{
                      'driverHome.' + item.key + '.title' | transloco
                    }}</span>
                    <span class="block text-sm text-muted">{{ item.detail | transloco }}</span>
                  </span>
                  <svg
                    [lucideIcon]="stateIcon(item.state)"
                    [class]="'size-6 shrink-0 ' + stateTone(item.state)"
                    aria-hidden="true"
                  ></svg>
                  <span class="sr-only">{{ 'driverHome.state.' + item.state | transloco }}</span>
                </a>
              </li>
            }
          </ol>
          <button
            cp-button
            size="lg"
            type="button"
            class="mt-5"
            [disabled]="true"
            aria-describedby="publish-locked"
          >
            <svg lucideSquarePlus class="size-5" aria-hidden="true"></svg>
            {{ 'nav.publish' | transloco }}
          </button>
          <p id="publish-locked" class="mt-2 text-sm text-muted">
            {{ 'driverHome.locked' | transloco }}
          </p>
        }
      </cp-glass-card>
    </div>
  `,
})
export default class DriverHome {
  private readonly auth = inject(AuthService);

  protected readonly canPublish = computed(() => this.auth.user()?.can_publish ?? false);
  protected readonly firstName = computed(() => this.auth.user()?.full_name.split(' ')[0] ?? '');
  protected readonly requirements = computed<Requirement[]>(() => {
    const blockers = this.auth.user()?.publish_blockers ?? [];
    const licenseBlocker = blockers.find((b) => b.startsWith('license_'));
    const [licenseState, licenseDetail] = licenseBlocker
      ? (LICENSE_STATE[licenseBlocker] ?? ['todo', 'driverHome.license.missing'])
      : ['done', 'driverHome.license.ok'];
    const vehicleMissing = blockers.includes('no_active_vehicle');
    return [
      {
        key: 'license',
        state: licenseState as StepState,
        detail: licenseDetail,
        link: '/licencia',
        icon: LucideIdCard,
      },
      {
        key: 'vehicle',
        state: vehicleMissing ? 'todo' : 'done',
        detail: vehicleMissing ? 'driverHome.vehicle.missing' : 'driverHome.vehicle.ok',
        link: '/vehiculos',
        icon: LucideCar,
      },
    ];
  });

  protected stateIcon(state: StepState): LucideIcon {
    return STATE_ICON[state];
  }

  protected stateTone(state: StepState): string {
    return STATE_TONE[state];
  }
}
