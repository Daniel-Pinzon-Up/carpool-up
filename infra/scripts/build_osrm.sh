#!/bin/sh
# Prepara los datos de OSRM para Pamplona (paso 5).
#
# 1. Descarga el extracto de Colombia de Geofabrik (unos 330 MB).
# 2. Lo recorta a Pamplona y alrededores con pyosmium (infra/osrm/clip.py).
# 3. Procesa el recorte con el perfil car y el algoritmo MLD
#    (osrm-extract, osrm-partition, osrm-customize).
# 4. Borra el extracto completo; quedan solo los archivos pamplona.osrm*.
#
# Requiere Docker. Uso desde la raiz del repositorio: sh infra/scripts/build_osrm.sh
set -eu

# En Git Bash (Windows) Docker necesita rutas de Windows y sin conversion automatica.
export MSYS_NO_PATHCONV=1
ROOT=$(cd "$(dirname "$0")/../.." && (pwd -W 2>/dev/null || pwd))
DATA="$ROOT/infra/osrm/data"
SOURCE_URL="https://download.geofabrik.de/south-america/colombia-latest.osm.pbf"
OSRM_IMAGE="ghcr.io/project-osrm/osrm-backend:v5.27.1"
# Caja: oeste, sur, este, norte. Cubre el casco urbano y las veredas cercanas.
BBOX="-72.75 7.30 -72.55 7.48"

mkdir -p "$DATA"

if [ ! -s "$DATA/colombia-latest.osm.pbf" ]; then
  echo "Descargando $SOURCE_URL"
  curl -fL --retry 3 -o "$DATA/colombia-latest.osm.pbf.part" "$SOURCE_URL"
  mv "$DATA/colombia-latest.osm.pbf.part" "$DATA/colombia-latest.osm.pbf"
fi

echo "Recortando a Pamplona ($BBOX)"
docker run --rm -v "$DATA:/data" -v "$ROOT/infra/osrm/clip.py:/clip.py:ro" python:3.12-slim \
  sh -c "apt-get update -qq && apt-get install -y -qq --no-install-recommends libexpat1 >/dev/null && \
         pip install --quiet --disable-pip-version-check --root-user-action=ignore 'osmium>=4' && \
         python /clip.py /data/colombia-latest.osm.pbf /data/pamplona.osm.pbf $BBOX"

echo "Procesando con OSRM (perfil car, MLD)"
rm -f "$DATA"/pamplona.osrm*
docker run --rm -v "$DATA:/data" "$OSRM_IMAGE" osrm-extract -p /opt/car.lua /data/pamplona.osm.pbf
docker run --rm -v "$DATA:/data" "$OSRM_IMAGE" osrm-partition /data/pamplona.osrm
docker run --rm -v "$DATA:/data" "$OSRM_IMAGE" osrm-customize /data/pamplona.osrm

rm -f "$DATA/colombia-latest.osm.pbf"
echo "Listo: $DATA/pamplona.osrm"
