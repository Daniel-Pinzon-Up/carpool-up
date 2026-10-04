import { ChangeDetectionStrategy, Component } from '@angular/core';
import { LanguageSelect } from '../../shared/ui/language-select';
import { ThemeToggle } from '../../shared/ui/theme-toggle';
import Catalog from './catalog';

/** El catalogo con su propio encabezado: se revisa sin iniciar sesion. */
@Component({
  selector: 'cp-catalog-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [Catalog, LanguageSelect, ThemeToggle],
  template: `
    <header class="flex justify-end gap-2 px-4 pt-4 sm:px-8">
      <cp-language-select />
      <cp-theme-toggle />
    </header>
    <main id="main" class="px-4 pb-16 sm:px-8"><cp-catalog /></main>
  `,
})
export default class CatalogPage {}
