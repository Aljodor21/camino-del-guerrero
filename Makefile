ENV_FILE = .env.docker

.PHONY: build up down restart logs ps

## Construir imágenes y levantar (primera vez o tras cambios)
build:
	docker compose --env-file $(ENV_FILE) up -d --build

## Levantar sin reconstruir
up:
	docker compose --env-file $(ENV_FILE) up -d

## Apagar contenedores
down:
	docker compose --env-file $(ENV_FILE) down

## Reiniciar
restart:
	docker compose --env-file $(ENV_FILE) restart

## Ver logs en tiempo real
logs:
	docker compose --env-file $(ENV_FILE) logs -f

## Ver estado de los contenedores
ps:
	docker compose --env-file $(ENV_FILE) ps
