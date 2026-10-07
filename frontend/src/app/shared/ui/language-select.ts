import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { TranslocoPipe } from '@jsverse/transloco';
import { LucideChevronDown, LucideLanguages } from '@icons';
import { LANGUAGES, Language, LanguageService, isLanguage } from '../../core/i18n/language.service';
import { uniqueId } from './form-control';

/** Selector compacto de idioma para encabezados y perfil. */
@Component({
  selector: 'cp-language-select',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [TranslocoPipe, LucideLanguages, LucideChevronDown],
  template: `
    <label [for]="id" class="sr-only">{{ 'layout.language' | transloco }}</label>
    <div class="glass-1 !rounded-full relative flex min-h-11 items-center">
      <svg
        lucideLanguages
        class="pointer-events-none absolute left-3 size-4 text-muted"
        aria-hidden="true"
      ></svg>
      <select
        [id]="id"
        class="min-h-11 appearance-none rounded-full bg-transparent py-2 pr-9 pl-9 text-sm font-semibold text-text"
        (change)="onChange($any($event.target).value)"
      >
        @for (lang of languages; track lang) {
          <option [value]="lang" [selected]="lang === language.current()">
            {{ 'languages.' + lang | transloco }}
          </option>
        }
      </select>
      <svg
        lucideChevronDown
        class="pointer-events-none absolute right-3 size-4 text-muted"
        aria-hidden="true"
      ></svg>
    </div>
  `,
})
export class LanguageSelect {
  protected readonly language = inject(LanguageService);
  protected readonly languages = LANGUAGES;
  protected readonly id = uniqueId('cp-lang');

  protected onChange(value: string): void {
    if (isLanguage(value)) this.language.set(value as Language);
  }
}
