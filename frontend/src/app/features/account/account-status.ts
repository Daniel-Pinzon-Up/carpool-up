import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { TranslocoPipe, TranslocoService } from '@jsverse/transloco';
import {
  LucideBan,
  LucideBriefcase,
  LucideCalendarX,
  LucideCircleAlert,
  LucideClock,
  LucideDynamicIcon,
  LucideFileWarning,
  LucideGraduationCap,
  LucideIcon,
  LucideLogOut,
  LucideRefreshCw,
} from '@lucide/angular';
import { homeFor } from '../../core/auth/auth.guards';
import { AuthService } from '../../core/auth/auth.service';
import { DocKind } from '../../core/auth/auth.models';
import { apiErrorMessage } from '../../core/http/api-error-message';
import { MetaService } from '../../core/meta/meta.service';
import { fieldError } from '../../shared/forms/validation';
import { Choice, ChoiceCards } from '../../shared/ui/choice-cards';
import { FileDrop } from '../../shared/ui/file-drop';
import { GlassButton } from '../../shared/ui/glass-button';
import { GlassCard } from '../../shared/ui/glass-card';
import { ToastService } from '../../shared/ui/toast.service';

type Situation = 'review' | 'rejected' | 'expired' | 'missing' | 'suspended';

const ICONS: Record<Situation, LucideIcon> = {
  review: LucideClock,
  rejected: LucideFileWarning,
  expired: LucideCalendarX,
  missing: LucideFileWarning,
  suspended: LucideBan,
};

/**
 * Lo unico que ve una cuenta que aun no esta activa: su estado, que sigue
 * y como subir o reemplazar su carnet o constancia.
 */
@Component({
  selector: 'cp-account-status',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    ReactiveFormsModule,
    TranslocoPipe,
    GlassCard,
    GlassButton,
    ChoiceCards,
    FileDrop,
    LucideDynamicIcon,
    LucideCircleAlert,
    LucideRefreshCw,
    LucideLogOut,
  ],
  template: `
    <cp-glass-card [level]="2" class="!p-6 sm:!p-8">
      <div class="flex flex-col items-center text-center" aria-live="polite">
        <span class="mb-5 grid size-20 place-items-center rounded-3xl" [class]="tone()">
          <svg [lucideIcon]="icon()" class="size-10" aria-hidden="true"></svg>
        </span>
        <p class="text-sm font-semibold text-muted">
          {{ 'account.hello' | transloco: { name: firstName() } }}
        </p>
        <h1 class="mb-2 text-2xl font-bold">
          {{ 'account.' + situation() + '.title' | transloco }}
        </h1>
        <p class="max-w-md text-muted">{{ 'account.' + situation() + '.body' | transloco }}</p>
        @if (situation() === 'rejected' && reason()) {
          <p class="mt-4 w-full rounded-2xl bg-danger/10 p-4 text-left text-sm">
            <span class="font-semibold">{{ 'account.reason' | transloco }}:</span> {{ reason() }}
          </p>
        }
      </div>

      @if (situation() !== 'suspended') {
        <section class="mt-8" aria-labelledby="upload-title">
          <h2 id="upload-title" class="mb-1 font-bold">
            {{
              (situation() === 'review' ? 'account.replaceTitle' : 'account.uploadTitle')
                | transloco
            }}
          </h2>
          <p class="mb-4 text-sm text-muted">{{ 'register.document.privacy' | transloco }}</p>
          @if (error()) {
            <div
              role="alert"
              class="mb-4 flex gap-3 rounded-2xl bg-danger/10 p-4 text-sm text-danger"
            >
              <svg lucideCircleAlert class="size-5 shrink-0" aria-hidden="true"></svg>
              <span>{{ error() }}</span>
            </div>
          }
          <form [formGroup]="form" (ngSubmit)="upload()" novalidate class="flex flex-col gap-4">
            <cp-choice-cards
              formControlName="kind"
              [label]="'register.document.label' | transloco"
              [choices]="docChoices()"
              [error]="err('kind')"
            />
            <cp-file-drop
              formControlName="file"
              [label]="'register.document.file' | transloco"
              [maxMb]="meta.settings().max_upload_mb"
              [typeError]="'errors.FILE_TYPE_NOT_ALLOWED' | transloco"
              [sizeError]="
                'errors.FILE_TOO_LARGE' | transloco: { max_mb: meta.settings().max_upload_mb }
              "
              [error]="err('file')"
            />
            <button cp-button type="submit" [loading]="busy()">
              {{ 'account.send' | transloco }}
            </button>
          </form>
        </section>
      }

      <div class="mt-8 flex flex-col gap-3 sm:flex-row sm:justify-between">
        <button
          cp-button
          variant="secondary"
          type="button"
          [loading]="checking()"
          (click)="check()"
        >
          <svg lucideRefreshCw class="size-4" aria-hidden="true"></svg>
          {{ 'account.check' | transloco }}
        </button>
        <button cp-button variant="ghost" type="button" (click)="logout()">
          <svg lucideLogOut class="size-4" aria-hidden="true"></svg>
          {{ 'profile.logout' | transloco }}
        </button>
      </div>
    </cp-glass-card>
  `,
})
export default class AccountStatus {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly transloco = inject(TranslocoService);
  private readonly toasts = inject(ToastService);
  protected readonly meta = inject(MetaService);

  protected readonly busy = signal(false);
  protected readonly checking = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly submitted = signal(false);
  protected readonly form = inject(FormBuilder).nonNullable.group({
    kind: [this.auth.user()?.document?.kind ?? '', Validators.required],
    file: inject(FormBuilder).control<File | null>(null, Validators.required),
  });

  protected readonly situation = computed<Situation>(() => {
    const user = this.auth.user();
    if (user?.status === 'suspended') return 'suspended';
    const status = user?.document?.status;
    if (status === 'pending') return 'review';
    if (status === 'rejected') return 'rejected';
    if (status === 'expired' || status === 'approved') return 'expired';
    return 'missing';
  });
  protected readonly icon = computed(() => ICONS[this.situation()]);
  protected readonly tone = computed(
    () =>
      ({
        review: 'bg-primary/15 text-primary',
        rejected: 'bg-danger/15 text-danger',
        expired: 'bg-warning/15 text-warning',
        missing: 'bg-warning/15 text-warning',
        suspended: 'bg-danger/15 text-danger',
      })[this.situation()],
  );
  protected readonly reason = computed(() => this.auth.user()?.document?.rejection_reason ?? null);
  protected readonly firstName = computed(() => this.auth.user()?.full_name.split(' ')[0] ?? '');
  protected readonly docChoices = computed<Choice[]>(() =>
    [
      { value: 'student_card', icon: LucideGraduationCap },
      { value: 'institutional_proof', icon: LucideBriefcase },
    ].map((c) => ({
      ...c,
      title: this.transloco.translate(`register.document.${c.value}.title`),
      description: this.transloco.translate(`register.document.${c.value}.body`),
    })),
  );

  constructor() {
    void this.meta.load();
  }

  protected err(name: 'kind' | 'file'): string | null {
    return fieldError(this.transloco, this.form.controls[name], this.submitted());
  }

  protected async upload(): Promise<void> {
    this.submitted.set(true);
    this.error.set(null);
    if (this.form.invalid || this.busy()) return;
    this.busy.set(true);
    try {
      const { kind, file } = this.form.getRawValue();
      await this.auth.uploadDocument(kind as DocKind, file as File);
      this.form.controls.file.reset(null);
      this.submitted.set(false);
      this.toasts.show(this.transloco.translate('account.sent'), 'success');
    } catch (error) {
      this.error.set(apiErrorMessage(this.transloco, error));
    } finally {
      this.busy.set(false);
    }
  }

  protected async check(): Promise<void> {
    this.checking.set(true);
    try {
      await this.auth.reloadMe();
      await this.router.navigateByUrl(homeFor(this.auth, this.router));
    } catch (error) {
      this.toasts.show(apiErrorMessage(this.transloco, error), 'danger');
    } finally {
      this.checking.set(false);
    }
  }

  protected async logout(): Promise<void> {
    await this.auth.logout();
    await this.router.navigateByUrl('/ingresar');
  }
}
