import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { getTranslocoTestingModule } from '../../../testing/transloco-testing';
import { buildMapStyle } from './map-style';
import { PlacePicker } from './place-picker';
import { Place, PlacesApi } from './places.api';
import { RouteSummary } from './route-summary';
import { RoutePreview, formatCop } from './routing.api';

async function settle(): Promise<void> {
  for (let i = 0; i < 5; i++) await Promise.resolve();
}

describe('buildMapStyle', () => {
  it('usa solo recursos propios: teselas, fuentes y sprites del mismo origen', async () => {
    const style = await buildMapStyle();
    const origin = location.origin;
    expect(style.glyphs).toBe(`${origin}/map/fonts/{fontstack}/{range}.pbf`);
    expect(style.sprite).toBe(`${origin}/map/sprites/light`);
    expect(JSON.stringify(style.sources)).toContain(`pmtiles://${origin}/tiles/pamplona.pmtiles`);
    expect(style.layers.length).toBeGreaterThan(10);
  });
});

describe('formatCop', () => {
  it('formatea pesos sin decimales', () => {
    const text = formatCop(4300, 'es');
    expect(text).toContain('4.300');
    expect(text).not.toContain(',00');
  });
});

const PREVIEW: RoutePreview = {
  geometry: [
    [-72.6495, 7.387],
    [-72.6512, 7.3712],
  ],
  distance_m: 3471,
  duration_s: 400,
  points: [
    {
      place_id: 'a',
      name: 'Ciudad Universitaria',
      lat: 7.387,
      lon: -72.6495,
      eta_offset_s: 0,
      eta: null,
    },
    { place_id: null, name: null, lat: 7.376, lon: -72.646, eta_offset_s: 170, eta: null },
    { place_id: 'b', name: 'Terminal', lat: 7.3712, lon: -72.6512, eta_offset_s: 400, eta: null },
  ],
  pricing_configured: true,
  suggested_price: 1200,
  max_price_per_seat: 5000,
};

describe('RouteSummary', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({ imports: [RouteSummary, getTranslocoTestingModule()] });
  });

  it('muestra distancia, duracion, precio y las paradas en texto', () => {
    const fixture = TestBed.createComponent(RouteSummary);
    fixture.componentRef.setInput('preview', PREVIEW);
    fixture.detectChanges();
    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('3,5 km');
    expect(text).toContain('7 min');
    expect(text).toContain('1.200');
    expect(text).toContain('Máximo permitido');
    const stops = fixture.nativeElement.querySelectorAll('li');
    expect(stops.length).toBe(3);
    expect(stops[1].textContent).toContain('Punto en el mapa');
    expect(stops[2].textContent).toContain('+7 min');
  });

  it('explica cuando el aporte no esta configurado', () => {
    const fixture = TestBed.createComponent(RouteSummary);
    fixture.componentRef.setInput('preview', {
      ...PREVIEW,
      pricing_configured: false,
      suggested_price: null,
      max_price_per_seat: null,
    });
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('aún no está configurado');
  });
});

const CATALOG: Place[] = [
  {
    id: 'c1',
    name: 'Ciudad Universitaria',
    kind: 'campus',
    lat: 7.387,
    lon: -72.6495,
    is_active: true,
  },
  { id: 's1', name: 'Barrio Chapinero', kind: 'sector', lat: 7.37, lon: -72.64, is_active: true },
  {
    id: 'l1',
    name: 'Parque Principal Águeda Gallardo',
    kind: 'landmark',
    lat: 7.375,
    lon: -72.648,
    is_active: true,
  },
];

describe('PlacePicker', () => {
  let api: {
    catalog: ReturnType<typeof vi.fn>;
    remember: ReturnType<typeof vi.fn>;
    recent: () => [];
  };

  beforeEach(() => {
    api = { catalog: vi.fn().mockResolvedValue(CATALOG), remember: vi.fn(), recent: () => [] };
    TestBed.configureTestingModule({
      imports: [PlacePicker, getTranslocoTestingModule()],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: PlacesApi, useValue: api },
      ],
    });
  });

  async function open() {
    const fixture = TestBed.createComponent(PlacePicker);
    fixture.componentRef.setInput('label', 'Origen');
    const onChange = vi.fn();
    fixture.componentInstance.registerOnChange(onChange);
    fixture.detectChanges();
    const input = fixture.nativeElement.querySelector('input[role=combobox]') as HTMLInputElement;
    input.dispatchEvent(new Event('focus'));
    await settle();
    fixture.detectChanges();
    return { fixture, input, onChange };
  }

  it('agrupa el catalogo y filtra sin importar tildes', async () => {
    const { fixture, input } = await open();
    expect(input.getAttribute('aria-expanded')).toBe('true');
    expect(fixture.nativeElement.querySelectorAll('[role=option]').length).toBe(3);
    expect(fixture.nativeElement.textContent).toContain('Sedes');

    input.value = 'agueda';
    input.dispatchEvent(new Event('input'));
    fixture.detectChanges();
    const options = fixture.nativeElement.querySelectorAll('[role=option]');
    expect(options.length).toBe(1);
    expect(options[0].textContent).toContain('Águeda');
  });

  it('se elige con el teclado y recuerda el lugar', async () => {
    const { fixture, input, onChange } = await open();
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown' }));
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown' }));
    fixture.detectChanges();
    expect(input.getAttribute('aria-activedescendant')).toContain('opt-1');
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));
    fixture.detectChanges();
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ place_id: 's1' }));
    expect(api.remember).toHaveBeenCalled();
    expect(fixture.nativeElement.textContent).toContain('Barrio Chapinero');
    expect(
      fixture.nativeElement.querySelector('button[aria-label="Quitar Barrio Chapinero"]'),
    ).not.toBeNull();
  });
});
