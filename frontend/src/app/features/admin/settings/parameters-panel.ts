import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { toSignal } from '@angular/core/rxjs-interop';
import { TranslocoPipe, TranslocoService } from '@jsverse/transloco';
import { LucideSave } from '@lucide/angular';
import { apiErrorMessage } from '../../../core/http/api-error-message';
import { LanguageService } from '../../../core/i18n/language.service';
import { GlassButton } from '../../../shared/ui/glass-button';
import { GlassCard } from '../../../shared/ui/glass-card';
import { GlassInput } from '../../../shared/ui/glass-input';
import { Skeleton } from '../../../shared/ui/skeleton';
import { ToastService } from '../../../shared/ui/toast.service';
import { AdminApi, SystemSetting } from '../admin.api';

type Editor = 'number' | 'boolean' | 'json';

/** Edita el texto de un valor segun su tipo: numeros y booleanos directo, lo demas en JSON. */
export function editorFor(value: unknown): Editor {
  if (typeof value === 'number') return 'number';
  if (typeof value === 'boolean') return 'boolean';
  return 'json';
}

export function toDraft(value: unknown): string {
  const editor = editorFor(value);
  if (editor === 'json') return JSON.stringify(value, null, 2);
  return String(value);
}

/** Convierte el borrador al tipo original; lanza SyntaxError si el JSON no es valido. */
export function fromDraft(original: unknown, draft: string): unknown {
  switch (editorFor(original)) {
    case 'number':
      return draft.trim() === '' ? NaN : Number(draft);
    case 'boolean':
      return draft === 'true';
    default:
      return JSON.parse(draft);
  }
}

/**
 * Parametros de negocio (system_settings). El servidor valida cada clave con su tipo;
 * aqui solo se convierte el texto y se muestra el error si lo rechaza.
 */
@Component({
  selector: 'cp-parameters-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    ReactiveFormsModule,
    TranslocoPipe,
    GlassButton,
    GlassCard,
    GlassInput,
    Skeleton,
    LucideSave,
  ],
  template: `
    <div class="flex flex-col gap-3">
      <cp-glass-input
        class="sm:max-w-sm"
        type="search"
        [formControl]="filter"
        [label]="'admin.settings.filter' | transloco"
      />
      @if (settings() === null) {
        <cp-glass-card><cp-skeleton [lines]="6" /></cp-glass-card>
      }
      @for (s of visible(); track s.key) {
        <cp-glass-card>
          <form class="flex flex-col gap-2" (submit)="$event.preventDefault(); save(s)">
            <div class="flex flex-wrap items-baseline justify-between gap-2">
              <label class="font-mono text-sm font-semibold" [for]="'setting-' + s.key">{{
                s.key
              }}</label>
              @if (s.updated_at) {
                <span class="text-xs text-muted">{{
                  'admin.settings.updated' | transloco: { when: date(s.updated_at) }
                }}</span>
              }
            </div>
            <p class="text-sm text-muted">{{ s.description }}</p>
            <div class="flex flex-wrap items-end gap-2">
              @switch (editor(s)) {
                @case ('boolean') {
                  <select
                    [id]="'setting-' + s.key"
                    class="glass-1 !rounded-xl min-h-11 px-3"
                    [value]="draft(s)"
                    (change)="edit(s.key, $any($event.target).value)"
                  >
                    <option value="true">{{ 'admin.settings.yes' | transloco }}</option>
                    <option value="false">{{ 'admin.settings.no' | transloco }}</option>
                  </select>
                }
                @case ('number') {
                  <input
                    [id]="'setting-' + s.key"
                    type="number"
                    step="any"
                    class="glass-1 !rounded-xl min-h-11 w-40 px-3"
                    [value]="draft(s)"
                    (input)="edit(s.key, $any($event.target).value)"
                  />
                }
                @default {
                  <textarea
                    [id]="'setting-' + s.key"
                    rows="3"
                    spellcheck="false"
                    class="glass-1 !rounded-xl min-w-0 flex-1 p-3 font-mono text-sm"
                    [value]="draft(s)"
                    (input)="edit(s.key, $any($event.target).value)"
                  ></textarea>
                }
              }
              <button cp-button variant="secondary" type="submit" [disabled]="!changed(s)">
                <svg lucideSave class="size-4" aria-hidden="true"></svg>
                {{ 'admin.settings.save' | transloco }}
              </button>
            </div>
          </form>
        </cp-glass-card>
      }
    </div>
  `,
})
export class ParametersPanel {
  private readonly api = inject(AdminApi);
  private readonly transloco = inject(TranslocoService);
  private readonly language = inject(LanguageService);
  private readonly toast = inject(ToastService);

  protected readonly filter = new FormControl('', { nonNullable: true });
  private readonly term = toSignal(this.filter.valueChanges, { initialValue: '' });
  protected readonly settings = signal<SystemSetting[] | null>(null);
  private readonly drafts = signal<Record<string, string>>({});
  protected readonly visible = computed(() => {
    const term = this.term().trim().toLowerCase();
    return (this.settings() ?? []).filter(
      (s) => !term || s.key.includes(term) || s.description.toLowerCase().includes(term),
    );
  });

  constructor() {
    void this.load();
  }

  private async load(): Promise<void> {
    try {
      this.settings.set(await this.api.settings());
    } catch (error) {
      this.settings.set([]);
      this.toast.show(apiErrorMessage(this.transloco, error), 'danger');
    }
  }

  protected editor(s: SystemSetting): Editor {
    return editorFor(s.value);
  }

  protected draft(s: SystemSetting): string {
    return this.drafts()[s.key] ?? toDraft(s.value);
  }

  protected changed(s: SystemSetting): boolean {
    const draft = this.drafts()[s.key];
    return draft !== undefined && draft !== toDraft(s.value);
  }

  protected edit(key: string, value: string): void {
    this.drafts.update((all) => ({ ...all, [key]: value }));
  }

  protected async save(s: SystemSetting): Promise<void> {
    let value: unknown;
    try {
      value = fromDraft(s.value, this.draft(s));
    } catch {
      this.toast.show(this.transloco.translate('admin.settings.invalidJson'), 'danger');
      return;
    }
    try {
      const updated = await this.api.updateSetting(s.key, value);
      this.settings.update(
        (list) => list?.map((item) => (item.key === updated.key ? updated : item)) ?? null,
      );
      this.drafts.update((all) =>
        Object.fromEntries(Object.entries(all).filter(([key]) => key !== s.key)),
      );
      this.toast.show(this.transloco.translate('admin.settings.saved', { key: s.key }), 'success');
    } catch (error) {
      this.toast.show(apiErrorMessage(this.transloco, error), 'danger');
    }
  }

  protected date(iso: string): string {
    return new Date(iso).toLocaleString(this.language.current(), {
      dateStyle: 'medium',
      timeStyle: 'short',
      timeZone: 'America/Bogota',
    });
  }
}
