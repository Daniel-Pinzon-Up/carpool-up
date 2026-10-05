#!/bin/sh
# Descarga las teselas del mapa base de Pamplona (paso 5).
#
# Extrae del ultimo build diario de Protomaps solo la caja de Pamplona, pidiendo
# rangos de bytes: no se descarga el planeta completo. El resultado (cerca de 1 MB)
# queda en infra/tiles/pamplona.pmtiles y Nginx lo sirve en /tiles/.
#
# Requiere Docker y curl. Uso desde la raiz del repositorio: sh infra/scripts/build_tiles.sh
set -eu

export MSYS_NO_PATHCONV=1
ROOT=$(cd "$(dirname "$0")/../.." && (pwd -W 2>/dev/null || pwd))
# Misma caja que OSRM: oeste, sur, este, norte.
BBOX="-72.75,7.30,-72.55,7.48"

BUILD=$(curl -fsS --max-time 30 https://build-metadata.protomaps.dev/builds.json \
  | grep -o '"key": *"[0-9]*\.pmtiles"' | tail -1 | grep -o '[0-9]*\.pmtiles')
echo "Build de Protomaps: $BUILD"

mkdir -p "$ROOT/infra/tiles"
docker run --rm -v "$ROOT/infra/tiles:/data" protomaps/go-pmtiles \
  extract "https://build.protomaps.com/$BUILD" /data/pamplona.pmtiles --bbox="$BBOX" --maxzoom=15

echo "Listo: $ROOT/infra/tiles/pamplona.pmtiles"
