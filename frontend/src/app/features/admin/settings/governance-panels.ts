import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { TranslocoPipe, TranslocoService } from '@jsverse/transloco';
import { LucideSearch, LucideUserPlus } from '@icons';
import { apiErrorMessage } from '../../../core/http/api-error-message';
import { LOCALE } from '../../../core/i18n/locale';
import { EmptyState } from '../../../shared/ui/empty-state';
import { ErrorState } from '../../../shared/ui/error-state';
import { GlassButton } from '../../../shared/ui/glass-button';
import { GlassCard } from '../../../shared/ui/glass-card';
import { GlassInput } from '../../../shared/ui/glass-input';
import { GlassSelect } from '../../../shared/ui/glass-select';
import { ToastService } from '../../../shared/ui/toast.service';
import { AdminApi, AdminUserRow, AuditEntry } from '../admin.api';

function dateTime(iso: string, lang: string): string {
  return new Date(iso).toLocaleString(lang, {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: 'America/Bogota',
  });
}

/** Administradores: alta de cuentas nuevas. El cambio de rol se hace en la ficha del usuario. */
@Component({
  selector: 'cp-admins-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    ReactiveFormsModule,
    RouterLink,
    TranslocoPipe,
    GlassButton,
    GlassCard,
    GlassInput,
    GlassSelect,
    LucideUserPlus,
  ],
  template: `
    <div class="flex flex-col gap-3">
      <cp-glass-card>
        <form [formGroup]="form" class="grid gap-3 sm:grid-cols-2" (ngSubmit)="create()" novalidate>
          <cp-glass-input
            formControlName="full_name"
            autocomplete="off"
            [label]="'fields.fullName' | transloco"
            [error]="error('full_name')"
          />
          <cp-glass-input
            formControlName="email"
            type="email"
            autocomplete="off"
            [label]="'fields.email' | transloco"
            [error]="error('email')"
          />
          <cp-glass-select
            formControlName="sex"
            [label]="'fields.sex' | transloco"
            [options]="sexes()"
          />
          <cp-glass-input
            formControlName="password"
            type="password"
            autocomplete="new-password"
            [revealable]="true"
            [label]="'admin.admins.password' | transloco"
            [hint]="'admin.admins.passwordHint' | transloco"
            [error]="error('password')"
          />
          <div class="sm:col-span-2">
            <button cp-button type="submit">
              <svg lucideUserPlus class="size-4" aria-hidden="true"></svg>
              {{ 'admin.admins.create' | transloco }}
            </button>
          </div>
        </form>
      </cp-glass-card>
      <ul class="flex flex-col gap-2">
        @for (a of admins(); track a.id) {
          <li>
            <a
              [routerLink]="['/admin/usuarios', a.id]"
              class="glass-1 !rounded-2xl flex flex-wrap items-center gap-3 p-4 transition hover:bg-glass-strong"
            >
              <span class="min-w-0 flex-1 truncate font-semibold">{{ a.full_name }}</span>
              <span class="text-sm text-muted">{{ a.email }}</span>
            </a>
          </li>
        }
      </ul>
    </div>
  `,
})
export class AdminsPanel {
  private readonly api = inject(AdminApi);
  private readonly transloco = inject(TranslocoService);
  private readonly toast = inject(ToastService);

  protected readonly admins = signal<AdminUserRow[]>([]);
  private readonly submitted = signal(false);
  protected readonly form = new FormGroup({
    full_name: new FormControl('', {
      nonNullable: true,
      validators: [Validators.required, Validators.minLength(3)],
    }),
    email: new FormControl('', {
      nonNullable: true,
      validators: [Validators.required, Validators.email],
    }),
    sex: new FormControl<'female' | 'male'>('female', { nonNullable: true }),
    password: new FormControl('', { nonNullable: true, validators: Validators.required }),
  });
  protected readonly sexes = computed(() => {
    return (['female', 'male'] as const).map((value) => ({
      value,
      label: this.transloco.translate(`fields.sexOptions.${value}`),
    }));
  });

  constructor() {
    void this.load();
  }

  private async load(): Promise<void> {
    try {
      this.admins.set((await this.api.users({ role: 'admin' })).items);
    } catch (error) {
      this.toast.show(apiErrorMessage(this.transloco, error), 'danger');
    }
  }

  protected error(name: keyof typeof this.form.controls): string | null {
    return this.submitted() && this.form.controls[name].invalid
      ? this.transloco.translate('admin.settings.required')
      : null;
  }

  protected async create(): Promise<void> {
    this.submitted.set(true);
    if (this.form.invalid) return;
    const value = this.form.getRawValue();
    try {
      await this.api.createAdmin({ ...value, email: value.email.trim().toLowerCase() });
      this.toast.show(
        this.transloco.translate('admin.admins.created', { name: value.full_name }),
        'success',
      );
      this.submitted.set(false);
      this.form.reset();
      await this.load();
    } catch (error) {
      this.toast.show(apiErrorMessage(this.transloco, error), 'danger');
    }
  }
}

/** Auditoria: cada accion administrativa con quien, que, sobre que y el antes y despues. */
@Component({
  selector: 'cp-audit-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    ReactiveFormsModule,
    TranslocoPipe,
    EmptyState,
    ErrorState,
    GlassButton,
    GlassCard,
    GlassInput,
    LucideSearch,
  ],
  template: `
    <div class="flex flex-col gap-3">
      <cp-glass-card>
        <form
          [formGroup]="filters"
          class="grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end"
          (ngSubmit)="load()"
        >
          <cp-glass-input
            formControlName="action"
            [label]="'admin.audit.action' | transloco"
            hint="user.suspend"
          />
          <cp-glass-input
            formControlName="entity"
            [label]="'admin.audit.entity' | transloco"
            hint="user"
          />
          <button cp-button type="submit">
            <svg lucideSearch class="size-4" aria-hidden="true"></svg>
            {{ 'search.submit' | transloco }}
          </button>
        </form>
      </cp-glass-card>
      @if (loadError(); as message) {
        <cp-glass-card><cp-error-state [message]="message" (retry)="load()" /></cp-glass-card>
      }
      <ul class="flex flex-col gap-2">
        @for (entry of items(); track entry.id) {
          <li class="glass-1 !rounded-2xl p-4 text-sm">
            <details>
              <summary class="flex min-h-11 cursor-pointer flex-wrap items-center gap-x-3 gap-y-1">
                <span class="font-mono font-semibold">{{ entry.action }}</span>
                <span class="text-muted">{{ entry.entity }}</span>
                <span class="flex-1">{{
                  entry.actor_name ?? ('admin.audit.system' | transloco)
                }}</span>
                <span class="text-muted">{{ when(entry.created_at) }}</span>
              </summary>
              <div class="mt-2 grid gap-2 sm:grid-cols-2">
                <div>
                  <p class="font-semibold">{{ 'admin.audit.before' | transloco }}</p>
                  <pre
                    class="overflow-x-auto whitespace-pre-wrap break-words rounded-xl bg-glass p-2 font-mono text-xs"
                    >{{ json(entry.before) }}</pre>
                </div>
                <div>
                  <p class="font-semibold">{{ 'admin.audit.after' | transloco }}</p>
                  <pre
                    class="overflow-x-auto whitespace-pre-wrap break-words rounded-xl bg-glass p-2 font-mono text-xs"
                    >{{ json(entry.after) }}</pre>
                </div>
                @if (entry.entity_id) {
                  <p class="text-muted sm:col-span-2">
                    ID: <span class="font-mono">{{ entry.entity_id }}</span>
                  </p>
                }
              </div>
            </details>
          </li>
        } @empty {
          @if (!loadError()) {
            <li><cp-empty-state [title]="'admin.audit.none' | transloco" /></li>
          }
        }
      </ul>
      @if (cursor()) {
        <button
          cp-button
          variant="secondary"
          type="button"
          class="self-center"
          (click)="load(true)"
        >
          {{ 'trips.more' | transloco }}
        </button>
      }
    </div>
  `,
})
export class AuditPanel {
  private readonly api = inject(AdminApi);
  private readonly transloco = inject(TranslocoService);
  private readonly toast = inject(ToastService);

  protected readonly filters = new FormGroup({
    action: new FormControl('', { nonNullable: true }),
    entity: new FormControl('', { nonNullable: true }),
  });
  protected readonly items = signal<AuditEntry[]>([]);
  protected readonly loadError = signal<string | null>(null);
  protected readonly cursor = signal<string | null>(null);

  constructor() {
    void this.load();
  }

  protected async load(more = false): Promise<void> {
    const { action, entity } = this.filters.getRawValue();
    if (!more) this.loadError.set(null);
    try {
      const page = await this.api.audit({
        action: action.trim(),
        entity: entity.trim(),
        cursor: more ? this.cursor() : null,
      });
      this.items.update((list) => (more ? [...list, ...page.items] : page.items));
      this.cursor.set(page.next_cursor);
    } catch (error) {
      if (more) this.toast.show(apiErrorMessage(this.transloco, error), 'danger');
      else {
        this.items.set([]);
        this.loadError.set(apiErrorMessage(this.transloco, error));
      }
    }
  }

  protected json(value: Record<string, unknown> | null): string {
    return value ? JSON.stringify(value, null, 2) : '-';
  }

  protected when(iso: string): string {
    return dateTime(iso, LOCALE);
  }
}
