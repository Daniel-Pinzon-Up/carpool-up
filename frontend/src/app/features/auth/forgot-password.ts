import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { TranslocoPipe, TranslocoService } from '@jsverse/transloco';
import { LucideCircleAlert, LucideKeyRound, LucideMail } from '@icons';
import { AuthService } from '../../core/auth/auth.service';
import { apiErrorMessage } from '../../core/http/api-error-message';
import { fieldError } from '../../shared/forms/validation';
import { GlassButton } from '../../shared/ui/glass-button';
import { GlassCard } from '../../shared/ui/glass-card';
import { GlassInput } from '../../shared/ui/glass-input';

@Component({
  selector: 'cp-forgot-password',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    ReactiveFormsModule,
    RouterLink,
    TranslocoPipe,
    GlassCard,
    GlassInput,
    GlassButton,
    LucideKeyRound,
    LucideCircleAlert,
  ],
  template: `
    <cp-glass-card [level]="2" class="!p-6 sm:!p-8">
      <span class="mb-5 grid size-16 place-items-center rounded-2xl bg-primary/15">
        <svg lucideKeyRound class="size-8 text-primary" aria-hidden="true"></svg>
      </span>
      <h1 class="mb-1 text-2xl font-bold">{{ 'forgot.title' | transloco }}</h1>
      <p class="mb-6 text-muted">{{ 'forgot.subtitle' | transloco }}</p>
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
          autocomplete="email"
          [icon]="mailIcon"
          [label]="'fields.institutionalEmail' | transloco"
          [error]="emailError()"
        />
        <button cp-button size="lg" [block]="true" type="submit" [loading]="busy()">
          {{ 'forgot.submit' | transloco }}
        </button>
      </form>
      <p class="mt-6 text-center text-sm">
        <a routerLink="/ingresar" class="text-muted underline underline-offset-4">
          {{ 'verify.backToLogin' | transloco }}
        </a>
      </p>
    </cp-glass-card>
  `,
})
export default class ForgotPassword {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly transloco = inject(TranslocoService);

  protected readonly mailIcon = LucideMail;
  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly submitted = signal(false);
  protected readonly form = inject(FormBuilder).nonNullable.group({
    email: ['', [Validators.required, Validators.email]],
  });

  protected emailError(): string | null {
    return fieldError(this.transloco, this.form.controls.email, this.submitted());
  }

  protected async submit(): Promise<void> {
    this.submitted.set(true);
    this.error.set(null);
    if (this.form.invalid || this.busy()) return;
    this.busy.set(true);
    try {
      await this.auth.forgotPassword(this.form.getRawValue().email.trim());
      await this.router.navigateByUrl('/restablecer');
    } catch (error) {
      this.error.set(apiErrorMessage(this.transloco, error));
    } finally {
      this.busy.set(false);
    }
  }
}
