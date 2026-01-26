.PHONY: help cluster conjur authn-k8s demo audit destroy
.DEFAULT_GOAL := help
CLUSTER := pam-lab08

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

cluster: ## Create a local kind cluster
	kind create cluster --name $(CLUSTER) --config k8s/kind-config.yaml
	kubectl create namespace conjur --dry-run=client -o yaml | kubectl apply -f -
	kubectl create namespace app --dry-run=client -o yaml | kubectl apply -f -

conjur: ## Install Conjur OSS via Helm
	helm repo add cyberark https://cyberark.github.io/helm-charts
	helm repo update
	helm install conjur-oss cyberark/conjur-oss \
		--namespace conjur \
		--set dataKey="$$(docker run --rm cyberark/conjur data-key generate)" \
		--set account.name=lab --set account.create=true
	@echo "Wait for the conjur pods to be Ready, then run 'make authn-k8s'."

authn-k8s: ## Configure the Kubernetes authenticator + load policy
	./scripts/setup-authn-k8s.sh

demo: ## Deploy a workload that pulls a secret at runtime
	kubectl apply -f k8s/demo-workload.yaml
	@echo "kubectl logs -n app deploy/secret-consumer  # should show the brokered secret was retrieved"

audit: ## Run KubiScan against the cluster
	./scripts/run-kubiscan.sh

destroy: ## Delete the cluster
	kind delete cluster --name $(CLUSTER)
