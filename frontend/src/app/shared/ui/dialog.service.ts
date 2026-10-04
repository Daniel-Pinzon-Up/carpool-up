import { Dialog, DialogConfig, DialogRef } from '@angular/cdk/dialog';
import { createGlobalPositionStrategy } from '@angular/cdk/overlay';
import { ComponentType } from '@angular/cdk/portal';
import { Injectable, Injector, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { ConfirmDialog, ConfirmDialogData } from './confirm-dialog';

export type DialogVariant = 'modal' | 'sheet';

/**
 * Abre modales y hojas inferiores sobre Angular CDK, que aporta rol de dialogo, aria-modal,
 * foco atrapado, cierre con Escape y retorno del foco al cerrar.
 * El contenido debe usar <cp-glass-modal> con el mismo variant.
 */
@Injectable({ providedIn: 'root' })
export class DialogService {
  private readonly dialog = inject(Dialog);
  private readonly injector = inject(Injector);

  open<R, D, C>(
    component: ComponentType<C>,
    data?: D,
    variant: DialogVariant = 'modal',
    config: DialogConfig<D, DialogRef<R, C>> = {},
  ): DialogRef<R, C> {
    const sheet = variant === 'sheet';
    const position = createGlobalPositionStrategy(this.injector).centerHorizontally();
    return this.dialog.open<R, D, C>(component, {
      data,
      autoFocus: 'first-tabbable',
      restoreFocus: true,
      width: sheet ? '100%' : 'min(92vw, 32rem)',
      maxWidth: sheet ? '40rem' : '92vw',
      panelClass: sheet ? 'cp-sheet-pane' : 'cp-modal-pane',
      positionStrategy: sheet ? position.bottom('0') : position.centerVertically(),
      ...config,
    });
  }

  /** Confirmacion para acciones destructivas. Resuelve true solo si el usuario confirma. */
  async confirm(data: ConfirmDialogData): Promise<boolean> {
    const ref = this.open<boolean, ConfirmDialogData, ConfirmDialog>(ConfirmDialog, data);
    return (await firstValueFrom(ref.closed)) === true;
  }
}
