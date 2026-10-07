import { DIALOG_DATA, DialogRef } from '@angular/cdk/dialog';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormControl, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { TranslocoPipe, TranslocoService } from '@jsverse/transloco';
import {
  LucideCheck,
  LucideCopy,
  LucideMessageSquare,
  LucidePhone,
  LucidePhoneCall,
  LucideShare2,
  LucideSiren,
} from '@lucide/angular';
import { apiErrorMessage } from '../../core/http/api-error-message';
import { GlassButton } from '../../shared/ui/glass-button';
import { GlassModal } from '../../shared/ui/glass-modal';
import { GlassTextarea } from '../../shared/ui/glass-textarea';
import { Skeleton } from '../../shared/ui/skeleton';
import { LifecycleApi, TrustedContact } from './lifecycle.api';

export interface TripRef {
  tripId: string;
}

/**
 * Compartir el viaje: crea un enlace de solo lectura (ubicacion en vivo, vehiculo, placa y
 * ruta) para enviarlo a quien el usuario quiera, por ejemplo a sus contactos de confianza.
 */
@Component({
  selector: 'cp-share-trip-dialog',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    RouterLink,
    TranslocoPipe,
    GlassButton,
    GlassModal,
    Skeleton,
    LucideCheck,
    LucideCopy,
    LucideMessageSquare,
    LucideShare2,
  ],
  template: `
    <cp-glass-modal [title]="'safety.share.title' | transloco">
      <div class="flex flex-col gap-4">
        <p class="text-muted">{{ 'safety.share.body' | transloco }}</p>
        @if (url(); as link) {
          <label class="flex flex-col gap-1 text-sm font-medium">
            {{ 'safety.share.link' | transloco }}
            <input
              readonly
              [value]="link"
              class="glass-1 min-h-11 !rounded-xl px-3 text-sm"
              (focus)="$any($event.target).select()"
            />
          </label>
          <p class="text-xs text-muted">
            {{ 'safety.share.expires' | transloco: { time: expires() } }}
          </p>
          <div class="flex flex-wrap gap-2">
            <button cp-button variant="secondary" type="button" (click)="copy(link)">
              @if (copied()) {
                <svg lucideCheck class="size-4" aria-hidden="true"></svg>
                {{ 'safety.share.copied' | transloco }}
              } @else {
                <svg lucideCopy class="size-4" aria-hidden="true"></svg>
                {{ 'safety.share.copy' | transloco }}
              }
            </button>
            @if (canShare) {
              <button cp-button type="button" (click)="share(link)">
                <svg lucideShare2 class="size-4" aria-hidden="true"></svg>
                {{ 'safety.share.send' | transloco }}
              </button>
            }
          </div>
          <section aria-labelledby="share-contacts">
            <h3 id="share-contacts" class="mb-2 text-sm font-semibold">
              {{ 'safety.contacts.title' | transloco }}
            </h3>
            @for (contact of contacts(); track contact.id) {
              <a
                class="flex min-h-11 items-center gap-2 rounded-xl px-2 hover:bg-glass"
                [href]="smsLink(contact, link)"
              >
                <svg lucideMessageSquare class="size-4 text-primary" aria-hidden="true"></svg>
                {{ 'safety.share.smsTo' | transloco: { name: contact.name } }}
              </a>
            } @empty {
              <p class="text-sm text-muted">
                {{ 'safety.contacts.none' | transloco }}
                <a routerLink="/perfil" class="font-semibold text-primary" (click)="ref.close()">
                  {{ 'safety.contacts.add' | transloco }}
                </a>
              </p>
            }
          </section>
        } @else if (error()) {
          <p role="alert" class="text-danger">{{ error() }}</p>
        } @else {
          <cp-skeleton [lines]="2" />
        }
      </div>
      <ng-container actions>
        <button cp-button variant="secondary" type="button" (click)="ref.close()">
          {{ 'common.close' | transloco }}
        </button>
      </ng-container>
    </cp-glass-modal>
  `,
})
export class ShareTripDialog {
  private readonly data = inject<TripRef>(DIALOG_DATA);
  protected readonly ref = inject(DialogRef);
  private readonly api = inject(LifecycleApi);
  private readonly transloco = inject(TranslocoService);

  protected readonly canShare = typeof globalThis.navigator?.share === 'function';
  protected readonly url = signal<string | null>(null);
  protected readonly expires = signal('');
  protected readonly contacts = signal<TrustedContact[]>([]);
  protected readonly copied = signal(false);
  protected readonly error = signal<string | null>(null);

  constructor() {
    void this.load();
  }

  private async load(): Promise<void> {
    try {
      const [link, contacts] = await Promise.all([
        this.api.shareLink(this.data.tripId),
        this.api.contacts(),
      ]);
      this.url.set(`${location.origin}${link.path}`);
      this.expires.set(
        new Date(link.expires_at).toLocaleTimeString(this.transloco.getActiveLang(), {
          hour: 'numeric',
          minute: '2-digit',
          timeZone: 'America/Bogota',
        }),
      );
      this.contacts.set(contacts);
    } catch (error) {
      this.error.set(apiErrorMessage(this.transloco, error));
    }
  }

  private message(link: string): string {
    return this.transloco.translate('safety.share.message', { link });
  }

  protected smsLink(contact: TrustedContact, link: string): string {
    return `sms:${contact.phone}?body=${encodeURIComponent(this.message(link))}`;
  }

  protected async copy(link: string): Promise<void> {
    try {
      await navigator.clipboard.writeText(link);
      this.copied.set(true);
    } catch {
      // Sin permiso del portapapeles: el campo queda seleccionable para copiar a mano.
    }
  }

  protected async share(link: string): Promise<void> {
    try {
      await navigator.share({ title: 'Carpool UP', text: this.message(link), url: link });
    } catch {
      // El usuario cerro el menu de compartir.
    }
  }
}

/**
 * Emergencia: primero la llamada a la linea 123; ademas avisa en vivo a los administradores
 * de la universidad con la ubicacion actual (si el navegador la da) y una nota opcional.
 */
@Component({
  selector: 'cp-emergency-dialog',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    ReactiveFormsModule,
    TranslocoPipe,
    GlassButton,
    GlassModal,
    GlassTextarea,
    LucideCheck,
    LucidePhone,
    LucidePhoneCall,
    LucideSiren,
  ],
  template: `
    <cp-glass-modal [title]="'safety.emergency.title' | transloco">
      <div class="flex flex-col gap-4">
        <a
          [href]="'tel:' + phone()"
          class="flex min-h-14 items-center justify-center gap-3 rounded-2xl bg-danger px-4 text-lg font-bold text-on-danger"
        >
          <svg lucidePhoneCall class="size-6" aria-hidden="true"></svg>
          {{ 'safety.emergency.call' | transloco: { phone: phone() } }}
        </a>
        @if (sentAt(); as at) {
          <p class="flex gap-2 rounded-xl bg-success/15 p-3" role="status">
            <svg lucideCheck class="size-5 shrink-0 text-success" aria-hidden="true"></svg>
            {{ 'safety.emergency.sent' | transloco: { time: at } }}
          </p>
        } @else {
          <p class="text-muted">{{ 'safety.emergency.body' | transloco }}</p>
          <form
            id="emergency-form"
            class="flex flex-col gap-3"
            (submit)="$event.preventDefault(); report()"
          >
            <cp-glass-textarea [formControl]="note" [label]="'safety.emergency.note' | transloco" />
          </form>
          @if (error()) {
            <p role="alert" class="text-sm text-danger">{{ error() }}</p>
          }
        }
        @if (contacts().length) {
          <section aria-labelledby="emergency-contacts">
            <h3 id="emergency-contacts" class="mb-2 text-sm font-semibold">
              {{ 'safety.contacts.title' | transloco }}
            </h3>
            @for (contact of contacts(); track contact.id) {
              <a
                class="flex min-h-11 items-center gap-2 rounded-xl px-2 hover:bg-glass"
                [href]="'tel:' + contact.phone"
              >
                <svg lucidePhone class="size-4 text-primary" aria-hidden="true"></svg>
                {{ 'safety.emergency.callContact' | transloco: { name: contact.name } }}
              </a>
            }
          </section>
        }
      </div>
      <ng-container actions>
        <button cp-button variant="secondary" type="button" (click)="ref.close()">
          {{ 'common.close' | transloco }}
        </button>
        @if (!sentAt()) {
          <button
            cp-button
            variant="danger"
            type="submit"
            form="emergency-form"
            [disabled]="busy()"
          >
            <svg lucideSiren class="size-4" aria-hidden="true"></svg>
            {{ 'safety.emergency.report' | transloco }}
          </button>
        }
      </ng-container>
    </cp-glass-modal>
  `,
})
export class EmergencyDialog {
  private readonly data = inject<TripRef>(DIALOG_DATA);
  protected readonly ref = inject(DialogRef);
  private readonly api = inject(LifecycleApi);
  private readonly transloco = inject(TranslocoService);

  protected readonly phone = signal('123');
  protected readonly contacts = signal<TrustedContact[]>([]);
  protected readonly sentAt = signal<string | null>(null);
  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly note = new FormControl('', {
    nonNullable: true,
    validators: [Validators.maxLength(500)],
  });

  constructor() {
    void this.api.contacts().then(
      (contacts) => this.contacts.set(contacts),
      () => undefined,
    );
  }

  private position(): Promise<{ lat?: number; lon?: number }> {
    const geolocation = globalThis.navigator?.geolocation;
    if (!geolocation) return Promise.resolve({});
    return new Promise((resolve) =>
      geolocation.getCurrentPosition(
        ({ coords }) => resolve({ lat: coords.latitude, lon: coords.longitude }),
        () => resolve({}),
        { enableHighAccuracy: true, timeout: 5000, maximumAge: 30_000 },
      ),
    );
  }

  protected async report(): Promise<void> {
    this.busy.set(true);
    this.error.set(null);
    try {
      const where = await this.position();
      const note = this.note.value.trim();
      const report = await this.api.emergency(this.data.tripId, {
        ...where,
        ...(note ? { note } : {}),
      });
      this.phone.set(report.phone);
      this.sentAt.set(
        new Date(report.emergency.created_at).toLocaleTimeString(this.transloco.getActiveLang(), {
          hour: 'numeric',
          minute: '2-digit',
          timeZone: 'America/Bogota',
        }),
      );
    } catch (error) {
      this.error.set(apiErrorMessage(this.transloco, error));
    } finally {
      this.busy.set(false);
    }
  }
}
