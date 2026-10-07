import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { FormBuilder, FormControl, ReactiveFormsModule } from '@angular/forms';
import { TranslocoPipe, TranslocoService } from '@jsverse/transloco';
import { LucideArrowUpDown, LucideCircleAlert, LucideSearch, LucideSearchX } from '@icons';
import { AuthService } from '../../core/auth/auth.service';
import { apiErrorMessage } from '../../core/http/api-error-message';
import { readPref, writePref } from '../../core/storage/local-preferences';
import { PlacePicker } from '../../shared/map/place-picker';
import { PlaceValue } from '../../shared/map/places.api';
import { EmptyState } from '../../shared/ui/empty-state';
import { GlassButton } from '../../shared/ui/glass-button';
import { GlassCard } from '../../shared/ui/glass-card';
import { GlassChip } from '../../shared/ui/glass-chip';
import { GlassInput } from '../../shared/ui/glass-input';
import { SeatPicker } from '../../shared/ui/seat-picker';
import { Skeleton } from '../../shared/ui/skeleton';
import { pamplonaDate, pamplonaTime } from '../trips/trips.api';
import { SearchedPlaces } from '../bookings/booking-panel';
import { ResultCard } from './result-card';
import { PREFERENCE_KEYS, SearchApi, SearchPreferences, SearchResult } from './search.api';

const LAST_SEARCH_KEY = 'cp.lastSearch';

interface SavedSearch extends SearchPreferences {
  origin: PlaceValue;
  destination: PlaceValue;
  date: string;
  time: string;
  seats: number;
}

/**
 * Buscar viajes: origen y destino, fecha, hora, puestos y preferencias. La ultima busqueda
 * se recuerda en el dispositivo para repetirla al volver (flexibilidad).
 */
@Component({
  selector: 'cp-search-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    ReactiveFormsModule,
    TranslocoPipe,
    EmptyState,
    GlassButton,
    GlassCard,
    GlassChip,
    GlassInput,
    PlacePicker,
    ResultCard,
    SeatPicker,
    Skeleton,
    LucideArrowUpDown,
    LucideCircleAlert,
    LucideSearch,
  ],
  template: `
    <div class="mx-auto flex max-w-5xl flex-col gap-5 py-2">
      <header class="flex items-center justify-between gap-4">
        <div>
          <h1 class="text-2xl font-bold sm:text-3xl">{{ 'search.title' | transloco }}</h1>
          <p class="text-muted">{{ 'search.subtitle' | transloco }}</p>
        </div>
        <img
          src="brand/pickup.webp"
          alt=""
          width="720"
          height="536"
          class="hidden h-28 w-auto shrink-0 md:block"
        />
      </header>

      <cp-glass-card [level]="2">
        <form [formGroup]="form" class="flex flex-col gap-4" (ngSubmit)="search()" novalidate>
          <div class="grid gap-4 md:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] md:items-start">
            <cp-place-picker formControlName="origin" [label]="'search.origin' | transloco" />
            <button
              type="button"
              class="grid size-11 place-items-center self-center rounded-full text-muted hover:bg-glass hover:text-text md:mt-7"
              [attr.aria-label]="'search.swap' | transloco"
              (click)="swap()"
            >
              <svg lucideArrowUpDown class="size-5 md:rotate-90" aria-hidden="true"></svg>
            </button>
            <cp-place-picker
              formControlName="destination"
              [label]="'search.destination' | transloco"
            />
          </div>
          <div class="grid gap-4 sm:grid-cols-3">
            <cp-glass-input
              formControlName="date"
              type="date"
              [label]="'publish.when.date' | transloco"
            />
            <cp-glass-input
              formControlName="time"
              type="time"
              [label]="'search.time' | transloco"
              [hint]="'publish.when.timeHint' | transloco"
            />
            <cp-seat-picker
              formControlName="seats"
              [label]="'search.seats' | transloco"
              [min]="1"
              [max]="4"
            />
          </div>
          <fieldset>
            <legend class="mb-2 text-sm font-medium">{{ 'search.preferences' | transloco }}</legend>
            <div class="flex flex-wrap gap-2">
              @for (key of preferenceKeys(); track key) {
                <cp-glass-chip [selected]="prefs()[key]" (selectedChange)="setPref(key, $event)">
                  {{ 'search.prefs.' + key | transloco }}
                </cp-glass-chip>
              }
            </div>
          </fieldset>
          @if (formError()) {
            <p role="alert" class="flex gap-2 text-sm text-danger">
              <svg lucideCircleAlert class="size-5 shrink-0" aria-hidden="true"></svg>
              {{ formError() }}
            </p>
          }
          <button cp-button type="submit" class="self-start" [disabled]="loading()">
            <svg lucideSearch class="size-4" aria-hidden="true"></svg>
            {{ 'search.submit' | transloco }}
          </button>
        </form>
      </cp-glass-card>

      <section
        aria-labelledby="results-title"
        aria-live="polite"
        [attr.aria-busy]="loading()"
        class="flex flex-col gap-3"
      >
        @if (results() !== null || loading()) {
          <h2 id="results-title" class="text-xl font-bold">
            {{
              loading()
                ? ('search.searching' | transloco)
                : ('search.results' | transloco: { count: results()!.length })
            }}
          </h2>
        }
        @if (loading()) {
          @for (row of [1, 2, 3]; track row) {
            <cp-glass-card><cp-skeleton [lines]="3" /></cp-glass-card>
          }
        } @else if (results(); as list) {
          @for (result of list; track result.trip_id) {
            <cp-result-card [result]="result" [places]="searchedPlaces()" />
          } @empty {
            <cp-empty-state
              [title]="'search.empty.title' | transloco"
              [description]="'search.empty.hint' | transloco"
              [icon]="emptyIcon"
              image="brand/car.webp"
            />
          }
        }
      </section>
    </div>
  `,
})
export default class SearchPage {
  private readonly api = inject(SearchApi);
  private readonly auth = inject(AuthService);
  private readonly transloco = inject(TranslocoService);
  private readonly fb = inject(FormBuilder);

  protected readonly emptyIcon = LucideSearchX;
  protected readonly form = this.fb.nonNullable.group({
    origin: new FormControl<PlaceValue | null>(null),
    destination: new FormControl<PlaceValue | null>(null),
    date: pamplonaDate(new Date()),
    time: nextHalfHour(),
    seats: 1,
  });
  protected readonly prefs = signal<SearchPreferences>({
    pets: false,
    luggage: false,
    no_smoking: false,
    music: false,
    women_only: false,
  });
  /** "Solo mujeres" solo tiene sentido para pasajeras (a los demas no se les ofrecen). */
  protected readonly preferenceKeys = computed(() =>
    PREFERENCE_KEYS.filter((key) => key !== 'women_only' || this.auth.user()?.sex === 'female'),
  );
  protected readonly results = signal<SearchResult[] | null>(null);
  protected readonly searchedPlaces = signal<SearchedPlaces | null>(null);
  protected readonly loading = signal(false);
  protected readonly formError = signal<string | null>(null);

  constructor() {
    this.restore();
  }

  private restore(): void {
    try {
      const saved = JSON.parse(readPref(LAST_SEARCH_KEY) ?? 'null') as SavedSearch | null;
      if (!saved?.origin || !saved.destination) return;
      const today = pamplonaDate(new Date());
      const date = saved.date >= today ? saved.date : today;
      this.form.patchValue({ ...saved, date });
      this.prefs.set({
        pets: !!saved.pets,
        luggage: !!saved.luggage,
        no_smoking: !!saved.no_smoking,
        music: !!saved.music,
        women_only: !!saved.women_only,
      });
      void this.search();
    } catch {
      // Una busqueda guardada ilegible se ignora.
    }
  }

  protected setPref(key: keyof SearchPreferences, on: boolean): void {
    this.prefs.update((prefs) => ({ ...prefs, [key]: on }));
  }

  protected swap(): void {
    const { origin, destination } = this.form.getRawValue();
    this.form.patchValue({ origin: destination, destination: origin });
  }

  protected async search(): Promise<void> {
    const { origin, destination, date, time, seats } = this.form.getRawValue();
    if (!origin || !destination) {
      this.formError.set(this.transloco.translate('publish.errors.route'));
      return;
    }
    if (!date || !time) {
      this.formError.set(this.transloco.translate('search.errors.when'));
      return;
    }
    this.formError.set(null);
    const prefs = this.prefs();
    const saved: SavedSearch = { origin, destination, date, time, seats, ...prefs };
    writePref(LAST_SEARCH_KEY, JSON.stringify(saved));
    this.loading.set(true);
    this.searchedPlaces.set({ pickup: origin, dropoff: destination });
    try {
      this.results.set(
        await this.api.search({
          origin_place_id: origin.place_id,
          destination_place_id: destination.place_id,
          date,
          time,
          seats,
          ...prefs,
          women_only: prefs.women_only && this.auth.user()?.sex === 'female',
        }),
      );
    } catch (error) {
      this.results.set(null);
      this.formError.set(apiErrorMessage(this.transloco, error));
    } finally {
      this.loading.set(false);
    }
  }
}

/** Siguiente media hora en Pamplona (hora por defecto de la busqueda). */
export function nextHalfHour(now = new Date()): string {
  const [h, m] = pamplonaTime(now).split(':').map(Number);
  const minutes = ((Math.floor((h * 60 + m) / 30) + 1) * 30) % (24 * 60);
  return `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`;
}
