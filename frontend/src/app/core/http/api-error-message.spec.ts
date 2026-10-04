import { TestBed } from '@angular/core/testing';
import { TranslocoService } from '@jsverse/transloco';
import { getTranslocoTestingModule } from '../../../testing/transloco-testing';
import { apiErrorMessage } from './api-error-message';

describe('apiErrorMessage', () => {
  let transloco: TranslocoService;

  beforeEach(() => {
    TestBed.configureTestingModule({ imports: [getTranslocoTestingModule()] });
    transloco = TestBed.inject(TranslocoService);
  });

  it('traduce el codigo de la API', () => {
    expect(apiErrorMessage(transloco, { code: 'EMAIL_TAKEN', details: {} })).toContain(
      'Ya existe una cuenta',
    );
  });

  it('convierte segundos de espera en minutos legibles', () => {
    const message = apiErrorMessage(transloco, {
      code: 'ACCOUNT_LOCKED',
      details: { retry_after_seconds: 840 },
    });
    expect(message).toContain('14 minutos');
  });

  it('usa un mensaje generico para codigos desconocidos', () => {
    expect(apiErrorMessage(transloco, { code: 'ALGO_RARO', details: {} })).toBe(
      transloco.translate('errors.UNKNOWN_ERROR'),
    );
    expect(apiErrorMessage(transloco, new Error('boom'))).toBe(
      transloco.translate('errors.UNKNOWN_ERROR'),
    );
  });
});
