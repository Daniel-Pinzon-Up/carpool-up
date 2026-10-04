# Contexto de build: raiz del repositorio (necesita infra/nginx).
FROM node:24-alpine AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN npx ng build --configuration production

FROM nginx:stable-alpine
RUN apk add --no-cache openssl
COPY infra/nginx/default.conf /etc/nginx/conf.d/default.conf
COPY --chmod=755 infra/nginx/10-self-signed-cert.sh /docker-entrypoint.d/10-self-signed-cert.sh
COPY --from=build /app/dist/carpool-web/browser /usr/share/nginx/html
EXPOSE 80 443
