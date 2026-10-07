#!/bin/sh
# Respaldo diario de PostgreSQL. Conserva los ultimos 7 archivos.
#
# Si la base no responde (por ejemplo, justo al reiniciar Docker) no se espera un dia entero:
# se reintenta cada 5 minutos hasta lograr el respaldo del dia.
set -u

RETRY_SECONDS=300
DAY_SECONDS=86400
KEEP=7

backup() {
  stamp=$(date -u +%Y%m%dT%H%M%SZ)
  file="/backups/carpool-${stamp}.dump"
  if ! pg_isready --timeout=30 >/dev/null 2>&1; then
    echo "backup: la base no responde todavia" >&2
    return 1
  fi
  if pg_dump --format=custom --file="${file}.tmp"; then
    mv "${file}.tmp" "${file}"
    echo "backup ok ${file} ($(du -h "${file}" | cut -f1))"
    ls -1t /backups/carpool-*.dump 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm -f
    return 0
  fi
  rm -f "${file}.tmp"
  echo "backup failed" >&2
  return 1
}

while true; do
  if backup; then
    sleep "${DAY_SECONDS}"
  else
    echo "backup: nuevo intento en ${RETRY_SECONDS} s" >&2
    sleep "${RETRY_SECONDS}"
  fi
done
