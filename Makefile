# Comandos del proyecto. En Windows sin make: .\make.ps1 <objetivo>
# OSRM arranca solo cuando ya existen sus datos (make osrm).
OSRM_PROFILE = $(if $(wildcard infra/osrm/data/pamplona.osrm.mldgr),--profile osrm,)
DC = docker compose --env-file .env -f infra/docker-compose.yml -f infra/docker-compose.dev.yml $(OSRM_PROFILE)
DC_TEST_DB = sh -c 'export DATABASE_URL=$${DATABASE_URL%/*}/carpool_test && alembic upgrade head && pytest --cov=app --cov-report=term-missing'

.PHONY: help env up down restart logs ps migrate seed token email-test e2e-users test test-backend test-frontend test-e2e lint build osrm tiles backup-check restore clean

help:
	@echo "env            crea .env desde .env.example si no existe"
	@echo "up             levanta todos los servicios (desarrollo)"
	@echo "down           detiene los servicios"
	@echo "logs           sigue los logs"
	@echo "migrate        aplica migraciones de Alembic"
	@echo "seed           carga datos semilla"
	@echo "token          token de desarrollo: make token EMAIL=correo"
	@echo "email-test     correo de prueba con la config SMTP: make email-test TO=correo"
	@echo "e2e-users      cuentas de las pruebas E2E (solo desarrollo)"
	@echo "test-e2e       pruebas E2E y de accesibilidad contra la app levantada"
	@echo "backup-check   restaura el ultimo respaldo en una base aparte y lo compara"
	@echo "restore        restaura un respaldo sobre la base: make restore FILE=carpool-XXXX.dump"
	@echo "test           pruebas de backend (con PostGIS real) y frontend"
	@echo "lint           ruff, mypy, eslint y prettier"
	@echo "osrm           descarga y procesa el mapa de Pamplona para OSRM"
	@echo "tiles          descarga las teselas del mapa base de Pamplona"

env:
	@test -f .env || cp .env.example .env

up: env
	$(DC) up -d --build
	@echo "Web: https://localhost  API: http://localhost:8000/api/v1/docs  Correo: http://localhost:8025"

down:
	$(DC) down

restart: down up

logs:
	$(DC) logs -f --tail=100

ps:
	$(DC) ps

migrate:
	$(DC) exec -T api alembic upgrade head

seed:
	$(DC) exec -T api python -m app.seed

token:
	@$(DC) exec api python -m app.cli token $(EMAIL)

email-test:
	@$(DC) exec -T worker python -m app.cli email-test $(TO)

e2e-users:
	@mkdir -p frontend/e2e/.auth
	@$(DC) exec -T api python -m app.cli e2e-users > frontend/e2e/.auth/credentials.json
	@echo "Cuentas E2E listas (credenciales en frontend/e2e/.auth, ignorado por git)"

test-e2e:
	cd frontend && npx playwright test

backup-check:
	$(DC) exec -T backup sh /restore.sh

restore:
	$(DC) stop api worker
	$(DC) exec -T backup sh /restore.sh $(FILE) live
	$(DC) start api worker

test: test-backend test-frontend

test-backend: env
	$(DC) up -d db redis
	$(DC) run --rm --no-deps api $(DC_TEST_DB)

test-frontend:
	cd frontend && npm ci && npx ng test --watch=false

lint:
	$(DC) run --rm --no-deps api sh -c 'ruff check . && ruff format --check . && mypy app'
	cd frontend && npx ng lint && npx prettier --check "src/**/*.{ts,html,css}"

build:
	$(DC) build

osrm:
	sh infra/scripts/build_osrm.sh

tiles:
	sh infra/scripts/build_tiles.sh

clean:
	$(DC) down -v
