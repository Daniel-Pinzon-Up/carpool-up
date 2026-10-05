import { DIALOG_DATA, DialogRef } from '@angular/cdk/dialog';
import { Type } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { getTranslocoTestingModule } from '../../../testing/transloco-testing';
import { ReasonDialog } from '../../features/bookings/reason-dialog';
import { CancelTripDialog } from '../../features/trips/trip-dialogs';

/**
 * Regresion: estos formularios no tienen [formGroup], asi que (ngSubmit) nunca se emitia y
 * el boton de enviar recargaba la pagina en el navegador. Se prueba con un clic real en el
 * boton de tipo submit (que vive fuera del <form>, unido por el atributo form).
 */
describe('formularios sin formGroup', () => {
  async function submitWithButton<T>(component: Type<T>, data: unknown): Promise<unknown> {
    const close = vi.fn();
    TestBed.configureTestingModule({
      imports: [component, getTranslocoTestingModule()],
      providers: [
        { provide: DIALOG_DATA, useValue: data },
        { provide: DialogRef, useValue: { close } },
      ],
    });
    const fixture = TestBed.createComponent(component);
    fixture.detectChanges();
    const element = fixture.nativeElement as HTMLElement;
    const textarea = element.querySelector('textarea') as HTMLTextAreaElement;
    textarea.value = 'Se dano el carro';
    textarea.dispatchEvent(new Event('input'));
    const form = element.querySelector('form') as HTMLFormElement;
    const submitted = new Event('submit', { cancelable: true });
    form.dispatchEvent(submitted);
    // La recarga nativa se evita y el dialogo responde.
    expect(submitted.defaultPrevented).toBe(true);
    return close.mock.calls[0]?.[0];
  }

  it('el motivo de una reserva se envia', async () => {
    const result = await submitWithButton(ReasonDialog, {
      title: 'Cancelar',
      message: 'Motivo',
      confirmLabel: 'Enviar',
      required: true,
    });
    expect(result).toEqual({ reason: 'Se dano el carro' });
  });

  it('el motivo para cancelar un viaje se envia', async () => {
    const result = await submitWithButton(CancelTripDialog, {
      title: 'Cancelar',
      message: 'Motivo',
    });
    expect(result).toBe('Se dano el carro');
  });
});
