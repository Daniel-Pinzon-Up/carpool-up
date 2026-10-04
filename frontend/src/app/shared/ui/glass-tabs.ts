import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  input,
  model,
  viewChildren,
} from '@angular/core';
import { uniqueId } from './form-control';

export interface TabItem {
  id: string;
  label: string;
}

/**
 * Pestanas segun el patron ARIA: flechas, Inicio y Fin mueven el foco y activan la pestana.
 * El panel lo pinta el padre segun el valor de [(selected)], usando panelId(tab.id).
 */
@Component({
  selector: 'cp-glass-tabs',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { class: 'block' },
  template: `
    <div
      role="tablist"
      [attr.aria-label]="label()"
      class="glass-1 !rounded-full inline-flex max-w-full gap-1 overflow-x-auto p-1"
    >
      @for (tab of tabs(); track tab.id; let i = $index) {
        <button
          #tabButton
          type="button"
          role="tab"
          [id]="tabId(tab.id)"
          [attr.aria-selected]="tab.id === selected()"
          [attr.aria-controls]="panelId(tab.id)"
          [tabIndex]="tab.id === selected() ? 0 : -1"
          (click)="selected.set(tab.id)"
          (keydown)="onKeydown($event, i)"
          class="min-h-10 shrink-0 rounded-full px-4 text-sm font-semibold transition duration-200"
          [class]="
            tab.id === selected() ? 'bg-accent text-on-accent shadow' : 'text-muted hover:text-text'
          "
        >
          {{ tab.label }}
        </button>
      }
    </div>
  `,
})
export class GlassTabs {
  readonly tabs = input.required<TabItem[]>();
  readonly label = input.required<string>();
  readonly selected = model.required<string>();

  private readonly buttons = viewChildren<ElementRef<HTMLButtonElement>>('tabButton');
  private readonly prefix = uniqueId('cp-tabs');

  tabId(id: string): string {
    return `${this.prefix}-tab-${id}`;
  }

  panelId(id: string): string {
    return `${this.prefix}-panel-${id}`;
  }

  protected onKeydown(event: KeyboardEvent, index: number): void {
    const count = this.tabs().length;
    const moves: Record<string, number> = {
      ArrowRight: (index + 1) % count,
      ArrowLeft: (index - 1 + count) % count,
      Home: 0,
      End: count - 1,
    };
    const target = moves[event.key];
    if (target === undefined) return;
    event.preventDefault();
    this.selected.set(this.tabs()[target].id);
    this.buttons()[target]?.nativeElement.focus();
  }
}
