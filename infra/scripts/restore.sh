#!/bin/sh
# Restaura un respaldo de PostgreSQL. Corre dentro del contenedor "backup" (tiene pg_restore y
# las credenciales):
#
#   docker compose ... exec backup sh /restore.sh                      # ultimo respaldo, verificacion
#   docker compose ... exec backup sh /restore.sh carpool-XXXX.dump    # un respaldo concreto
#   docker compose ... exec backup sh /restore.sh carpool-XXXX.dump live      # sobre la base real
#
# Sin base de destino restaura en "carpool_restore_check", compara el numero de filas de las
# tablas principales con la base en uso y borra la copia: asi se prueba un respaldo sin tocar
# nada. Restaurar sobre la base real exige detener antes api y worker.
set -eu

file="${1:-$(ls -1t /backups/carpool-*.dump | head -n 1)}"
case "${file}" in /*) ;; *) file="/backups/${file}" ;; esac
target="${2:-carpool_restore_check}"
[ "${target}" = "live" ] && target="${PGDATABASE}"
[ -f "${file}" ] || { echo "No existe ${file}" >&2; exit 1; }

echo "Restaurando ${file} en ${target}"
if [ "${target}" = "carpool_restore_check" ]; then
  psql -d postgres -qc "DROP DATABASE IF EXISTS carpool_restore_check"
  psql -d postgres -qc "CREATE DATABASE carpool_restore_check"
  pg_restore --dbname=carpool_restore_check --no-owner --exit-on-error "${file}"
  status=0
  for table in users trips bookings ratings tickets messages audit_log; do
    copy=$(psql -d carpool_restore_check -tAc "SELECT count(*) FROM ${table}")
    live=$(psql -tAc "SELECT count(*) FROM ${table}")
    echo "${table}: respaldo=${copy} actual=${live}"
    # El respaldo puede ser de horas atras: tener menos filas es normal, tener mas no.
    [ "${copy}" -le "${live}" ] || status=1
  done
  psql -d postgres -qc "DROP DATABASE carpool_restore_check"
  [ "${status}" -eq 0 ] && echo "Respaldo verificado." || { echo "El respaldo no coincide" >&2; exit 1; }
else
  pg_restore --dbname="${target}" --clean --if-exists --no-owner --exit-on-error "${file}"
  echo "Restaurado en ${target}. Vuelve a levantar api y worker."
fi
