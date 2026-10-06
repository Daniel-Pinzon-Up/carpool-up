import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  effect,
  inject,
  input,
  output,
  signal,
  untracked,
  viewChild,
} from '@angular/core';
import { TranslocoPipe } from '@jsverse/transloco';
import type { GeoJSONSource, Map as MapLibreMap, Marker } from 'maplibre-gl';
import { LanguageService } from '../../core/i18n/language.service';
import { ThemeService } from '../../core/theme/theme.service';
import { MAP_BOUNDS, PAMPLONA_CENTER, ROUTE_COLORS, buildMapStyle } from './map-style';

export type MarkerKind = 'origin' | 'stop' | 'destination' | 'pin' | 'vehicle';

export interface MapMarker {
  lat: number;
  lon: number;
  kind: MarkerKind;
  label: string;
}

export interface PickedPoint {
  lat: number;
  lon: number;
}

const MARKER_COLORS: Record<MarkerKind, string> = {
  origin: 'var(--accent)',
  stop: 'var(--primary)',
  destination: 'var(--danger)',
  pin: 'var(--warning)',
  vehicle: 'var(--success)',
};

let protocolReady: Promise<void> | null = null;
let stylesReady: Promise<void> | null = null;

/** La hoja de MapLibre se publica aparte (angular.json) y solo se carga cuando hay un mapa. */
function ensureMapStyles(): Promise<void> {
  stylesReady ??= new Promise((resolve) => {
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = 'maplibre.css';
    // Si falla, el mapa funciona igual; solo pierde el estilo de los controles.
    link.onload = link.onerror = () => resolve();
    document.head.appendChild(link);
  });
  return stylesReady;
}

/** Registra una sola vez el protocolo pmtiles:// en MapLibre. */
async function ensurePmtilesProtocol(maplibre: typeof import('maplibre-gl')): Promise<void> {
  protocolReady ??= import('pmtiles').then(({ Protocol }) => {
    const protocol = new Protocol();
    maplibre.addProtocol('pmtiles', protocol.tile);
  });
  return protocolReady;
}

/**
 * Mapa de MapLibre con teselas propias. Dibuja una ruta y marcadores y, si es seleccionable,
 * emite el punto tocado. El mapa es complementario: la informacion siempre esta tambien en texto.
 */
@Component({
  selector: 'cp-map-view',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [TranslocoPipe],
  host: { class: 'relative block overflow-hidden rounded-2xl bg-glass' },
  template: `
    <div
      #container
      class="size-full"
      role="region"
      [attr.aria-label]="label() || ('map.label' | transloco)"
      [attr.aria-describedby]="pickable() ? hintId : null"
    ></div>
    @if (pickable()) {
      <p
        [id]="hintId"
        class="pointer-events-none absolute inset-x-3 top-3 rounded-xl bg-[var(--surface-2-solid)]/90 px-3 py-2 text-center text-sm font-medium shadow"
      >
        {{ 'map.pickHint' | transloco }}
      </p>
    }
    @if (failed()) {
      <p
        role="alert"
        class="absolute inset-0 grid place-items-center p-6 text-center text-sm text-muted"
      >
        {{ 'map.unavailable' | transloco }}
      </p>
    }
  `,
})
export class MapView {
  /** Ruta en GeoJSON: [[lon, lat], ...]. */
  readonly route = input<number[][] | null>(null);
  readonly markers = input<MapMarker[]>([]);
  readonly pickable = input(false);
  readonly label = input('');
  readonly picked = output<PickedPoint>();

  private readonly container = viewChild.required<ElementRef<HTMLDivElement>>('container');
  private readonly theme = inject(ThemeService);
  private readonly language = inject(LanguageService);
  private map: MapLibreMap | null = null;
  private maplibre: typeof import('maplibre-gl') | null = null;
  private placedMarkers: Marker[] = [];
  private readonly ready = signal(false);
  protected readonly failed = signal(false);
  protected readonly hintId = `cp-map-hint-${Math.random().toString(36).slice(2, 8)}`;

  constructor() {
    const destroyRef = inject(DestroyRef);
    destroyRef.onDestroy(() => this.map?.remove());
    queueMicrotask(() => void this.init());

    // Tema o idioma: se cambia el estilo y se vuelven a dibujar la ruta y los marcadores.
    effect(() => {
      const dark = this.theme.isDark();
      const lang = this.language.current();
      if (!untracked(this.ready)) return;
      void buildMapStyle(dark, lang).then((style) => this.map?.setStyle(style));
    });
    effect(() => {
      const route = this.route();
      if (this.ready()) this.drawRoute(route);
    });
    effect(() => {
      const markers = this.markers();
      if (this.ready()) this.drawMarkers(markers);
    });
  }

  private async init(): Promise<void> {
    try {
      const [maplibre] = await Promise.all([import('maplibre-gl'), ensureMapStyles()]);
      await ensurePmtilesProtocol(maplibre);
      this.maplibre = maplibre;
      const style = await buildMapStyle(this.theme.isDark(), this.language.current());
      const map = new maplibre.Map({
        container: this.container().nativeElement,
        style,
        center: PAMPLONA_CENTER,
        zoom: 13.5,
        maxBounds: MAP_BOUNDS,
        attributionControl: { compact: true },
        cooperativeGestures: false,
      });
      map.addControl(new maplibre.NavigationControl({ showCompass: false }), 'bottom-right');
      map.on('style.load', () => {
        this.addRouteLayers();
        this.drawRoute(this.route());
      });
      map.on('click', (event) => {
        if (this.pickable()) this.picked.emit({ lat: event.lngLat.lat, lon: event.lngLat.lng });
      });
      this.map = map;
      map.once('load', () => {
        this.ready.set(true);
        this.drawMarkers(this.markers());
      });
    } catch {
      this.failed.set(true);
    }
  }

  private addRouteLayers(): void {
    const map = this.map;
    if (!map || map.getSource('route')) return;
    const colors = this.theme.isDark() ? ROUTE_COLORS.dark : ROUTE_COLORS.light;
    map.addSource('route', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
    map.addLayer({
      id: 'route-casing',
      type: 'line',
      source: 'route',
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': colors.casing, 'line-width': 9 },
    });
    map.addLayer({
      id: 'route-line',
      type: 'line',
      source: 'route',
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': colors.route, 'line-width': 5 },
    });
  }

  private drawRoute(route: number[][] | null): void {
    const map = this.map;
    const source = map?.getSource('route') as GeoJSONSource | undefined;
    if (!map || !source || !this.maplibre) return;
    source.setData(
      route && route.length > 1
        ? { type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: route } }
        : { type: 'FeatureCollection', features: [] },
    );
    if (route && route.length > 1) {
      const bounds = route.reduce(
        (box, coord) => box.extend(coord as [number, number]),
        new this.maplibre.LngLatBounds(route[0] as [number, number], route[0] as [number, number]),
      );
      map.fitBounds(bounds, {
        padding: 48,
        duration: matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 400,
      });
    }
  }

  private drawMarkers(markers: MapMarker[]): void {
    const maplibre = this.maplibre;
    const map = this.map;
    if (!maplibre || !map) return;
    this.placedMarkers.forEach((marker) => marker.remove());
    this.placedMarkers = markers.map((item) => {
      const element = document.createElement('div');
      element.className = 'cp-map-marker';
      element.style.background = MARKER_COLORS[item.kind];
      element.setAttribute('role', 'img');
      element.setAttribute('aria-label', item.label);
      element.title = item.label;
      return new maplibre.Marker({ element }).setLngLat([item.lon, item.lat]).addTo(map);
    });
    if (markers.length === 1 && !this.route()) {
      map.easeTo({ center: [markers[0].lon, markers[0].lat], duration: 0 });
    }
  }
}
