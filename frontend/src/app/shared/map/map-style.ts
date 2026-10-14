import type { StyleSpecification } from 'maplibre-gl';

/** Centro aproximado de Pamplona (Norte de Santander). */
export const PAMPLONA_CENTER: [number, number] = [-72.6475, 7.3756];
/** Limite del mapa: igual que el area de las teselas descargadas. */
export const MAP_BOUNDS: [[number, number], [number, number]] = [
  [-72.75, 7.3],
  [-72.55, 7.48],
];

export const ROUTE_COLORS = { route: '#1E5AA8', casing: '#FFFFFF' };

/**
 * Estilo del mapa base de Protomaps con todo servido por la propia app:
 * teselas PMTiles, fuentes y sprites (la CSP no permite recursos externos).
 */
export async function buildMapStyle(): Promise<StyleSpecification> {
  const { layers, namedFlavor } = await import('@protomaps/basemaps');
  const flavor = 'light';
  const origin = globalThis.location?.origin ?? '';
  return {
    version: 8,
    glyphs: `${origin}/map/fonts/{fontstack}/{range}.pbf`,
    sprite: `${origin}/map/sprites/${flavor}`,
    sources: {
      protomaps: {
        type: 'vector',
        url: `pmtiles://${origin}/tiles/pamplona.pmtiles`,
        attribution:
          '<a href="https://openstreetmap.org/copyright" target="_blank" rel="noopener">&copy; OpenStreetMap</a>',
      },
    },
    layers: layers('protomaps', namedFlavor(flavor), { lang: 'es' }),
  } as StyleSpecification;
}
