COMPOSE=docker compose -f infra/compose/compose.yml

.PHONY: up down build logs ps test health clean

up:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

build:
	$(COMPOSE) build

logs:
	$(COMPOSE) logs -f --tail=200

ps:
	$(COMPOSE) ps

test:
	python -m compileall apps/portal-bff services

health:
	bash scripts/deployment/health-check.sh

clean:
	$(COMPOSE) down -v --remove-orphans
