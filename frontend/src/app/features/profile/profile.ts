import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  resource,
  signal,
} from '@angular/core';
import { PassengerMetrics } from '../stats/stats-views';
import { TrustedContacts } from './trusted-contacts';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormBuilder, FormControl, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { TranslocoPipe, TranslocoService } from '@jsverse/transloco';
import { LucideLaptop, LucideLogOut, LucideShieldOff } from '@lucide/angular';
import { AuthService } from '../../core/auth/auth.service';
import { apiErrorMessage } from '../../core/http/api-error-message';
import { ThemePreference, ThemeService } from '../../core/theme/theme.service';
import { Avatar } from '../../shared/ui/avatar';
import { DialogService } from '../../shared/ui/dialog.service';
import { GlassButton } from '../../shared/ui/glass-button';
import { GlassCard } from '../../shared/ui/glass-card';
import { GlassInput } from '../../shared/ui/glass-input';
import { GlassSelect, SelectOption } from '../../shared/ui/glass-select';
import { LanguageSelect } from '../../shared/ui/language-select';
import { Skeleton } from '../../shared/ui/skeleton';
import { BadgeTone, StatusBadge } from '../../shared/ui/status-badge';
import { ToastService } from '../../shared/ui/toast.service';

const DOC_TONES: Record<string, BadgeTone> = {
  pending: 'pending',
  approved: 'success',
  rejected: 'danger',
  expired: 'warning',
};

@Component({
  selector: 'cp-profile',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    ReactiveFormsModule,
    RouterLink,
    TranslocoPipe,
    Avatar,
    GlassCard,
    GlassButton,
    GlassInput,
    GlassSelect,
    LanguageSelect,
    Skeleton,
    StatusBadge,
    TrustedContacts,
    PassengerMetrics,
    LucideLaptop,
    LucideLogOut,
    LucideShieldOff,
  ],
  templateUrl: './profile.html',
})
export default class Profile {
  protected readonly auth = inject(AuthService);
  protected readonly theme = inject(ThemeService);
  private readonly router = inject(Router);
  private readonly transloco = inject(TranslocoService);
  private readonly toasts = inject(ToastService);
  private readonly dialogs = inject(DialogService);
  private readonly fb = inject(FormBuilder).nonNullable;

  protected readonly user = this.auth.user;
  protected readonly isDriver = computed(() => this.user()?.role === 'driver');
  protected readonly docTone = computed(
    () => DOC_TONES[this.user()?.document?.status ?? ''] ?? 'neutral',
  );
  protected readonly licenseTone = computed(
    () => DOC_TONES[this.user()?.license?.status ?? ''] ?? 'neutral',
  );
  protected readonly saving = signal(false);
  protected readonly closingOthers = signal(false);

  protected readonly details = this.fb.group({
    program: [this.user()?.program ?? '', Validators.maxLength(120)],
    payment_note: [this.user()?.payment_note ?? '', Validators.maxLength(300)],
  });

  protected readonly sessions = resource({ loader: () => this.auth.sessions() });
  protected readonly themeControl = new FormControl<string>(this.theme.preference(), {
    nonNullable: true,
  });

  constructor() {
    this.themeControl.valueChanges
      .pipe(takeUntilDestroyed())
      .subscribe((value) => this.theme.setPreference(value as ThemePreference));
  }

  protected themeOptions(): SelectOption[] {
    return (['system', 'light', 'dark'] as const).map((value) => ({
      value,
      label: this.transloco.translate(`layout.theme.${value}`),
    }));
  }

  protected lastSeen(iso: string): string {
    return new Date(iso).toLocaleString(this.transloco.getActiveLang(), {
      dateStyle: 'medium',
      timeStyle: 'short',
    });
  }

  protected async saveDetails(): Promise<void> {
    if (this.details.invalid || this.saving()) return;
    this.saving.set(true);
    try {
      const { program, payment_note } = this.details.getRawValue();
      await this.auth.updateMe(
        this.isDriver()
          ? { program: program.trim() || null, payment_note: payment_note.trim() }
          : { program: program.trim() || null },
      );
      this.toasts.show(this.transloco.translate('profile.saved'), 'success');
    } catch (error) {
      this.toasts.show(apiErrorMessage(this.transloco, error), 'danger');
    } finally {
      this.saving.set(false);
    }
  }

  protected async closeOthers(): Promise<void> {
    const t = (key: string) => this.transloco.translate(`profile.sessions.${key}`);
    const confirmed = await this.dialogs.confirm({
      title: t('confirmTitle'),
      message: t('confirmBody'),
      confirmLabel: t('closeOthers'),
      cancelLabel: this.transloco.translate('common.cancel'),
      danger: true,
    });
    if (!confirmed) return;
    this.closingOthers.set(true);
    try {
      const revoked = await this.auth.logoutOthers();
      this.toasts.show(
        this.transloco.translate('profile.sessions.closed', { count: revoked }),
        'success',
      );
      this.sessions.reload();
    } catch (error) {
      this.toasts.show(apiErrorMessage(this.transloco, error), 'danger');
    } finally {
      this.closingOthers.set(false);
    }
  }

  protected async logout(): Promise<void> {
    await this.auth.logout();
    await this.router.navigateByUrl('/ingresar');
  }
}
