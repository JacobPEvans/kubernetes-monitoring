.PHONY: help validate generate-overlay deploy deploy-doppler status logs build-images run-claude run-gemini clean

CONTEXT ?= orbstack
NAMESPACE := monitoring

help: ## Show all targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

validate: ## Validate kustomize base builds cleanly
	kubectl kustomize k8s/base/

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
	kubectl --context $(CONTEXT) apply -f k8s/base/ai-jobs/claude-code-job.yaml

run-gemini: ## Create a Gemini CLI ephemeral job
	kubectl --context $(CONTEXT) apply -f k8s/base/ai-jobs/gemini-cli-job.yaml

clean: ## Delete monitoring namespace (destructive!)
	kubectl --context $(CONTEXT) delete namespace $(NAMESPACE) --ignore-not-found
