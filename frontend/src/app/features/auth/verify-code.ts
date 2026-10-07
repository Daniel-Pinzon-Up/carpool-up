import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  computed,
  inject,
  signal,
} from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { TranslocoPipe, TranslocoService } from '@jsverse/transloco';
import { LucideCircleAlert, LucideMailCheck } from '@icons';
import { homeFor } from '../../core/auth/auth.guards';
import { AuthService } from '../../core/auth/auth.service';
import { apiErrorCode, apiErrorMessage } from '../../core/http/api-error-message';
import { MetaService } from '../../core/meta/meta.service';
import { fieldError } from '../../shared/forms/validation';
import { GlassButton } from '../../shared/ui/glass-button';
import { GlassCard } from '../../shared/ui/glass-card';
import { GlassInput } from '../../shared/ui/glass-input';
import { ToastService } from '../../shared/ui/toast.service';

/** Codigo de 6 digitos para verificar el correo o el segundo factor. */
@Component({
  selector: 'cp-verify-code',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    ReactiveFormsModule,
    RouterLink,
    TranslocoPipe,
    GlassCard,
    GlassInput,
    GlassButton,
    LucideMailCheck,
    LucideCircleAlert,
  ],
  template: `
    <cp-glass-card [level]="2" class="!p-6 sm:!p-8">
      @if (challenge(); as current) {
        <span class="mb-5 grid size-16 place-items-center rounded-2xl bg-accent/15">
          <svg lucideMailCheck class="size-8 text-accent" aria-hidden="true"></svg>
        </span>
        <h1 class="mb-1 text-2xl font-bold">
          {{ 'verify.' + current.purpose + '.title' | transloco }}
        </h1>
        <p class="mb-6 text-muted">
          {{ 'verify.sentTo' | transloco: { email: current.emailHint } }}
          {{ 'verify.' + current.purpose + '.why' | transloco }}
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
            [hint]="'verify.codeHint' | transloco: { minutes: codeMinutes() }"
            [error]="codeError()"
          />
          <button cp-button size="lg" [block]="true" type="submit" [loading]="busy()">
            {{ 'verify.submit' | transloco }}
          </button>
        </form>

        <div class="mt-6 flex flex-col items-center gap-2 text-sm">
          <button
            cp-button
            variant="ghost"
            type="button"
            [disabled]="secondsLeft() > 0 || resending()"
            [loading]="resending()"
            (click)="resend()"
          >
            @if (secondsLeft() > 0) {
              {{ 'verify.resendIn' | transloco: { seconds: secondsLeft() } }}
            } @else {
              {{ 'verify.resend' | transloco }}
            }
          </button>
          <p class="sr-only" aria-live="polite">{{ resendAnnouncement() }}</p>
          <a routerLink="/ingresar" class="text-muted underline underline-offset-4">
            {{ 'verify.backToLogin' | transloco }}
          </a>
        </div>
      } @else {
        <h1 class="mb-2 text-xl font-bold">{{ 'verify.expired.title' | transloco }}</h1>
        <p class="mb-6 text-muted">{{ 'verify.expired.body' | transloco }}</p>
        <a cp-button routerLink="/ingresar" [block]="true">{{
          'verify.backToLogin' | transloco
        }}</a>
      }
    </cp-glass-card>
  `,
})
export default class VerifyCode {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly transloco = inject(TranslocoService);
  private readonly toasts = inject(ToastService);

  protected readonly challenge = this.auth.challenge;
  private readonly meta = inject(MetaService);
  protected readonly codeMinutes = computed(() => this.meta.settings().auth_code_minutes);
  protected readonly busy = signal(false);
  protected readonly resending = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly submitted = signal(false);
  protected readonly resendAnnouncement = signal('');
  private readonly now = signal(Date.now());
  protected readonly secondsLeft = computed(() =>
    Math.max(0, Math.ceil(((this.challenge()?.resendAt ?? 0) - this.now()) / 1000)),
  );
  protected readonly form = inject(FormBuilder).nonNullable.group({
    code: ['', [Validators.required, Validators.pattern(/^\d{6}$/)]],
  });

  constructor() {
    void this.meta.load();
    // La recuperacion de contrasena pide el codigo junto con la clave nueva.
    if (this.challenge()?.purpose === 'password_reset')
      void this.router.navigateByUrl('/restablecer');
    const timer = setInterval(() => this.now.set(Date.now()), 1000);
    inject(DestroyRef).onDestroy(() => clearInterval(timer));
  }

  protected codeError(): string | null {
    return fieldError(this.transloco, this.form.controls.code, this.submitted());
  }

  protected async submit(): Promise<void> {
    this.submitted.set(true);
    this.error.set(null);
    if (this.form.invalid || this.busy()) return;
    this.busy.set(true);
    try {
      await this.auth.verifyCode(this.form.getRawValue().code.trim());
      await this.router.navigateByUrl(homeFor(this.auth, this.router));
    } catch (error) {
      this.error.set(apiErrorMessage(this.transloco, error));
      if (apiErrorCode(error) === 'CODE_INVALID') this.form.controls.code.reset('');
    } finally {
      this.busy.set(false);
    }
  }

  protected async resend(): Promise<void> {
    this.resending.set(true);
    this.error.set(null);
    try {
      await this.auth.resendCode();
      const message = this.transloco.translate('verify.resent');
      this.resendAnnouncement.set(message);
      this.toasts.show(message, 'success');
    } catch (error) {
      this.error.set(apiErrorMessage(this.transloco, error));
    } finally {
      this.resending.set(false);
    }
  }
}
