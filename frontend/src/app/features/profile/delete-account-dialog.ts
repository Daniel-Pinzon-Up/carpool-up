import { DialogRef } from '@angular/cdk/dialog';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormControl, ReactiveFormsModule, Validators } from '@angular/forms';
import { TranslocoPipe, TranslocoService } from '@jsverse/transloco';
import { LucideTrash2 } from '@icons';
import { AuthService } from '../../core/auth/auth.service';
import { apiErrorMessage } from '../../core/http/api-error-message';
import { GlassButton } from '../../shared/ui/glass-button';
import { GlassCheckbox } from '../../shared/ui/glass-checkbox';
import { GlassInput } from '../../shared/ui/glass-input';
import { GlassModal } from '../../shared/ui/glass-modal';

/**
 * Eliminar la cuenta: explica que se borra y que se conserva, pide confirmar que se entiende y
 * la contrasena. El error del servidor (contrasena, viaje en curso) se muestra aqui mismo.
 * Cierra con true si la cuenta se elimino.
 */
@Component({
  selector: 'cp-delete-account-dialog',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    ReactiveFormsModule,
    TranslocoPipe,
    GlassButton,
    GlassCheckbox,
    GlassInput,
    GlassModal,
    LucideTrash2,
  ],
  template: `
    <cp-glass-modal [title]="'profile.delete.title' | transloco">
      <form
        id="delete-account-form"
        class="flex flex-col gap-4"
        (submit)="$event.preventDefault(); confirm()"
        novalidate
      >
        <p>{{ 'profile.delete.intro' | transloco }}</p>
        <ul class="flex list-disc flex-col gap-1 pl-5 text-sm text-muted">
          <li>{{ 'profile.delete.erased' | transloco }}</li>
          <li>{{ 'profile.delete.trips' | transloco }}</li>
          <li>{{ 'profile.delete.kept' | transloco }}</li>
        </ul>
        <cp-glass-checkbox [formControl]="understood">
          {{ 'profile.delete.understood' | transloco }}
        </cp-glass-checkbox>
        <cp-glass-input
          [formControl]="password"
          type="password"
          autocomplete="current-password"
          [label]="'fields.password' | transloco"
          [error]="error()"
        />
      </form>
      <ng-container actions>
        <button cp-button variant="secondary" type="button" (click)="ref.close(false)">
          {{ 'common.cancel' | transloco }}
        </button>
        <button
          cp-button
          variant="danger"
          type="submit"
          form="delete-account-form"
          [loading]="busy()"
          [disabled]="!understood.value || !password.value"
        >
          <svg lucideTrash2 class="size-4" aria-hidden="true"></svg>
          {{ 'profile.delete.confirm' | transloco }}
        </button>
      </ng-container>
    </cp-glass-modal>
  `,
})
export class DeleteAccountDialog {
  protected readonly ref = inject<DialogRef<boolean>>(DialogRef);
  private readonly auth = inject(AuthService);
  private readonly transloco = inject(TranslocoService);

  protected readonly understood = new FormControl(false, { nonNullable: true });
  protected readonly password = new FormControl('', {
    nonNullable: true,
    validators: Validators.required,
  });
  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);

  protected async confirm(): Promise<void> {
    if (!this.understood.value || !this.password.value || this.busy()) return;
    this.busy.set(true);
    this.error.set(null);
    try {
      await this.auth.deleteAccount(this.password.value);
      this.ref.close(true);
    } catch (error) {
      this.error.set(apiErrorMessage(this.transloco, error));
    } finally {
      this.busy.set(false);
    }
  }
}
