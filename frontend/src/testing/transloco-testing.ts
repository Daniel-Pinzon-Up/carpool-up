import { TranslocoTestingModule, TranslocoTestingOptions } from '@jsverse/transloco';
import es from '../../public/i18n/es.json';

/** Transloco con las traducciones reales en espanol para pruebas de componentes. */
export function getTranslocoTestingModule(options: TranslocoTestingOptions = {}) {
  return TranslocoTestingModule.forRoot({
    langs: { es },
    translocoConfig: { availableLangs: ['es'], defaultLang: 'es' },
    preloadLangs: true,
    ...options,
  });
}
