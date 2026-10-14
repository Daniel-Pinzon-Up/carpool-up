import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  input,
  signal,
  untracked,
} from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { TranslocoPipe, TranslocoService } from '@jsverse/transloco';
import { LucideArrowLeft, LucideBan, LucideRotateCcw, LucideSearch, LucideUserX } from '@icons';
import { firstValueFrom } from 'rxjs';
import { AuthService } from '../../core/auth/auth.service';
import { UserRole } from '../../core/auth/auth.models';
import { apiErrorMessage } from '../../core/http/api-error-message';
import { LOCALE } from '../../core/i18n/locale';
import { DialogService } from '../../shared/ui/dialog.service';
import { EmptyState } from '../../shared/ui/empty-state';
import { ErrorState } from '../../shared/ui/error-state';
import { GlassButton } from '../../shared/ui/glass-button';
import { GlassCard } from '../../shared/ui/glass-card';
import { GlassInput } from '../../shared/ui/glass-input';
import { GlassSelect } from '../../shared/ui/glass-select';
import { Skeleton } from '../../shared/ui/skeleton';
import { BadgeTone, StatusBadge } from '../../shared/ui/status-badge';
import { ToastService } from '../../shared/ui/toast.service';
import { ReasonDialog, ReasonDialogData, ReasonResult } from '../bookings/reason-dialog';
import { StatTiles } from '../stats/stats-views';
import { SuspendDialog, SuspendResult } from './admin-dialogs';
import { AdminApi, AdminUserDetail, AdminUserRow } from './admin.api';

export const USER_STATUS_TONE: Record<string, BadgeTone> = {
  active: 'success',
  pending_email: 'neutral',
  pending_approval: 'pending',
  suspended: 'warning',
  blocked: 'danger',
};

function shortDate(iso: string | null, lang: string): string {
  return iso
    ? new Date(iso).toLocaleString(lang, {
        dateStyle: 'medium',
        timeStyle: 'short',
        timeZone: 'America/Bogota',
      })
    : '-';
}

/** Usuarios: busqueda por nombre o correo con filtros de rol y estado. */
@Component({
  selector: 'cp-admin-users',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    ReactiveFormsModule,
    RouterLink,
    TranslocoPipe,
    EmptyState,
    ErrorState,
    GlassButton,
    GlassCard,
    GlassInput,
    GlassSelect,
    Skeleton,
    StatusBadge,
    LucideSearch,
  ],
  template: `
    <div class="mx-auto flex max-w-5xl flex-col gap-5 py-2">
      <h1 class="text-2xl font-bold sm:text-3xl">{{ 'nav.users' | transloco }}</h1>
      <cp-glass-card>
        <form
          [formGroup]="filters"
          class="grid gap-3 sm:grid-cols-[1fr_12rem_12rem_auto] sm:items-end"
          (ngSubmit)="search()"
        >
          <cp-glass-input
            formControlName="q"
            type="search"
            [label]="'admin.users.search' | transloco"
          />
          <cp-glass-select
            formControlName="role"
            [label]="'admin.users.role' | transloco"
            [options]="roleOptions()"
          />
          <cp-glass-select
            formControlName="status"
            [label]="'admin.users.status' | transloco"
            [options]="statusOptions()"
          />
          <button cp-button type="submit">
            <svg lucideSearch class="size-4" aria-hidden="true"></svg>
            {{ 'search.submit' | transloco }}
          </button>
        </form>
      </cp-glass-card>
      @if (loadError(); as message) {
        <cp-glass-card><cp-error-state [message]="message" (retry)="search()" /></cp-glass-card>
      } @else if (rows() === null) {
        <cp-glass-card><cp-skeleton [lines]="5" /></cp-glass-card>
      } @else {
        <ul class="flex flex-col gap-2">
          @for (user of rows(); track user.id) {
            <li>
              <a
                [routerLink]="['/admin/usuarios', user.id]"
                class="glass-1 !rounded-2xl flex flex-wrap items-center gap-3 p-4 transition hover:bg-glass-strong"
              >
                <span class="min-w-0 flex-1">
                  <span class="block truncate font-semibold">{{ user.full_name }}</span>
                  <span class="block truncate text-sm text-muted">{{ user.email }}</span>
                </span>
                <span class="text-sm text-muted">{{ 'roles.' + user.role | transloco }}</span>
                <cp-status-badge [variant]="tone(user.status)">{{
                  'admin.users.statuses.' + user.status | transloco
                }}</cp-status-badge>
              </a>
            </li>
          } @empty {
            <li><cp-empty-state [title]="'admin.users.none' | transloco" /></li>
          }
        </ul>
        @if (cursor()) {
          <button
            cp-button
            variant="secondary"
            type="button"
            class="self-center"
            (click)="search(true)"
          >
            {{ 'trips.more' | transloco }}
          </button>
        }
      }
    </div>
  `,
})
export default class AdminUsers {
  private readonly api = inject(AdminApi);
  private readonly transloco = inject(TranslocoService);
  private readonly toast = inject(ToastService);

  protected readonly filters = new FormGroup({
    q: new FormControl('', { nonNullable: true }),
    role: new FormControl('', { nonNullable: true }),
    status: new FormControl('', { nonNullable: true }),
  });
  protected readonly rows = signal<AdminUserRow[] | null>(null);
  protected readonly loadError = signal<string | null>(null);
  protected readonly cursor = signal<string | null>(null);
  protected readonly roleOptions = computed(() => {
    return [
      { value: '', label: this.transloco.translate('admin.users.any') },
      ...['passenger', 'driver', 'admin', 'superadmin'].map((value) => ({
        value,
        label: this.transloco.translate(`admin.users.roles.${value}`),
      })),
    ];
  });
  protected readonly statusOptions = computed(() => {
    return [
      { value: '', label: this.transloco.translate('admin.users.any') },
      ...Object.keys(USER_STATUS_TONE).map((value) => ({
        value,
        label: this.transloco.translate(`admin.users.statuses.${value}`),
      })),
    ];
  });

  constructor() {
    void this.search();
  }

  protected async search(more = false): Promise<void> {
    if (!more) this.loadError.set(null);
    try {
      const page = await this.api.users({
        ...this.filters.getRawValue(),
        cursor: more ? this.cursor() : null,
      });
      this.rows.update((list) => (more ? [...(list ?? []), ...page.items] : page.items));
      this.cursor.set(page.next_cursor);
    } catch (error) {
      if (more) this.toast.show(apiErrorMessage(this.transloco, error), 'danger');
      else this.loadError.set(apiErrorMessage(this.transloco, error));
    }
  }

  protected tone(status: string): BadgeTone {
    return USER_STATUS_TONE[status] ?? 'neutral';
  }
}

/** Ficha de un usuario: datos, documentos, metricas, sanciones y acciones auditadas. */
@Component({
  selector: 'cp-admin-user-detail',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    ReactiveFormsModule,
    RouterLink,
    TranslocoPipe,
    GlassButton,
    GlassCard,
    ErrorState,
    GlassSelect,
    Skeleton,
    StatTiles,
    StatusBadge,
    LucideArrowLeft,
    LucideBan,
    LucideRotateCcw,
    LucideUserX,
  ],
  template: `
    <div class="mx-auto flex max-w-4xl flex-col gap-5 py-2">
      <a
        routerLink="/admin/usuarios"
        class="inline-flex min-h-11 items-center gap-2 self-start text-primary"
      >
        <svg lucideArrowLeft class="size-4" aria-hidden="true"></svg>
        {{ 'nav.users' | transloco }}
      </a>
      @if (user(); as u) {
        <header class="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 class="text-2xl font-bold">{{ u.full_name }}</h1>
            <p class="text-muted">{{ u.email }} · {{ 'roles.' + u.role | transloco }}</p>
            @if (u.program) {
              <p class="text-sm text-muted">{{ u.program }}</p>
            }
          </div>
          <cp-status-badge [variant]="tone(u.status)">{{
            'admin.users.statuses.' + u.status | transloco
          }}</cp-status-badge>
        </header>

        <cp-stat-tiles [tiles]="tiles()" />

        <cp-glass-card>
          <dl class="grid gap-3 text-sm sm:grid-cols-3">
            <div>
              <dt class="text-muted">{{ 'admin.users.document' | transloco }}</dt>
              <dd class="font-semibold">
                {{
                  (u.document_status
                    ? 'documentStatus.' + u.document_status
                    : 'admin.users.noDocument'
                  ) | transloco
                }}
              </dd>
            </div>
            @if (u.role === 'driver') {
              <div>
                <dt class="text-muted">{{ 'admin.users.license' | transloco }}</dt>
                <dd class="font-semibold">
                  {{
                    (u.license_status
                      ? 'documentStatus.' + u.license_status
                      : 'admin.users.noDocument'
                    ) | transloco
                  }}
                </dd>
              </div>
            }
            <div>
              <dt class="text-muted">{{ 'admin.users.lastLogin' | transloco }}</dt>
              <dd class="font-semibold">{{ date(u.last_login_at) }}</dd>
            </div>
          </dl>
        </cp-glass-card>

        @if (canManage()) {
          <cp-glass-card class="flex flex-col gap-3">
            <h2 class="font-semibold">{{ 'admin.users.actions' | transloco }}</h2>
            <div class="flex flex-wrap gap-2">
              @if (u.status === 'suspended' || u.status === 'blocked') {
                <button cp-button variant="secondary" type="button" (click)="reinstate()">
                  <svg lucideRotateCcw class="size-4" aria-hidden="true"></svg>
                  {{ 'admin.users.reinstate' | transloco }}
                </button>
              } @else {
                <button cp-button variant="secondary" type="button" (click)="suspend()">
                  <svg lucideUserX class="size-4" aria-hidden="true"></svg>
                  {{ 'admin.users.suspend' | transloco }}
                </button>
              }
              @if (u.status !== 'blocked') {
                <button cp-button variant="danger" type="button" (click)="block()">
                  <svg lucideBan class="size-4" aria-hidden="true"></svg>
                  {{ 'admin.users.block' | transloco }}
                </button>
              }
              @if (banned()) {
                <button cp-button variant="secondary" type="button" (click)="liftBan()">
                  {{ 'admin.users.liftBan' | transloco }}
                </button>
              }
            </div>
            @if (isSuperadmin() && u.role !== 'superadmin') {
              <form
                class="flex flex-wrap items-end gap-2"
                (submit)="$event.preventDefault(); changeRole()"
              >
                <cp-glass-select
                  class="w-56"
                  [formControl]="role"
                  [label]="'admin.users.changeRole' | transloco"
                  [options]="roleChoices()"
                />
                <button
                  cp-button
                  variant="secondary"
                  type="submit"
                  [disabled]="role.value === u.role"
                >
                  {{ 'admin.users.saveRole' | transloco }}
                </button>
              </form>
            }
            <p class="text-xs text-muted">{{ 'admin.audited' | transloco }}</p>
          </cp-glass-card>
        }

        <cp-glass-card>
          <h2 class="mb-2 font-semibold">{{ 'admin.users.suspensions' | transloco }}</h2>
          <ul class="flex flex-col gap-2 text-sm">
            @if (u.status === 'suspended') {
              <li class="rounded-xl bg-glass p-3">
                <span class="font-semibold">{{ 'admin.users.kinds.account' | transloco }}</span>
                →
                {{
                  u.suspended_until
                    ? date(u.suspended_until)
                    : ('admin.users.untilReinstated' | transloco)
                }}
                <span class="block text-muted">{{ u.suspension_reason }}</span>
              </li>
            }
            @if (banned()) {
              <li class="rounded-xl bg-glass p-3">
                <span class="font-semibold">{{ 'admin.users.kinds.booking_ban' | transloco }}</span>
                → {{ date(u.booking_ban_until) }}
              </li>
            }
            @if (u.status !== 'suspended' && !banned()) {
              <li class="text-muted">{{ 'admin.users.noSuspensions' | transloco }}</li>
            }
          </ul>
        </cp-glass-card>
      } @else if (loadError(); as message) {
        <cp-glass-card><cp-error-state [message]="message" (retry)="load(id())" /></cp-glass-card>
      } @else {
        <cp-glass-card><cp-skeleton [lines]="6" /></cp-glass-card>
      }
    </div>
  `,
})
export class AdminUserDetailPage {
  readonly id = input.required<string>();

  private readonly api = inject(AdminApi);
  private readonly auth = inject(AuthService);
  private readonly dialogs = inject(DialogService);
  private readonly transloco = inject(TranslocoService);
  private readonly toast = inject(ToastService);

  protected readonly user = signal<AdminUserDetail | null>(null);
  protected readonly loadError = signal<string | null>(null);
  protected readonly role = new FormControl<string>('', { nonNullable: true });
  protected readonly isSuperadmin = computed(() => this.auth.user()?.role === 'superadmin');
  /** Reservas suspendidas por ausencias todavia vigentes. */
  protected readonly banned = computed(() => {
    const until = this.user()?.booking_ban_until;
    return !!until && new Date(until).getTime() > Date.now();
  });
  protected readonly canManage = computed(() => {
    const target = this.user();
    const me = this.auth.user();
    if (!target || !me || target.id === me.id || target.role === 'superadmin') return false;
    return target.role !== 'admin' || me.role === 'superadmin';
  });
  protected readonly roleChoices = computed(() =>
    ['passenger', 'driver', 'admin'].map((value) => ({
      value,
      label: this.transloco.translate(`admin.users.roles.${value}`),
    })),
  );
  protected readonly tiles = computed(() => {
    const u = this.user();
    if (!u) return [];
    const t = (key: string) => this.transloco.translate(key);
    return [
      {
        label: t('admin.users.rating'),
        value: u.rating !== null ? `${u.rating.toLocaleString(LOCALE)} / 5` : '-',
        hint: this.transloco.translate('admin.users.ratingCount', { count: u.rating_count }),
      },
      {
        label: t('admin.users.tripsDriver'),
        value: String(u.trips_as_driver),
        hint: `${t('stats.driverCancellations')}: ${u.driver_cancellations}`,
      },
      {
        label: t('admin.users.tripsPassenger'),
        value: String(u.trips_as_passenger),
        hint: `${t('stats.noShows')}: ${u.passenger_no_shows}`,
      },
      { label: t('admin.users.active'), value: String(u.active_bookings + u.upcoming_trips) },
    ];
  });

  constructor() {
    effect(() => {
      const id = this.id();
      untracked(() => void this.load(id));
    });
  }

  protected async load(id: string): Promise<void> {
    this.loadError.set(null);
    try {
      const user = await this.api.user(id);
      this.user.set(user);
      this.role.setValue(user.role);
    } catch (error) {
      if (this.user()) this.toast.show(apiErrorMessage(this.transloco, error), 'danger');
      else this.loadError.set(apiErrorMessage(this.transloco, error));
    }
  }

  private async run(action: () => Promise<AdminUserDetail | unknown>, done: string): Promise<void> {
    try {
      const result = await action();
      if (result && typeof result === 'object' && 'booking_ban_until' in result) {
        this.user.set(result as AdminUserDetail);
      } else {
        await this.load(this.id());
      }
      this.toast.show(this.transloco.translate(done), 'success');
    } catch (error) {
      this.toast.show(apiErrorMessage(this.transloco, error), 'danger');
    }
  }

  private async reason(
    title: string,
    required: boolean,
    danger = true,
  ): Promise<ReasonResult | undefined> {
    const ref = this.dialogs.open<ReasonResult, ReasonDialogData, ReasonDialog>(ReasonDialog, {
      title: this.transloco.translate(title, { name: this.user()?.full_name }),
      message: this.transloco.translate('admin.users.reasonHelp'),
      confirmLabel: this.transloco.translate('common.confirm'),
      required,
      danger,
    });
    return firstValueFrom(ref.closed);
  }

  protected async suspend(): Promise<void> {
    const ref = this.dialogs.open<SuspendResult, { name: string }, SuspendDialog>(SuspendDialog, {
      name: this.user()?.full_name ?? '',
    });
    const result = await firstValueFrom(ref.closed);
    if (result)
      await this.run(
        () => this.api.suspend(this.id(), result.reason, result.days),
        'admin.users.suspended',
      );
  }

  protected async reinstate(): Promise<void> {
    const answer = await this.reason('admin.users.reinstateTitle', false, false);
    if (answer)
      await this.run(() => this.api.reinstate(this.id(), answer.reason), 'admin.users.reinstated');
  }

  protected async block(): Promise<void> {
    const answer = await this.reason('admin.users.blockTitle', true);
    if (answer?.reason)
      await this.run(() => this.api.block(this.id(), answer.reason!), 'admin.users.blocked');
  }

  protected async liftBan(): Promise<void> {
    const answer = await this.reason('admin.users.liftBanTitle', false, false);
    if (answer)
      await this.run(() => this.api.liftBan(this.id(), answer.reason), 'admin.users.banLifted');
  }

  protected async changeRole(): Promise<void> {
    const role = this.role.value as UserRole;
    const ok = await this.dialogs.confirm({
      title: this.transloco.translate('admin.users.changeRole'),
      message: this.transloco.translate('admin.users.changeRoleMessage', {
        name: this.user()?.full_name,
        role: this.transloco.translate(`admin.users.roles.${role}`),
      }),
      confirmLabel: this.transloco.translate('admin.users.saveRole'),
      cancelLabel: this.transloco.translate('common.cancel'),
    });
    if (ok) await this.run(() => this.api.changeRole(this.id(), role), 'admin.users.roleChanged');
  }

  protected tone(status: string): BadgeTone {
    return USER_STATUS_TONE[status] ?? 'neutral';
  }

  protected date(iso: string | null): string {
    return shortDate(iso, LOCALE);
  }
}
