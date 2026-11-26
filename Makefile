MLFLOW_ENV_FILE ?= $(or $(wildcard infra/mlflow/.env.local),infra/mlflow/.env.example)
MLOPS_ENV_FILE ?= .env
MLFLOW_PROJECT ?= mlops-mlflow
DOCKER ?= docker

storage = $(DOCKER) compose --env-file "$(MLOPS_ENV_FILE)" -f compose.storage.yaml
compose = $(DOCKER) compose --env-file "$(MLOPS_ENV_FILE)" --env-file "$(MLFLOW_ENV_FILE)" --project-name "$(MLFLOW_PROJECT)" -f compose.mlflow.yaml -f versions.lock.yaml

.PHONY: init storage-up up status logs smoke demo test down

init:
	$(compose) --profile tools config --format json | python3 scripts/bootstrap/mlflow-secrets.py

storage-up:
	@test -z "$$($(DOCKER) ps -q --filter name=^/clearml-local-rustfs-1$$)" || { 		echo "The legacy ClearML RustFS is running. See docs/shared-rustfs.md for cutover." >&2; exit 1; 	}
	$(storage) up -d --wait --wait-timeout 120

up: storage-up
	@test -z "$$($(DOCKER) ps -q --filter label=com.docker.compose.project="$(MLFLOW_PROJECT)" --filter label=com.docker.compose.service=rustfs)" || { 		echo "The legacy MLflow RustFS is running. Copy its objects before changing the tracking endpoint." >&2; exit 1; 	}
	$(compose) up -d --build --wait --wait-timeout 240

status:
	$(storage) ps --all
	$(compose) ps --all

logs:
	$(compose) logs --tail=100

smoke:
	$(compose) run --rm --no-deps client verify --reference /results/demo.json

demo:
	$(compose) run --rm --no-deps client train --reference /results/demo.json
	$(MAKE) smoke

test:
	python3 tests/integration/mlflow-core.py "$(MLOPS_ENV_FILE)" "$(MLFLOW_ENV_FILE)" "$(MLFLOW_PROJECT)" "$(DOCKER)"

down:
	$(compose) down
