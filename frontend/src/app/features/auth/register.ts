import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { AbstractControl, FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { TranslocoPipe, TranslocoService } from '@jsverse/transloco';
import {
  LucideArrowLeft,
  LucideArrowRight,
  LucideBriefcase,
  LucideCar,
  LucideCircleAlert,
  LucideGraduationCap,
  LucideLock,
  LucideMail,
  LucideUser,
  LucideUsers,
} from '@icons';
import { AuthService } from '../../core/auth/auth.service';
import { apiErrorMessage } from '../../core/http/api-error-message';
import { MetaService } from '../../core/meta/meta.service';
import {
  dynamicMinLength,
  fieldError,
  institutionalEmail,
  matchFields,
} from '../../shared/forms/validation';
import { Choice, ChoiceCards } from '../../shared/ui/choice-cards';
import { FileDrop } from '../../shared/ui/file-drop';
import { GlassButton } from '../../shared/ui/glass-button';
import { GlassCard } from '../../shared/ui/glass-card';
import { GlassCheckbox } from '../../shared/ui/glass-checkbox';
import { GlassInput } from '../../shared/ui/glass-input';
import { GlassSelect, SelectOption } from '../../shared/ui/glass-select';
import { Stepper } from '../../shared/ui/stepper';

const STEPS = ['data', 'role', 'document', 'terms'] as const;
type Step = (typeof STEPS)[number];

/** Registro en cuatro pasos: datos, rol, documento y terminos, con resumen antes de enviar. */
@Component({
  selector: 'cp-register',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    ReactiveFormsModule,
    RouterLink,
    TranslocoPipe,
    GlassCard,
    GlassInput,
    GlassSelect,
    GlassButton,
    GlassCheckbox,
    ChoiceCards,
    FileDrop,
    Stepper,
    LucideArrowLeft,
    LucideArrowRight,
    LucideCircleAlert,
  ],
  templateUrl: './register.html',
})
export default class Register {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly transloco = inject(TranslocoService);
  protected readonly meta = inject(MetaService);
  private readonly fb = inject(FormBuilder).nonNullable;

  protected readonly icons = { user: LucideUser, mail: LucideMail, lock: LucideLock };
  protected readonly steps = STEPS;
  protected readonly index = signal(0);
  protected readonly step = computed<Step>(() => STEPS[this.index()]);
  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly attempted = signal<Record<Step, boolean>>({
    data: false,
    role: false,
    document: false,
    terms: false,
  });

  protected readonly data = this.fb.group(
    {
      full_name: ['', [Validators.required, Validators.minLength(3), Validators.maxLength(120)]],
      email: [
        '',
        [
          Validators.required,
          Validators.email,
          institutionalEmail(() => this.meta.settings().allowed_email_suffix),
        ],
      ],
      password: [
        '',
        [Validators.required, dynamicMinLength(() => this.meta.settings().password_min_length)],
      ],
      confirm: ['', Validators.required],
      sex: ['', Validators.required],
      program: ['', Validators.maxLength(120)],
    },
    { validators: matchFields('password', 'confirm') },
  );
  protected readonly role = this.fb.group({ role: ['', Validators.required] });
  protected readonly document = this.fb.group({
    doc_kind: ['', Validators.required],
    file: this.fb.control<File | null>(null, Validators.required),
  });
  protected readonly terms = this.fb.group({
    accept_terms: [false, Validators.requiredTrue],
    accept_data_policy: [false, Validators.requiredTrue],
  });

  private readonly lang = toSignal(this.transloco.langChanges$, {
    initialValue: this.transloco.getActiveLang(),
  });
  protected readonly stepLabels = computed(() => {
    this.lang();
    return STEPS.map((s) => this.transloco.translate(`register.steps.${s}`));
  });
  protected readonly sexOptions = computed<SelectOption[]>(() => {
    this.lang();
    return ['female', 'male'].map((value) => ({
      value,
      label: this.transloco.translate(`fields.sexOptions.${value}`),
    }));
  });
  protected readonly roleChoices = computed<Choice[]>(() => {
    this.lang();
    return [
      { value: 'passenger', icon: LucideUsers },
      { value: 'driver', icon: LucideCar },
    ].map((c) => ({
      ...c,
      title: this.transloco.translate(`register.role.${c.value}.title`),
      description: this.transloco.translate(`register.role.${c.value}.body`),
    }));
  });
  protected readonly docChoices = computed<Choice[]>(() => {
    this.lang();
    return [
      { value: 'student_card', icon: LucideGraduationCap },
      { value: 'institutional_proof', icon: LucideBriefcase },
    ].map((c) => ({
      ...c,
      title: this.transloco.translate(`register.document.${c.value}.title`),
      description: this.transloco.translate(`register.document.${c.value}.body`),
    }));
  });

  constructor() {
    void this.meta.load();
  }

  private groupFor(step: Step): AbstractControl {
    return { data: this.data, role: this.role, document: this.document, terms: this.terms }[step];
  }

  protected err(control: string): string | null {
    const step = this.step();
    return fieldError(this.transloco, this.groupFor(step).get(control), this.attempted()[step]);
  }

  protected fileErrors() {
    return {
      type: this.transloco.translate('errors.FILE_TYPE_NOT_ALLOWED'),
      size: this.transloco.translate('errors.FILE_TOO_LARGE', {
        max_mb: this.meta.settings().max_upload_mb,
      }),
    };
  }

  protected summaryValue(key: 'role' | 'doc_kind' | 'sex'): string {
    if (key === 'role')
      return this.transloco.translate(`register.role.${this.role.value.role}.title`);
    if (key === 'doc_kind')
      return this.transloco.translate(`register.document.${this.document.value.doc_kind}.title`);
    return this.transloco.translate(`fields.sexOptions.${this.data.value.sex}`);
  }

  protected back(): void {
    this.error.set(null);
    this.index.update((i) => Math.max(0, i - 1));
  }

  protected next(): void {
    const step = this.step();
    this.attempted.update((value) => ({ ...value, [step]: true }));
    const group = this.groupFor(step);
    group.markAllAsTouched();
    if (group.invalid) {
      this.focusFirstInvalid();
      return;
    }
    if (this.index() < STEPS.length - 1) {
      this.index.update((i) => i + 1);
      queueMicrotask(() => document.querySelector<HTMLElement>('#register-step-title')?.focus());
      return;
    }
    void this.submit();
  }

  private focusFirstInvalid(): void {
    queueMicrotask(() =>
      document.querySelector<HTMLElement>('cp-register [aria-invalid="true"]')?.focus(),
    );
  }

  private async submit(): Promise<void> {
    if (this.busy()) return;
    this.busy.set(true);
    this.error.set(null);
    const data = this.data.getRawValue();
    const form = new FormData();
    form.append('email', data.email.trim().toLowerCase());
    form.append('password', data.password);
    form.append('full_name', data.full_name.trim());
    form.append('sex', data.sex);
    if (data.program.trim()) form.append('program', data.program.trim());
    form.append('role', this.role.getRawValue().role);
    form.append('doc_kind', this.document.getRawValue().doc_kind);
    form.append('document', this.document.getRawValue().file as File);
    form.append('accept_terms', String(this.terms.getRawValue().accept_terms));
    form.append('accept_data_policy', String(this.terms.getRawValue().accept_data_policy));
    try {
      await this.auth.register(form);
      await this.router.navigateByUrl('/verificar');
    } catch (error) {
      this.error.set(apiErrorMessage(this.transloco, error));
    } finally {
      this.busy.set(false);
    }
  }
}
