import { Injectable, inject } from '@angular/core';
import { TranslocoService } from '@jsverse/transloco';
import { firstValueFrom } from 'rxjs';
import { apiErrorCode, apiErrorMessage } from '../../core/http/api-error-message';
import { DialogService } from '../../shared/ui/dialog.service';
import { ToastService } from '../../shared/ui/toast.service';
import { Booking, BookingsApi } from './bookings.api';
import { ReasonDialog, ReasonDialogData, ReasonResult } from './reason-dialog';

/**
 * Acciones de reservas con sus confirmaciones, compartidas por el detalle del viaje,
 * Mis viajes y la bandeja del conductor. Devuelven el resultado o null si no se hizo.
 */
@Injectable({ providedIn: 'root' })
export class BookingActions {
  private readonly api = inject(BookingsApi);
  private readonly dialogs = inject(DialogService);
  private readonly toast = inject(ToastService);
  private readonly transloco = inject(TranslocoService);

  private t(key: string, params?: Record<string, unknown>): string {
    return this.transloco.translate(key, params);
  }

  private async askReason(data: ReasonDialogData): Promise<ReasonResult | undefined> {
    const ref = this.dialogs.open<ReasonResult, ReasonDialogData, ReasonDialog>(ReasonDialog, data);
    return firstValueFrom(ref.closed);
  }

  private async run<T>(action: () => Promise<T>, done: string): Promise<T | null> {
    try {
      const result = await action();
      this.toast.show(this.t(done), 'success');
      return result;
    } catch (error) {
      this.toast.show(apiErrorMessage(this.transloco, error), 'danger');
      return null;
    }
  }

  /**
   * Cancela directo cuando se puede; si el viaje esta cerca, pide el motivo y crea la
   * solicitud de cancelacion para el conductor.
   */
  async cancel(bookingId: string, late = false): Promise<Booking | null> {
    if (!late) {
      const ok = await this.dialogs.confirm({
        title: this.t('bookings.cancel.title'),
        message: this.t('bookings.cancel.message'),
        confirmLabel: this.t('bookings.cancel.confirm'),
        cancelLabel: this.t('bookings.reason.back'),
        danger: true,
      });
      if (!ok) return null;
      try {
        const booking = await this.api.cancel(bookingId, null);
        this.toast.show(this.t('bookings.cancel.done'), 'success');
        return booking;
      } catch (error) {
        if (apiErrorCode(error) !== 'CANCEL_REASON_REQUIRED') {
          this.toast.show(apiErrorMessage(this.transloco, error), 'danger');
          return null;
        }
      }
    }
    const answer = await this.askReason({
      title: this.t('bookings.cancel.lateTitle'),
      message: this.t('bookings.cancel.lateMessage'),
      confirmLabel: this.t('bookings.cancel.lateConfirm'),
      required: true,
      danger: true,
    });
    if (!answer?.reason) return null;
    return this.run(() => this.api.cancel(bookingId, answer.reason), 'bookings.cancel.requested');
  }

  accept(bookingId: string): Promise<Booking | null> {
    return this.run(() => this.api.accept(bookingId), 'bookings.inbox.accepted');
  }

  async reject(bookingId: string): Promise<Booking | null> {
    const answer = await this.askReason({
      title: this.t('bookings.inbox.rejectTitle'),
      message: this.t('bookings.inbox.rejectMessage'),
      confirmLabel: this.t('bookings.inbox.reject'),
      required: false,
      danger: true,
    });
    if (!answer) return null;
    return this.run(() => this.api.reject(bookingId, answer.reason), 'bookings.inbox.rejected');
  }

  resolveCancellation(bookingId: string, accept: boolean): Promise<Booking | null> {
    return this.run(
      () => this.api.resolveCancellation(bookingId, accept),
      accept ? 'bookings.inbox.cancellationAccepted' : 'bookings.inbox.cancellationRejected',
    );
  }
}
