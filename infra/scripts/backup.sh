#!/bin/sh
# Respaldo diario de PostgreSQL. Conserva los ultimos 7 archivos.
set -eu

while true; do
  stamp=$(date -u +%Y%m%dT%H%M%SZ)
  file="/backups/carpool-${stamp}.dump"
  if pg_dump --format=custom --file="${file}.tmp"; then
    mv "${file}.tmp" "${file}"
    echo "backup ok ${file}"
  else
    rm -f "${file}.tmp"
    echo "backup failed" >&2
  fi
  ls -1t /backups/carpool-*.dump 2>/dev/null | tail -n +8 | xargs -r rm -f
  sleep 86400
done
