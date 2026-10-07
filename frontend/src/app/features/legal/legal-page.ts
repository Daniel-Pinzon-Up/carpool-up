import { HttpClient } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';
import { rxResource } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { TranslocoPipe } from '@jsverse/transloco';
import { LucideArrowLeft } from '@icons';
import { marked } from 'marked';
import { LegalDocument, LegalKind } from '../../core/auth/auth.models';
import { LanguageService } from '../../core/i18n/language.service';
import { GlassCard } from '../../shared/ui/glass-card';
import { ErrorState } from '../../shared/ui/error-state';
import { Skeleton } from '../../shared/ui/skeleton';

const KIND_BY_SLUG: Record<string, LegalKind> = { terminos: 'terms', datos: 'data_policy' };

/** Version vigente de los terminos o de la politica de datos, en el idioma activo. */
@Component({
  selector: 'cp-legal-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, TranslocoPipe, ErrorState, GlassCard, Skeleton, LucideArrowLeft],
  styles: `
    :host ::ng-deep .legal h1 {
      font-size: 1.6rem;
      font-weight: 700;
      margin-bottom: 1rem;
    }
    :host ::ng-deep .legal h2 {
      font-size: 1.15rem;
      font-weight: 700;
      margin: 1.5rem 0 0.5rem;
    }
    :host ::ng-deep .legal p,
    :host ::ng-deep .legal li {
      color: var(--text-muted);
      line-height: 1.7;
    }
    :host ::ng-deep .legal ul {
      list-style: disc;
      padding-left: 1.25rem;
      margin: 0.5rem 0;
    }
    :host ::ng-deep .legal blockquote {
      border-left: 4px solid var(--warning);
      padding: 0.5rem 1rem;
      margin: 1rem 0;
      background: color-mix(in srgb, var(--warning) 10%, transparent);
      border-radius: 0.75rem;
    }
    :host ::ng-deep .legal strong {
      color: var(--text);
    }
  `,
  template: `
    <div class="mx-auto max-w-3xl px-4 py-6 sm:py-10">
      <a
        routerLink="/"
        class="mb-4 inline-flex items-center gap-2 rounded text-sm font-semibold text-primary"
      >
        <svg lucideArrowLeft class="size-4" aria-hidden="true"></svg>
        {{ 'legal.back' | transloco }}
      </a>
      <cp-glass-card [level]="2" class="!p-6 sm:!p-10">
        @if (documents.isLoading()) {
          <div aria-busy="true"><cp-skeleton [lines]="8" /></div>
        } @else if (documents.error()) {
          <cp-error-state (retry)="documents.reload()" />
        } @else if (html(); as body) {
          <article class="legal" [innerHTML]="body"></article>
          <p class="mt-8 text-sm text-muted">
            {{ 'legal.version' | transloco: { version: doc()?.version, date: publishedOn() } }}
          </p>
        } @else {
          <p class="text-muted">{{ 'legal.unavailable' | transloco }}</p>
        }
      </cp-glass-card>
    </div>
  `,
})
export default class LegalPage {
  /** Viene de la ruta /legal/:kind (terminos o datos). */
  readonly kind = input.required<string>();

  private readonly http = inject(HttpClient);
  private readonly language = inject(LanguageService);

  protected readonly documents = rxResource({
    params: () => ({ language: this.language.current() }),
    stream: ({ params }) => this.http.get<LegalDocument[]>('/api/v1/legal/current', { params }),
  });
  protected readonly doc = computed(() =>
    this.documents.value()?.find((d) => d.kind === KIND_BY_SLUG[this.kind()]),
  );
  /** Angular sanea el HTML al asignarlo con [innerHTML]. */
  protected readonly html = computed(() => {
    const doc = this.doc();
    return doc ? (marked.parse(doc.body_markdown, { async: false }) as string) : null;
  });
  protected readonly publishedOn = computed(() => {
    const doc = this.doc();
    return doc
      ? new Date(doc.published_at).toLocaleDateString(this.language.current(), {
          dateStyle: 'long',
        })
      : '';
  });
}
