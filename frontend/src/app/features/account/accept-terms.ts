import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { TranslocoPipe, TranslocoService } from '@jsverse/transloco';
import { LucideCircleAlert, LucideScrollText } from '@icons';
import { homeFor } from '../../core/auth/auth.guards';
import { AuthService } from '../../core/auth/auth.service';
import { apiErrorMessage } from '../../core/http/api-error-message';
import { fieldError } from '../../shared/forms/validation';
import { GlassButton } from '../../shared/ui/glass-button';
import { GlassCard } from '../../shared/ui/glass-card';
import { GlassCheckbox } from '../../shared/ui/glass-checkbox';

/** Aparece cuando se publica una version nueva de los terminos o de la politica de datos. */
@Component({
  selector: 'cp-accept-terms',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    ReactiveFormsModule,
    RouterLink,
    TranslocoPipe,
    GlassCard,
    GlassButton,
    GlassCheckbox,
    LucideScrollText,
    LucideCircleAlert,
  ],
  template: `
    <cp-glass-card [level]="2" class="!p-6 sm:!p-8">
      <span class="mb-5 grid size-16 place-items-center rounded-2xl bg-primary/15">
        <svg lucideScrollText class="size-8 text-primary" aria-hidden="true"></svg>
      </span>
      <h1 class="mb-1 text-2xl font-bold">{{ 'acceptTerms.title' | transloco }}</h1>
      <p class="mb-5 text-muted">{{ 'acceptTerms.body' | transloco }}</p>
      <ul class="mb-5 flex flex-col gap-2">
        @for (doc of pending(); track doc.id) {
          <li>
            <a
              [routerLink]="['/legal', doc.kind === 'terms' ? 'terminos' : 'datos']"
              target="_blank"
              class="font-semibold text-primary underline underline-offset-4"
            >
              {{ (doc.kind === 'terms' ? 'legal.terms' : 'legal.dataPolicy') | transloco }}
            </a>
            <span class="text-sm text-muted">
              ({{ 'acceptTerms.version' | transloco: { version: doc.version } }})
            </span>
          </li>
        }
      </ul>
      @if (error()) {
        <div role="alert" class="mb-4 flex gap-3 rounded-2xl bg-danger/10 p-4 text-sm text-danger">
          <svg lucideCircleAlert class="size-5 shrink-0" aria-hidden="true"></svg>
          <span>{{ error() }}</span>
        </div>
      }
      <form [formGroup]="form" (ngSubmit)="accept()" novalidate class="flex flex-col gap-5">
        <cp-glass-checkbox formControlName="accepted" [error]="acceptedError()">
          {{ 'acceptTerms.checkbox' | transloco }}
        </cp-glass-checkbox>
        <button cp-button type="submit" [block]="true" [loading]="busy()">
          {{ 'acceptTerms.submit' | transloco }}
        </button>
      </form>
    </cp-glass-card>
  `,
})
export default class AcceptTerms {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly transloco = inject(TranslocoService);

  protected readonly pending = computed(() => this.auth.user()?.pending_legal ?? []);
  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly submitted = signal(false);
  protected readonly form = inject(FormBuilder).nonNullable.group({
    accepted: [false, Validators.requiredTrue],
  });

  protected acceptedError(): string | null {
    return fieldError(this.transloco, this.form.controls.accepted, this.submitted());
  }

  protected async accept(): Promise<void> {
    this.submitted.set(true);
    this.error.set(null);
    if (this.form.invalid || this.busy()) return;
    this.busy.set(true);
    try {
      await this.auth.acceptLegal(this.pending().map((doc) => doc.id));
      await this.router.navigateByUrl(homeFor(this.auth, this.router));
    } catch (error) {
      this.error.set(apiErrorMessage(this.transloco, error));
    } finally {
      this.busy.set(false);
    }
  }
}
