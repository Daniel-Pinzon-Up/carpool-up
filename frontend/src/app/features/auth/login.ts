import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { TranslocoPipe, TranslocoService } from '@jsverse/transloco';
import { LucideCircleAlert, LucideLock, LucideMail } from '@icons';
import { homeFor } from '../../core/auth/auth.guards';
import { AuthService } from '../../core/auth/auth.service';
import { apiErrorMessage } from '../../core/http/api-error-message';
import { fieldError } from '../../shared/forms/validation';
import { GlassButton } from '../../shared/ui/glass-button';
import { GlassCard } from '../../shared/ui/glass-card';
import { GlassInput } from '../../shared/ui/glass-input';

@Component({
  selector: 'cp-login',
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
      <h1 class="mb-1 text-2xl font-bold">{{ 'login.title' | transloco }}</h1>
      <p class="mb-6 text-muted">{{ 'login.subtitle' | transloco }}</p>

      @if (error()) {
        <div role="alert" class="mb-5 flex gap-3 rounded-2xl bg-danger/10 p-4 text-sm text-danger">
          <svg lucideCircleAlert class="size-5 shrink-0" aria-hidden="true"></svg>
          <span>{{ error() }}</span>
        </div>
      }

      <form [formGroup]="form" (ngSubmit)="submit()" novalidate class="flex flex-col gap-4">
        <cp-glass-input
          formControlName="email"
          type="email"
          autocomplete="username"
          [icon]="icons.mail"
          [label]="'fields.email' | transloco"
          [error]="err('email')"
        />
        <cp-glass-input
          formControlName="password"
          type="password"
          autocomplete="current-password"
          [revealable]="true"
          [icon]="icons.lock"
          [label]="'fields.password' | transloco"
          [error]="err('password')"
        />
        <a
          routerLink="/recuperar"
          class="self-end rounded text-sm font-semibold text-primary underline-offset-4 hover:underline"
        >
          {{ 'login.forgot' | transloco }}
        </a>
        <button cp-button size="lg" [block]="true" type="submit" [loading]="busy()">
          {{ 'login.submit' | transloco }}
        </button>
      </form>

      <p class="mt-6 text-center text-sm text-muted">
        {{ 'login.noAccount' | transloco }}
        <a
          routerLink="/registro"
          class="font-semibold text-primary underline-offset-4 hover:underline"
        >
          {{ 'login.register' | transloco }}
        </a>
      </p>
    </cp-glass-card>
  `,
})
export default class Login {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly transloco = inject(TranslocoService);

  protected readonly icons = { mail: LucideMail, lock: LucideLock };
  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly submitted = signal(false);
  protected readonly form = inject(FormBuilder).nonNullable.group({
    email: ['', [Validators.required, Validators.email]],
    password: ['', Validators.required],
  });

  protected err(name: 'email' | 'password'): string | null {
    return fieldError(this.transloco, this.form.controls[name], this.submitted());
  }

  protected async submit(): Promise<void> {
    this.submitted.set(true);
    this.error.set(null);
    if (this.form.invalid || this.busy()) return;
    this.busy.set(true);
    try {
      const { email, password } = this.form.getRawValue();
      const result = await this.auth.login(email.trim(), password);
      await this.router.navigateByUrl(
        result.result === 'authenticated' ? homeFor(this.auth, this.router) : '/verificar',
      );
    } catch (error) {
      this.error.set(apiErrorMessage(this.transloco, error));
    } finally {
      this.busy.set(false);
    }
  }
}
