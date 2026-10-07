import { HttpClient } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { TranslocoPipe, TranslocoService } from '@jsverse/transloco';
import { LucideCircleAlert, LucideIdCard } from '@icons';
import { firstValueFrom } from 'rxjs';
import { LicenseSummary } from '../../core/auth/auth.models';
import { AuthService } from '../../core/auth/auth.service';
import { apiErrorMessage } from '../../core/http/api-error-message';
import { MetaService } from '../../core/meta/meta.service';
import { fieldError } from '../../shared/forms/validation';
import { FileDrop } from '../../shared/ui/file-drop';
import { GlassButton } from '../../shared/ui/glass-button';
import { GlassCard } from '../../shared/ui/glass-card';
import { GlassInput } from '../../shared/ui/glass-input';
import { BadgeTone, StatusBadge } from '../../shared/ui/status-badge';
import { ToastService } from '../../shared/ui/toast.service';

const TONES: Record<string, BadgeTone> = {
  pending: 'pending',
  approved: 'success',
  rejected: 'danger',
  expired: 'warning',
};

/** Licencia de conduccion del conductor: estado, vigencia y carga o reemplazo. */
@Component({
  selector: 'cp-license-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    ReactiveFormsModule,
    TranslocoPipe,
    FileDrop,
    GlassButton,
    GlassCard,
    GlassInput,
    StatusBadge,
    LucideIdCard,
    LucideCircleAlert,
  ],
  template: `
    <div class="mx-auto flex max-w-2xl flex-col gap-6 py-2">
      <header class="flex items-center gap-4">
        <span class="grid size-14 shrink-0 place-items-center rounded-2xl bg-primary/15">
          <svg lucideIdCard class="size-7 text-primary" aria-hidden="true"></svg>
        </span>
        <div>
          <h1 class="text-2xl font-bold sm:text-3xl">{{ 'license.title' | transloco }}</h1>
          <p class="text-muted">{{ 'license.subtitle' | transloco }}</p>
        </div>
      </header>

      <cp-glass-card>
        <h2 class="mb-3 text-lg font-bold">{{ 'license.statusTitle' | transloco }}</h2>
        @if (license(); as current) {
          <div class="flex flex-wrap items-center gap-3">
            <cp-status-badge [variant]="tone()">{{
              'documentStatus.' + current.status | transloco
            }}</cp-status-badge>
            <span class="text-sm text-muted">
              {{ 'license.validUntil' | transloco: { date: formatDate(current.expires_on) } }}
            </span>
          </div>
          @if (current.status === 'rejected' && current.rejection_reason) {
            <p class="mt-4 rounded-2xl bg-danger/10 p-4 text-sm">
              <span class="font-semibold">{{ 'account.reason' | transloco }}:</span>
              {{ current.rejection_reason }}
            </p>
          }
          <p class="mt-4 text-sm text-muted">{{ 'license.state.' + current.status | transloco }}</p>
        } @else {
          <p class="text-muted">{{ 'license.none' | transloco }}</p>
        }
      </cp-glass-card>

      <cp-glass-card>
        <h2 class="mb-1 text-lg font-bold">
          {{ (license() ? 'license.replaceTitle' : 'license.uploadTitle') | transloco }}
        </h2>
        <p class="mb-4 text-sm text-muted">{{ 'license.help' | transloco }}</p>
        @if (error()) {
          <div
            role="alert"
            class="mb-4 flex gap-3 rounded-2xl bg-danger/10 p-4 text-sm text-danger"
          >
            <svg lucideCircleAlert class="size-5 shrink-0" aria-hidden="true"></svg>
            <span>{{ error() }}</span>
          </div>
        }
        <form [formGroup]="form" (ngSubmit)="submit()" novalidate class="flex flex-col gap-4">
          <cp-glass-input
            formControlName="expires_on"
            type="date"
            [label]="'license.expiresOn' | transloco"
            [hint]="'license.expiresHint' | transloco"
            [error]="err('expires_on')"
          />
          <cp-file-drop
            formControlName="file"
            [label]="'license.file' | transloco"
            [maxMb]="meta.settings().max_upload_mb"
            [typeError]="'errors.FILE_TYPE_NOT_ALLOWED' | transloco"
            [sizeError]="
              'errors.FILE_TOO_LARGE' | transloco: { max_mb: meta.settings().max_upload_mb }
            "
            [error]="err('file')"
          />
          <p class="text-sm text-muted">{{ 'license.declaration' | transloco }}</p>
          <button cp-button type="submit" [loading]="busy()" class="self-start">
            {{ 'license.send' | transloco }}
          </button>
        </form>
      </cp-glass-card>
    </div>
  `,
})
export default class LicensePage {
  private readonly http = inject(HttpClient);
  private readonly auth = inject(AuthService);
  private readonly transloco = inject(TranslocoService);
  private readonly toasts = inject(ToastService);
  protected readonly meta = inject(MetaService);

  protected readonly license = computed<LicenseSummary | null>(
    () => this.auth.user()?.license ?? null,
  );
  protected readonly tone = computed(() => TONES[this.license()?.status ?? ''] ?? 'neutral');
  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly submitted = signal(false);
  protected readonly form = inject(FormBuilder).nonNullable.group({
    expires_on: ['', Validators.required],
    file: inject(FormBuilder).control<File | null>(null, Validators.required),
  });

  constructor() {
    void this.meta.load();
  }

  protected err(name: 'expires_on' | 'file'): string | null {
    return fieldError(this.transloco, this.form.controls[name], this.submitted());
  }

  protected formatDate(iso: string): string {
    return new Date(`${iso}T12:00:00`).toLocaleDateString(this.transloco.getActiveLang(), {
      dateStyle: 'long',
    });
  }

  protected async submit(): Promise<void> {
    this.submitted.set(true);
    this.error.set(null);
    if (this.form.invalid || this.busy()) return;
    this.busy.set(true);
    try {
      const { expires_on, file } = this.form.getRawValue();
      const data = new FormData();
      data.append('expires_on', expires_on);
      data.append('document', file as File);
      await firstValueFrom(this.http.put<LicenseSummary>('/api/v1/users/me/license', data));
      await this.auth.reloadMe();
      this.form.reset();
      this.submitted.set(false);
      this.toasts.show(this.transloco.translate('license.sent'), 'success');
    } catch (error) {
      this.error.set(apiErrorMessage(this.transloco, error));
    } finally {
      this.busy.set(false);
    }
  }
}
