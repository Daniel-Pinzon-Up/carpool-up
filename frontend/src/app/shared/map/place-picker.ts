import {
  ChangeDetectionStrategy,
  Component,
  computed,
  forwardRef,
  inject,
  input,
  signal,
} from '@angular/core';
import { NG_VALUE_ACCESSOR } from '@angular/forms';
import { TranslocoPipe, TranslocoService } from '@jsverse/transloco';
import { LucideMapPin, LucideMapPinned, LucideX } from '@icons';
import { firstValueFrom } from 'rxjs';
import { DialogService } from '../ui/dialog.service';
import { FIELD_CLASSES, FormControlBase, uniqueId } from '../ui/form-control';
import { MapPickDialog } from './map-pick-dialog';
import { Place, PlaceValue, PlacesApi, toPlaceValue } from './places.api';

interface Option {
  id: string; // id del elemento en el DOM
  group: 'recent' | 'campus' | 'sector' | 'landmark';
  value: PlaceValue;
}

/**
 * Combobox de lugares (patron ARIA): recientes y catalogo filtrados al escribir,
 * mas la opcion de elegir un punto en el mapa.
 */
@Component({
  selector: 'cp-place-picker',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [TranslocoPipe, LucideMapPin, LucideMapPinned, LucideX],
  providers: [
    { provide: NG_VALUE_ACCESSOR, useExisting: forwardRef(() => PlacePicker), multi: true },
  ],
  host: { class: 'block' },
  template: `
    <label [for]="id" class="mb-1.5 block text-sm font-medium">{{ label() }}</label>
    @if (value(); as place) {
      <div class="glass-1 !rounded-2xl flex min-h-11 items-center gap-3 px-4 py-2">
        <svg lucideMapPin class="size-5 shrink-0 text-accent" aria-hidden="true"></svg>
        <span class="min-w-0 flex-1 truncate font-medium" [id]="id">{{ place.name }}</span>
        <button
          type="button"
          class="-mr-2 grid size-10 shrink-0 place-items-center rounded-full text-muted hover:text-text"
          [disabled]="disabled()"
          [attr.aria-label]="'places.clear' | transloco: { name: place.name }"
          (click)="clear()"
        >
          <svg lucideX class="size-5" aria-hidden="true"></svg>
        </button>
      </div>
    } @else {
      <div class="relative">
        <input
          [id]="id"
          type="text"
          role="combobox"
          autocomplete="off"
          [class]="fieldClasses()"
          [value]="query()"
          [placeholder]="'places.placeholder' | transloco"
          [disabled]="disabled()"
          [attr.aria-expanded]="open()"
          [attr.aria-controls]="listId"
          aria-autocomplete="list"
          [attr.aria-activedescendant]="activeOptionId()"
          [attr.aria-invalid]="error() ? true : null"
          [attr.aria-describedby]="error() ? id + '-error' : null"
          (input)="onInput($any($event.target).value)"
          (focus)="openList()"
          (blur)="onBlur()"
          (keydown)="onKeydown($event)"
        />
        @if (open()) {
          <ul
            [id]="listId"
            role="listbox"
            [attr.aria-label]="label()"
            class="glass-2 !rounded-2xl absolute inset-x-0 top-full z-20 mt-2 max-h-72 overflow-y-auto p-2"
          >
            @for (option of options(); track option.id; let i = $index) {
              @if (i === 0 || options()[i - 1].group !== option.group) {
                <li
                  role="presentation"
                  class="px-3 pt-2 pb-1 text-xs font-semibold tracking-wide text-muted uppercase"
                >
                  {{ 'places.groups.' + option.group | transloco }}
                </li>
              }
              <li
                [id]="option.id"
                role="option"
                [attr.aria-selected]="i === active()"
                class="flex min-h-11 cursor-pointer items-center gap-2 rounded-xl px-3"
                [class.bg-accent/15]="i === active()"
                (mousedown)="$event.preventDefault()"
                tabindex="-1"
                (click)="choose(option.value)"
                (keydown.enter)="choose(option.value)"
              >
                <svg lucideMapPin class="size-4 shrink-0 text-muted" aria-hidden="true"></svg>
                {{ option.value.name }}
              </li>
            } @empty {
              <li role="presentation" class="px-3 py-2 text-sm text-muted">
                {{ 'places.noMatches' | transloco }}
              </li>
            }
          </ul>
        }
      </div>
      <button
        type="button"
        class="mt-2 inline-flex min-h-11 items-center gap-2 rounded-full px-1 text-sm font-semibold text-primary"
        [disabled]="disabled()"
        (click)="pickOnMap()"
      >
        <svg lucideMapPinned class="size-4" aria-hidden="true"></svg>
        {{ 'places.pickOnMap' | transloco }}
      </button>
    }
    @if (error()) {
      <p [id]="id + '-error'" class="mt-1.5 text-sm text-danger">{{ error() }}</p>
    }
  `,
})
export class PlacePicker extends FormControlBase<PlaceValue> {
  readonly label = input.required<string>();
  readonly error = input<string | null>(null);

  private readonly places = inject(PlacesApi);
  private readonly dialogs = inject(DialogService);
  private readonly transloco = inject(TranslocoService);

  protected readonly id = uniqueId('cp-place');
  protected readonly listId = `${this.id}-list`;
  protected readonly query = signal('');
  protected readonly open = signal(false);
  protected readonly active = signal(-1);
  private readonly catalog = signal<Place[]>([]);
  protected readonly fieldClasses = computed(
    () => `${FIELD_CLASSES} ${this.error() ? '!border-danger' : ''}`,
  );

  protected readonly options = computed<Option[]>(() => {
    const text = normalize(this.query());
    const matches = (name: string) => !text || normalize(name).includes(text);
    const recent = text ? [] : this.places.recent();
    const recentIds = new Set(recent.map((p) => p.place_id));
    const groups: Option[] = recent.map((value) => ({ id: '', group: 'recent', value }));
    for (const kind of ['campus', 'sector', 'landmark'] as const) {
      for (const place of this.catalog()) {
        if (place.kind === kind && matches(place.name) && !recentIds.has(place.id)) {
          groups.push({ id: '', group: kind, value: toPlaceValue(place) });
        }
      }
    }
    return groups.map((option, index) => ({ ...option, id: `${this.id}-opt-${index}` }));
  });
  protected readonly activeOptionId = computed(() => this.options()[this.active()]?.id ?? null);

  protected async openList(): Promise<void> {
    this.open.set(true);
    if (this.catalog().length === 0) {
      try {
        this.catalog.set(await this.places.catalog());
      } catch {
        // Sin catalogo queda la opcion de elegir en el mapa.
      }
    }
  }

  protected onInput(text: string): void {
    this.query.set(text);
    this.active.set(0);
    this.open.set(true);
  }

  protected onBlur(): void {
    this.open.set(false);
    this.onTouched();
  }

  protected onKeydown(event: KeyboardEvent): void {
    const count = this.options().length;
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      void this.openList();
      this.active.set(count ? (this.active() + 1) % count : -1);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      this.active.set(count ? (this.active() - 1 + count) % count : -1);
    } else if (event.key === 'Enter' && this.open() && this.options()[this.active()]) {
      event.preventDefault();
      this.choose(this.options()[this.active()].value);
    } else if (event.key === 'Escape') {
      this.open.set(false);
    }
  }

  protected choose(place: PlaceValue): void {
    this.places.remember(place);
    this.query.set('');
    this.open.set(false);
    this.active.set(-1);
    this.update(place);
    this.onTouched();
  }

  protected clear(): void {
    this.update(null);
    queueMicrotask(() => document.getElementById(this.id)?.focus());
  }

  protected async pickOnMap(): Promise<void> {
    const ref = this.dialogs.open<PlaceValue, undefined, MapPickDialog>(
      MapPickDialog,
      undefined,
      'modal',
      {
        width: 'auto',
        maxWidth: '96vw',
      },
    );
    const place = await firstValueFrom(ref.closed);
    if (place) this.choose(place);
  }
}

function normalize(text: string): string {
  return text.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();
}
