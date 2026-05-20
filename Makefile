.PHONY: help up down logs build migrate seed shell test clean

help: ## Affiche cette aide
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

up: ## Démarre tous les services (db, redis, api)
	docker compose up -d

down: ## Arrête tous les services
	docker compose down

logs: ## Affiche les logs de l'API
	docker compose logs -f api

build: ## Rebuild l'image API
	docker compose build api

migrate: ## Applique les migrations Alembic
	docker compose exec api alembic upgrade head

seed: ## Insère les données de démonstration
	docker compose exec api python -m app.scripts.seed

shell: ## Ouvre un shell dans le conteneur API
	docker compose exec api bash

test: ## Lance les tests
	docker compose exec api pytest -v

clean: ## Stoppe et supprime volumes (DESTRUCTIF)
	docker compose down -v

restart: down up ## Redémarre tout
