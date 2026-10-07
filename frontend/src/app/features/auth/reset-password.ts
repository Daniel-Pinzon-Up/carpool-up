import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { TranslocoPipe, TranslocoService } from '@jsverse/transloco';
import { LucideCircleAlert, LucideLock } from '@icons';
import { AuthService } from '../../core/auth/auth.service';
import { apiErrorMessage } from '../../core/http/api-error-message';
import { MetaService } from '../../core/meta/meta.service';
import { dynamicMinLength, fieldError, matchFields } from '../../shared/forms/validation';
import { GlassButton } from '../../shared/ui/glass-button';
import { GlassCard } from '../../shared/ui/glass-card';
import { GlassInput } from '../../shared/ui/glass-input';
import { ToastService } from '../../shared/ui/toast.service';

/** Codigo recibido por correo mas la contrasena nueva. Cierra todas las sesiones. */
@Component({
  selector: 'cp-reset-password',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    ReactiveFormsModule,
    RouterLink,
    TranslocoPipe,
    GlassCard,
    GlassInput,
    GlassButton,
    LucideCircleAlert,
  ],
  template: `
    <cp-glass-card [level]="2" class="!p-6 sm:!p-8">
      @if (auth.challenge(); as challenge) {
        <h1 class="mb-1 text-2xl font-bold">{{ 'reset.title' | transloco }}</h1>
        <p class="mb-6 text-muted">
          {{ 'verify.sentTo' | transloco: { email: challenge.emailHint } }}
          {{ 'reset.subtitle' | transloco }}
        </p>
        @if (error()) {
          <div
            role="alert"
            class="mb-5 flex gap-3 rounded-2xl bg-danger/10 p-4 text-sm text-danger"
          >
            <svg lucideCircleAlert class="size-5 shrink-0" aria-hidden="true"></svg>
            <span>{{ error() }}</span>
          </div>
        }
        <form [formGroup]="form" (ngSubmit)="submit()" novalidate class="flex flex-col gap-4">
          <cp-glass-input
            formControlName="code"
            inputmode="numeric"
            autocomplete="one-time-code"
            [maxlength]="6"
            [label]="'verify.code' | transloco"
            [error]="err('code')"
          />
          <cp-glass-input
            formControlName="password"
            type="password"
            autocomplete="new-password"
            [revealable]="true"
            [icon]="lockIcon"
            [label]="'fields.newPassword' | transloco"
            [hint]="'fields.passwordHint' | transloco: { min: meta.settings().password_min_length }"
            [error]="err('password')"
          />
          <cp-glass-input
            formControlName="confirm"
            type="password"
            autocomplete="new-password"
            [revealable]="true"
            [icon]="lockIcon"
            [label]="'fields.confirmPassword' | transloco"
            [error]="err('confirm')"
          />
          <p class="text-sm text-muted">{{ 'reset.sessionsNote' | transloco }}</p>
          <button cp-button size="lg" [block]="true" type="submit" [loading]="busy()">
            {{ 'reset.submit' | transloco }}
          </button>
        </form>
      } @else {
        <h1 class="mb-2 text-xl font-bold">{{ 'verify.expired.title' | transloco }}</h1>
        <p class="mb-6 text-muted">{{ 'verify.expired.body' | transloco }}</p>
        <a cp-button routerLink="/recuperar" [block]="true">{{ 'forgot.submit' | transloco }}</a>
      }
    </cp-glass-card>
  `,
})
export default class ResetPassword {
  protected readonly auth = inject(AuthService);
  protected readonly meta = inject(MetaService);
  private readonly router = inject(Router);
  private readonly transloco = inject(TranslocoService);
  private readonly toasts = inject(ToastService);

  protected readonly lockIcon = LucideLock;
  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly submitted = signal(false);
  protected readonly form = inject(FormBuilder).nonNullable.group(
    {
      code: ['', [Validators.required, Validators.pattern(/^\d{6}$/)]],
      password: [
        '',
        [Validators.required, dynamicMinLength(() => this.meta.settings().password_min_length)],
      ],
      confirm: ['', Validators.required],
    },
    { validators: matchFields('password', 'confirm') },
  );

  constructor() {
    void this.meta.load();
  }

  protected err(name: 'code' | 'password' | 'confirm'): string | null {
    return fieldError(this.transloco, this.form.controls[name], this.submitted());
  }

  protected async submit(): Promise<void> {
    this.submitted.set(true);
    this.error.set(null);
    if (this.form.invalid || this.busy()) return;
    this.busy.set(true);
    try {
      const { code, password } = this.form.getRawValue();
      await this.auth.resetPassword(code.trim(), password);
      this.toasts.show(this.transloco.translate('reset.done'), 'success');
      await this.router.navigateByUrl('/ingresar');
    } catch (error) {
      this.error.set(apiErrorMessage(this.transloco, error));
    } finally {
      this.busy.set(false);
    }
  }
}
