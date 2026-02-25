.PHONY: help validate validate-schemas generate-overlay deploy deploy-doppler status logs build-images run-claude run-gemini test test-e2e test-smoke test-pipeline test-forwarding test-setup full-power power-save power-status clean

CONTEXT ?= orbstack
NAMESPACE := monitoring

help: ## Show all targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

validate: ## Validate kustomize builds and schemas
	bash -c 'set -o pipefail; kubectl kustomize k8s/base/ | kubeconform -strict -summary -output text'

validate-schemas: ## Validate rendered manifests against K8s schemas
	bash -c 'set -o pipefail; kubectl kustomize k8s/base/ | kubeconform -strict -summary -output text'

generate-overlay: ## Generate local overlay with real volume paths
	./scripts/generate-overlay.sh

deploy: ## Full deploy: generate overlay + create secrets + apply
	./scripts/deploy.sh

deploy-doppler: ## Deploy with Cribl secrets from Doppler (project/config in SOPS)
	sops exec-env secrets.enc.yaml './scripts/deploy-doppler.sh'

status: ## Show monitoring namespace status
	kubectl --context $(CONTEXT) get all -n $(NAMESPACE)

logs: ## Tail all pod logs in monitoring namespace
	kubectl --context $(CONTEXT) -n $(NAMESPACE) logs -l app.kubernetes.io/part-of=claude-monitoring --all-containers --tail=50 -f

build-images: ## Build Claude Code and Gemini CLI Docker images
	docker build -t kubernetes-monitoring/claude-code:latest docker/claude-code/
	docker build -t kubernetes-monitoring/gemini-cli:latest docker/gemini-cli/

run-claude: ## Create a Claude Code ephemeral job
	sed "s|PLACEHOLDER_HOME_DIR|$$HOME|g" k8s/base/ai-jobs/claude-code-job.yaml | kubectl --context $(CONTEXT) apply -f -

run-gemini: ## Create a Gemini CLI ephemeral job
	sed "s|PLACEHOLDER_HOME_DIR|$$HOME|g" k8s/base/ai-jobs/gemini-cli-job.yaml | kubectl --context $(CONTEXT) apply -f -

test: ## Run all pipeline tests (requires deployed stack)
	@test -x .venv/bin/pytest || { echo "Run 'make test-setup' first to install test dependencies"; exit 1; }
	.venv/bin/pytest tests/ -v

test-smoke: ## Run smoke tests only (pod health + services)
	@test -x .venv/bin/pytest || { echo "Run 'make test-setup' first to install test dependencies"; exit 1; }
	.venv/bin/pytest tests/test_smoke.py -v

test-pipeline: ## Run OTLP pipeline tests (sends test traces)
	@test -x .venv/bin/pytest || { echo "Run 'make test-setup' first to install test dependencies"; exit 1; }
	.venv/bin/pytest tests/test_pipeline.py -v

test-forwarding: ## Run forwarding tests (Cribl pipeline)
	@test -x .venv/bin/pytest || { echo "Run 'make test-setup' first to install test dependencies"; exit 1; }
	.venv/bin/pytest tests/test_forwarding.py -v

test-e2e: ## Run full test suite in order (smoke → pipeline → forwarding)
	@test -x .venv/bin/pytest || { echo "Run 'make test-setup' first to install test dependencies"; exit 1; }
	.venv/bin/pytest tests/test_smoke.py tests/test_pipeline.py tests/test_forwarding.py -v --tb=short

test-setup: ## Install test dependencies in virtual environment
	python3 -m venv .venv
	.venv/bin/pip install -r tests/requirements.txt

power-save: ## Scale all monitoring pods to 0 replicas (battery saver)
	@echo "Scaling down monitoring stack..."
	kubectl --context $(CONTEXT) -n $(NAMESPACE) scale statefulset --all --replicas=0
	@echo "All monitoring pods scaled to 0. Run 'make full-power' to restore."

full-power: ## Scale all monitoring pods to 1 replica (full power)
	@echo "Scaling up monitoring stack..."
	kubectl --context $(CONTEXT) -n $(NAMESPACE) scale statefulset --all --replicas=1
	@echo "Waiting for rollouts..."
	@for sts in otel-collector cribl-edge-managed cribl-edge-standalone cribl-stream-standalone; do \
		kubectl --context $(CONTEXT) -n $(NAMESPACE) rollout status statefulset/$$sts --timeout=120s; \
	done
	@echo "All monitoring pods restored."

power-status: ## Show monitoring pod replica counts and macOS power source
	@kubectl --context $(CONTEXT) -n $(NAMESPACE) get statefulsets --no-headers 2>/dev/null | awk '{printf "  %-35s %s\n", $$1, $$2}'
	@echo ""
	@pmset -g batt 2>/dev/null | head -1 || true

clean: ## Delete monitoring namespace (destructive!)
	kubectl --context $(CONTEXT) delete namespace $(NAMESPACE) --ignore-not-found
