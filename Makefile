MLFLOW_ENV_FILE ?= $(or $(wildcard infra/mlflow/.env.local),infra/mlflow/.env.example)
MLFLOW_PROJECT ?= mlops-mlflow
DOCKER ?= docker

compose = $(DOCKER) compose --env-file "$(MLFLOW_ENV_FILE)" --project-name "$(MLFLOW_PROJECT)" -f compose.mlflow.yaml -f versions.lock.yaml

.PHONY: init up status logs smoke demo test down

init:
	$(compose) --profile tools config --format json | python3 scripts/bootstrap/mlflow-secrets.py

up:
	$(compose) up -d --build --wait --wait-timeout 240
	$(compose) run --rm --no-deps git-init

status:
	$(compose) ps --all

logs:
	$(compose) logs --tail=100

smoke:
	$(compose) run --rm --no-deps client verify --reference /results/demo.json

demo:
	$(compose) run --rm --no-deps client train --reference /results/demo.json
	$(MAKE) smoke

test:
	python3 tests/integration/mlflow-core.py "$(MLFLOW_ENV_FILE)" "$(MLFLOW_PROJECT)" "$(DOCKER)"

down:
	$(compose) down
