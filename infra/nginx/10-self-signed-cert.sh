#!/bin/sh
# Genera un certificado autofirmado si no se monto uno real en /etc/nginx/certs.
set -eu

dir=/etc/nginx/certs
if [ ! -s "$dir/server.crt" ] || [ ! -s "$dir/server.key" ]; then
  mkdir -p "$dir"
  openssl req -x509 -nodes -newkey rsa:2048 -days 825 \
    -subj "/CN=localhost" \
    -addext "subjectAltName=DNS:localhost,IP:127.0.0.1" \
    -keyout "$dir/server.key" -out "$dir/server.crt"
  echo "Certificado autofirmado creado en $dir"
fi
