import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { TranslocoPipe, TranslocoService } from '@jsverse/transloco';
import { LucidePencil, LucidePhone, LucidePlus, LucideTrash2 } from '@lucide/angular';
import { apiErrorMessage } from '../../core/http/api-error-message';
import { fieldError } from '../../shared/forms/validation';
import { DialogService } from '../../shared/ui/dialog.service';
import { GlassButton } from '../../shared/ui/glass-button';
import { GlassCard } from '../../shared/ui/glass-card';
import { GlassInput } from '../../shared/ui/glass-input';
import { ErrorState } from '../../shared/ui/error-state';
import { Skeleton } from '../../shared/ui/skeleton';
import { ToastService } from '../../shared/ui/toast.service';
import { LifecycleApi, TrustedContact } from '../trips/lifecycle.api';

const MAX_CONTACTS = 5;

/**
 * Contactos de confianza (hasta 5): a quienes se envia el enlace del viaje o se llama desde
 * el boton de emergencia. Solo los ve su dueno.
 */
@Component({
  selector: 'cp-trusted-contacts',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    ReactiveFormsModule,
    TranslocoPipe,
    GlassButton,
    GlassCard,
    GlassInput,
    ErrorState,
    Skeleton,
    LucidePencil,
    LucidePhone,
    LucidePlus,
    LucideTrash2,
  ],
  template: `
    <cp-glass-card>
      <h2 class="mb-1 text-lg font-bold">{{ 'safety.contacts.title' | transloco }}</h2>
      <p class="mb-4 text-sm text-muted">{{ 'safety.contacts.help' | transloco }}</p>
      @if (loadError(); as message) {
        <cp-error-state [message]="message" (retry)="load()" />
      } @else if (contacts() === null) {
        <cp-skeleton [lines]="2" />
      } @else {
        <ul class="mb-4 flex flex-col gap-2">
          @for (contact of contacts(); track contact.id) {
            <li class="flex items-center gap-3 rounded-xl bg-glass p-3">
              <svg lucidePhone class="size-5 shrink-0 text-primary" aria-hidden="true"></svg>
              <div class="min-w-0 flex-1">
                <p class="truncate font-medium">
                  {{ contact.name }}
                  @if (contact.relationship) {
                    <span class="text-sm text-muted">· {{ contact.relationship }}</span>
                  }
                </p>
                <p class="text-sm text-muted">{{ contact.phone }}</p>
              </div>
              <button
                type="button"
                class="grid size-11 place-items-center rounded-full hover:bg-glass-strong"
                [attr.aria-label]="'safety.contacts.edit' | transloco: { name: contact.name }"
                (click)="edit(contact)"
              >
                <svg lucidePencil class="size-4" aria-hidden="true"></svg>
              </button>
              <button
                type="button"
                class="grid size-11 place-items-center rounded-full text-danger hover:bg-glass-strong"
                [attr.aria-label]="'safety.contacts.remove' | transloco: { name: contact.name }"
                (click)="remove(contact)"
              >
                <svg lucideTrash2 class="size-4" aria-hidden="true"></svg>
              </button>
            </li>
          } @empty {
            <li class="text-sm text-muted">{{ 'safety.contacts.none' | transloco }}</li>
          }
        </ul>
        @if (editing() !== null || (contacts()?.length ?? 0) < max) {
          <form [formGroup]="form" class="grid gap-3 sm:grid-cols-3" (ngSubmit)="save()" novalidate>
            <cp-glass-input
              formControlName="name"
              [label]="'safety.contacts.name' | transloco"
              [error]="error('name')"
            />
            <cp-glass-input
              formControlName="phone"
              type="tel"
              autocomplete="tel"
              [label]="'safety.contacts.phone' | transloco"
              [error]="error('phone')"
            />
            <cp-glass-input
              formControlName="relationship"
              [label]="'safety.contacts.relationship' | transloco"
            />
            <div class="flex flex-wrap gap-2 sm:col-span-3">
              <button cp-button type="submit" [loading]="busy()">
                <svg lucidePlus class="size-4" aria-hidden="true"></svg>
                {{ (editing() ? 'safety.contacts.save' : 'safety.contacts.add') | transloco }}
              </button>
              @if (editing()) {
                <button cp-button variant="ghost" type="button" (click)="cancel()">
                  {{ 'common.cancel' | transloco }}
                </button>
              }
            </div>
          </form>
        } @else {
          <p class="text-sm text-muted">{{ 'safety.contacts.full' | transloco: { max: max } }}</p>
        }
      }
    </cp-glass-card>
  `,
})
export class TrustedContacts {
  private readonly api = inject(LifecycleApi);
  private readonly dialogs = inject(DialogService);
  private readonly toast = inject(ToastService);
  private readonly transloco = inject(TranslocoService);

  protected readonly max = MAX_CONTACTS;
  protected readonly contacts = signal<TrustedContact[] | null>(null);
  protected readonly loadError = signal<string | null>(null);
  protected readonly editing = signal<string | null>(null);
  protected readonly busy = signal(false);
  private readonly submitted = signal(false);
  protected readonly form = inject(FormBuilder).nonNullable.group({
    name: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(80)]],
    phone: ['', [Validators.required, Validators.pattern(/^\+?[0-9\s\-().]{7,20}$/)]],
    relationship: ['', [Validators.maxLength(40)]],
  });

  constructor() {
    void this.load();
  }

  protected async load(): Promise<void> {
    this.loadError.set(null);
    try {
      this.contacts.set(await this.api.contacts());
    } catch (error) {
      this.loadError.set(apiErrorMessage(this.transloco, error));
    }
  }

  protected error(field: 'name' | 'phone'): string | null {
    return fieldError(this.transloco, this.form.controls[field], this.submitted());
  }

  protected edit(contact: TrustedContact): void {
    this.editing.set(contact.id);
    this.form.setValue({
      name: contact.name,
      phone: contact.phone,
      relationship: contact.relationship ?? '',
    });
  }

  protected cancel(): void {
    this.editing.set(null);
    this.submitted.set(false);
    this.form.reset();
  }

  protected async save(): Promise<void> {
    this.submitted.set(true);
    this.form.markAllAsTouched();
    if (this.form.invalid) return;
    const { name, phone, relationship } = this.form.getRawValue();
    const body = { name: name.trim(), phone, relationship: relationship.trim() || null };
    this.busy.set(true);
    try {
      const id = this.editing();
      if (id) await this.api.updateContact(id, body);
      else await this.api.addContact(body);
      this.cancel();
      await this.load();
    } catch (error) {
      this.toast.show(apiErrorMessage(this.transloco, error), 'danger');
    } finally {
      this.busy.set(false);
    }
  }

  protected async remove(contact: TrustedContact): Promise<void> {
    const ok = await this.dialogs.confirm({
      title: this.transloco.translate('safety.contacts.removeTitle'),
      message: this.transloco.translate('safety.contacts.removeMessage', { name: contact.name }),
      confirmLabel: this.transloco.translate('safety.contacts.removeConfirm'),
      cancelLabel: this.transloco.translate('common.cancel'),
      danger: true,
    });
    if (!ok) return;
    try {
      await this.api.deleteContact(contact.id);
      await this.load();
    } catch (error) {
      this.toast.show(apiErrorMessage(this.transloco, error), 'danger');
    }
  }
}
