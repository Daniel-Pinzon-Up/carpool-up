import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  input,
  output,
  signal,
  untracked,
} from '@angular/core';
import { TranslocoPipe, TranslocoService } from '@jsverse/transloco';
import {
  LucideCircleAlert,
  LucideFlagTriangleRight,
  LucideLocateFixed,
  LucidePlay,
  LucideReceipt,
  LucideShare2,
  LucideSiren,
} from '@icons';
import { apiErrorCode, apiErrorMessage } from '../../core/http/api-error-message';
import { LanguageService } from '../../core/i18n/language.service';
import { LocationSharingService } from '../../core/location/location-sharing.service';
import { formatCop } from '../../shared/map/routing.api';
import { DialogService } from '../../shared/ui/dialog.service';
import { GlassButton } from '../../shared/ui/glass-button';
import { GlassCard } from '../../shared/ui/glass-card';
import { ToastService } from '../../shared/ui/toast.service';
import { LifecycleApi, Ticket } from './lifecycle.api';
import { EmergencyDialog, ShareTripDialog, TripRef } from './safety-dialogs';
import { Trip } from './trips.api';

/**
 * Panel del conductor segun el estado del viaje: iniciar; en curso, la ubicacion compartida
 * y finalizar; completado, los tickets con la confirmacion del aporte.
 */
@Component({
  selector: 'cp-trip-control',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    TranslocoPipe,
    GlassButton,
    GlassCard,
    LucideCircleAlert,
    LucideFlagTriangleRight,
    LucideLocateFixed,
    LucidePlay,
    LucideReceipt,
  ],
  host: { class: 'block' },
  template: `
    @if (trip().status === 'scheduled') {
      <cp-glass-card [level]="2" class="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 class="font-bold">{{ 'lifecycle.start.title' | transloco }}</h2>
          <p class="text-sm text-muted">{{ 'lifecycle.start.hint' | transloco }}</p>
        </div>
        <button cp-button type="button" [disabled]="busy()" (click)="start()">
          <svg lucidePlay class="size-4" aria-hidden="true"></svg>
          {{ 'lifecycle.start.action' | transloco }}
        </button>
      </cp-glass-card>
    } @else if (trip().status === 'in_progress') {
      <cp-glass-card [level]="2" class="flex flex-col gap-3">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <p class="flex items-center gap-2" role="status">
            <svg
              lucideLocateFixed
              class="size-5 shrink-0"
              [class]="sharing.status() === 'on' ? 'text-success' : 'text-warning'"
              aria-hidden="true"
            ></svg>
            {{ 'lifecycle.location.' + sharing.status() | transloco }}
          </p>
          @if (sharing.status() === 'denied' || sharing.status() === 'unavailable') {
            <button cp-button variant="secondary" type="button" (click)="share()">
              {{ 'lifecycle.location.retry' | transloco }}
            </button>
          }
        </div>
        @if (sharing.keepsScreenOn()) {
          <p class="text-xs text-muted">{{ 'lifecycle.location.screenOn' | transloco }}</p>
        }
        @if (error()) {
          <p role="alert" class="flex gap-2 text-sm text-danger">
            <svg lucideCircleAlert class="size-4 shrink-0" aria-hidden="true"></svg>
            {{ error() }}
          </p>
        }
        <button cp-button type="button" class="self-start" [disabled]="busy()" (click)="finish()">
          <svg lucideFlagTriangleRight class="size-4" aria-hidden="true"></svg>
          {{ 'lifecycle.finish.action' | transloco }}
        </button>
      </cp-glass-card>
    } @else if (trip().status === 'completed' && tickets().length) {
      <cp-glass-card [level]="2">
        <h2 class="mb-3 flex items-center gap-2 font-bold">
          <svg lucideReceipt class="size-5" aria-hidden="true"></svg>
          {{ 'lifecycle.tickets.title' | transloco }}
        </h2>
        <ul class="flex flex-col gap-2">
          @for (ticket of tickets(); track ticket.id) {
            <li class="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-glass p-3">
              <span>
                <span class="font-semibold">{{ ticket.passenger_name }}</span>
                <span class="block text-sm text-muted">
                  {{ ticket.code }} · {{ money(ticket.amount) }}
                </span>
              </span>
              <label class="flex min-h-11 items-center gap-2 text-sm font-medium">
                <input
                  type="checkbox"
                  class="size-5 accent-[var(--accent)]"
                  [checked]="ticket.paid_confirmed"
                  (change)="togglePaid(ticket, $any($event.target).checked)"
                />
                {{ 'lifecycle.tickets.paid' | transloco }}
              </label>
            </li>
          }
        </ul>
        <p class="mt-3 text-xs text-muted">{{ 'lifecycle.tickets.hint' | transloco }}</p>
      </cp-glass-card>
    }
  `,
})
export class TripControl {
  readonly trip = input.required<Trip>();
  readonly changed = output<void>();

  private readonly api = inject(LifecycleApi);
  protected readonly sharing = inject(LocationSharingService);
  private readonly dialogs = inject(DialogService);
  private readonly toast = inject(ToastService);
  private readonly transloco = inject(TranslocoService);
  private readonly language = inject(LanguageService);

  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly tickets = signal<Ticket[]>([]);

  constructor() {
    effect(() => {
      const trip = this.trip();
      untracked(() => {
        // Al volver a abrir un viaje en curso, se retoma la ubicacion compartida.
        if (trip.status === 'in_progress' && this.sharing.tripId() !== trip.id) this.share();
        if (trip.status === 'completed') void this.loadTickets(trip.id);
      });
    });
  }

  protected share(): void {
    this.sharing.start(this.trip().id);
  }

  private async run(action: () => Promise<unknown>, done: string): Promise<boolean> {
    this.busy.set(true);
    this.error.set(null);
    try {
      await action();
      this.toast.show(this.transloco.translate(done), 'success');
      this.changed.emit();
      return true;
    } catch (error) {
      this.error.set(apiErrorMessage(this.transloco, error));
      if (apiErrorCode(error) !== 'PASSENGERS_UNMARKED') {
        this.toast.show(apiErrorMessage(this.transloco, error), 'danger');
      }
      return false;
    } finally {
      this.busy.set(false);
    }
  }

  protected async start(): Promise<void> {
    if (await this.run(() => this.api.start(this.trip().id), 'lifecycle.start.done')) {
      this.share();
    }
  }

  protected async finish(): Promise<void> {
    const ok = await this.dialogs.confirm({
      title: this.transloco.translate('lifecycle.finish.title'),
      message: this.transloco.translate('lifecycle.finish.message'),
      confirmLabel: this.transloco.translate('lifecycle.finish.action'),
      cancelLabel: this.transloco.translate('common.cancel'),
    });
    if (!ok) return;
    if (await this.run(() => this.api.finish(this.trip().id), 'lifecycle.finish.done')) {
      this.sharing.stop();
    }
  }

  private async loadTickets(tripId: string): Promise<void> {
    try {
      this.tickets.set(await this.api.tickets('driver', tripId));
    } catch {
      this.tickets.set([]);
    }
  }

  protected async togglePaid(ticket: Ticket, paid: boolean): Promise<void> {
    try {
      const updated = await this.api.markPaid(ticket.id, paid);
      this.tickets.update((list) => list.map((t) => (t.id === updated.id ? updated : t)));
    } catch (error) {
      this.toast.show(apiErrorMessage(this.transloco, error), 'danger');
    }
  }

  protected money(amount: number): string {
    return formatCop(amount, this.language.current());
  }
}

/** Compartir el viaje y emergencia: para el conductor y los pasajeros aceptados. */
@Component({
  selector: 'cp-safety-actions',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [TranslocoPipe, GlassButton, LucideShare2, LucideSiren],
  host: { class: 'flex flex-wrap gap-2' },
  template: `
    <button cp-button variant="secondary" type="button" (click)="share()">
      <svg lucideShare2 class="size-4" aria-hidden="true"></svg>
      {{ 'safety.share.action' | transloco }}
    </button>
    <button cp-button variant="danger" type="button" (click)="emergency()">
      <svg lucideSiren class="size-4" aria-hidden="true"></svg>
      {{ 'safety.emergency.action' | transloco }}
    </button>
  `,
})
export class SafetyActions {
  readonly tripId = input.required<string>();
  private readonly dialogs = inject(DialogService);

  protected share(): void {
    this.dialogs.open<void, TripRef, ShareTripDialog>(ShareTripDialog, { tripId: this.tripId() });
  }

  protected emergency(): void {
    this.dialogs.open<void, TripRef, EmergencyDialog>(EmergencyDialog, { tripId: this.tripId() });
  }
}

/** Ticket del pasajero cuando el viaje termino. */
@Component({
  selector: 'cp-my-ticket',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [TranslocoPipe, GlassCard, LucideReceipt],
  template: `
    @if (ticket(); as t) {
      <cp-glass-card [level]="2">
        <h2 class="mb-2 flex items-center gap-2 font-bold">
          <svg lucideReceipt class="size-5" aria-hidden="true"></svg>
          {{ 'lifecycle.tickets.mine' | transloco }}
        </h2>
        <p class="font-mono text-lg font-bold tracking-wider">{{ t.code }}</p>
        <p class="text-sm">{{ amount() }} · {{ 'trips.seats' | transloco: { count: t.seats } }}</p>
        <p class="text-sm text-muted">
          {{
            (t.paid_confirmed ? 'lifecycle.tickets.confirmed' : 'lifecycle.tickets.pending')
              | transloco
          }}
        </p>
        <p class="mt-2 text-xs text-muted">{{ 'lifecycle.tickets.hint' | transloco }}</p>
      </cp-glass-card>
    }
  `,
})
export class MyTicket {
  readonly tripId = input.required<string>();
  private readonly api = inject(LifecycleApi);
  private readonly language = inject(LanguageService);
  protected readonly ticket = signal<Ticket | null>(null);
  protected readonly amount = computed(() =>
    formatCop(this.ticket()?.amount ?? 0, this.language.current()),
  );

  constructor() {
    effect(() => {
      const id = this.tripId();
      untracked(
        () =>
          void this.api.tickets('passenger', id).then(
            (list) => this.ticket.set(list[0] ?? null),
            () => this.ticket.set(null),
          ),
      );
    });
  }
}
