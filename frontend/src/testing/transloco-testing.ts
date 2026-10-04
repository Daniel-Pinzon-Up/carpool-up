import { TranslocoTestingModule, TranslocoTestingOptions } from '@jsverse/transloco';
import en from '../../public/i18n/en.json';
import es from '../../public/i18n/es.json';

/** Transloco con las traducciones reales en espanol para pruebas de componentes. */
export function getTranslocoTestingModule(options: TranslocoTestingOptions = {}) {
  return TranslocoTestingModule.forRoot({
    langs: { es, en },
    translocoConfig: { availableLangs: ['es', 'en'], defaultLang: 'es' },
    preloadLangs: true,
    ...options,
  });
}
