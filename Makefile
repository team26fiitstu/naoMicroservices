# ==========================================
# Makefile for Multi-Service Project
# ==========================================

-include .env
REGISTRY ?= jperdek
TAG ?= latest
SERVICES = web nao-robot-api skeleton-finder-api translator voice-command-api exercise-config-service audio-to-text-converter

# ------------------------------------------
#          HELP (auto-generated)
# ------------------------------------------
.PHONY: help
help:  ## Show this help message
	@echo ""
	@echo "📌 Available commands:"
	@echo ""
	@awk 'BEGIN {FS = ":.*##"; printf ""} /^[a-zA-Z0-9_.-]+:.*##/ { printf "  \033[36m%-25s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)
	@echo ""

# ------------------------------------------
#          IMAGE MANAGEMENT
# ------------------------------------------
build-all: ## Build all Docker images
	@echo "Building all Docker images..."
	docker compose -f docker-compose.build.yml build

build-%: ## Build a single service (usage: make build-web)
	@echo "Building $*..."
	docker compose -f docker-compose.build.yml build $*

rebuild-all: ## Rebuild all images from scratch (no cache) and restart
	@echo "Rebuilding all Docker images (no cache)..."
	docker compose -f docker-compose.build.yml build --no-cache
	docker compose -f docker-compose.dev.yml up -d

rebuild-%: ## Rebuild a single service from scratch (usage: make rebuild-web)
	@echo "Rebuilding $* (no cache)..."
	docker compose -f docker-compose.build.yml build --no-cache $*
	docker compose -f docker-compose.dev.yml up -d $*

push-all: ## Push all images to registry (run build-all first if needed)
	@echo "Pushing images to registry..."
	@for service in $(SERVICES); do \
		image=$(REGISTRY)/$$service:$(TAG); \
		echo "Pushing $$image"; \
		docker push $$image || echo "Failed to push $$image"; \
	done

check-images: ## Check if all local images exist
	@echo "Checking local images..."
	@for service in $(SERVICES); do \
		image=$(REGISTRY)/$$service:$(TAG); \
		if docker image inspect $$image >/dev/null 2>&1; then \
			echo "✓ $$image"; \
		else \
			echo "✗ $$image - not found"; \
		fi \
	done

# ------------------------------------------
#     DEVELOPMENT (Docker Compose)
# ------------------------------------------
dev-start: ## Start dev environment from existing images (no build)
	docker compose -f docker-compose.dev.yml up -d
	@echo ""
	@echo "🌐 Services:"
	@echo "  - web:                http://localhost:8090"
	@echo "  - nao-robot-api:      http://localhost:5000"
	@echo "  - skeleton-finder-api: http://localhost:6001"
	@echo "  - translator:         http://localhost:7000"
	@echo "  - voice-command-api:  http://localhost:8000"
	@echo "  - exercise-config:    http://localhost:7001"
	@echo "  - audio-to-text:      http://localhost:9901"

dev-start-%: ## Start a single service from existing image (usage: make dev-start-web)
	docker compose -f docker-compose.dev.yml up -d $*

dev-up: build-all ## Start development environment (build + run)
	@echo "Starting development environment..."
	docker compose -f docker-compose.dev.yml up -d
	@echo ""
	@echo "🌐 Services:"
	@echo "  - web:                http://localhost:8090"
	@echo "  - nao-robot-api:      http://localhost:5000"
	@echo "  - skeleton-finder-api: http://localhost:6001"
	@echo "  - translator:         http://localhost:7000"
	@echo "  - voice-command-api:  http://localhost:8000"
	@echo "  - exercise-config:    http://localhost:7001"
	@echo "  - audio-to-text:      http://localhost:9901"

dev-up-%: build-% ## Start only one dev service (usage: make dev-up-web)
	@echo "Starting development environment for $*..."
	docker compose -f docker-compose.dev.yml up -d $*
	@echo ""
	@echo "Service $* started"

dev-logs-%: ## Show logs for one service (usage: make dev-logs-web)
	docker compose -f docker-compose.dev.yml logs -f $*

dev-down: ## Stop development environment
	@echo "Stopping development environment..."
	docker compose -f docker-compose.dev.yml down

dev-logs: ## Show dev logs (real-time)
	docker compose -f docker-compose.dev.yml logs -f

dev-restart: dev-down dev-up ## Restart dev environment

# ------------------------------------------
#                 TESTING
# ------------------------------------------
test: ## Test all services locally
	@echo "Testing services..."
	@curl -sSf http://localhost:8090/ >/dev/null && echo "✓ web (8080)" || echo "✗ web"
	@curl -sSf http://localhost:3000/ >/dev/null && echo "✓ team19-web (3000)" || echo "✗ team19-web"
	@curl -sSf http://localhost:5000/ >/dev/null && echo "✓ nao-robot-api (5000)" || echo "✗ nao-robot-api"
	@curl -sSf http://localhost:6001/ >/dev/null && echo "✓ skeleton-finder-api (6001)" || echo "✗ skeleton-finder-api"
	@curl -sSf http://localhost:7000/test >/dev/null && echo "✓ translator (7000)" || echo "✗ translator"
	@curl -sSf http://localhost:8000/ >/dev/null && echo "✓ voice-command-api (8000)" || echo "✗ voice-command-api"
	@curl -sSf http://localhost:7001/health >/dev/null && echo "✓ exercise-config-service (7001)" || echo "✗ exercise-config-service"

# ------------------------------------------
#                 CLEANUP
# ------------------------------------------
clean: ## Remove all containers + volumes + images
	@echo "Cleaning up..."
	docker compose -f docker-compose.dev.yml down -v
	@for service in $(SERVICES); do \
		image=$(REGISTRY)/$$service:$(TAG); \
		echo "Removing image $$image"; \
		docker rmi $$image 2>/dev/null || true; \
	done
	@echo "Cleanup complete!"

status: ## Show running Docker Compose services
	@echo "=== Running Containers ==="
	@docker compose -f docker-compose.dev.yml ps

# ------------------------------------------
#               KUBERNETES
# ------------------------------------------
k8s-apply: ## Apply k8s manifests without pushing (use local images)
	@echo "Applying k8s manifests..."
	kubectl apply -R -f k8s/
	@kubectl wait --for=condition=available deployment/web-deployment --timeout=120s 2>/dev/null || true
	@kubectl wait --for=condition=available deployment/team19-web-deployment --timeout=120s 2>/dev/null || true
	@kubectl wait --for=condition=available deployment/naorobotapi-deployment --timeout=120s 2>/dev/null || true
	@kubectl wait --for=condition=available deployment/skeletonfinderapi-deployment --timeout=120s 2>/dev/null || true
	@kubectl wait --for=condition=available deployment/translatorapi-deployment --timeout=120s 2>/dev/null || true
	@kubectl wait --for=condition=available deployment/voicecommandapi-deployment --timeout=120s 2>/dev/null || true
	@kubectl wait --for=condition=available deployment/exercise-config-service-deployment --timeout=120s 2>/dev/null || true
	@echo "k8s apply done"

k8s-deploy: push-all ## Push images and deploy all services to Kubernetes
	@echo "Deploying to Kubernetes..."
	kubectl apply -R -f k8s/
	@kubectl wait --for=condition=available deployment/web-deployment --timeout=120s 2>/dev/null || true
	@kubectl wait --for=condition=available deployment/team19-web-deployment --timeout=120s 2>/dev/null || true
	@kubectl wait --for=condition=available deployment/naorobotapi-deployment --timeout=120s 2>/dev/null || true
	@kubectl wait --for=condition=available deployment/skeletonfinderapi-deployment --timeout=120s 2>/dev/null || true
	@kubectl wait --for=condition=available deployment/translatorapi-deployment --timeout=120s 2>/dev/null || true
	@kubectl wait --for=condition=available deployment/voicecommandapi-deployment --timeout=120s 2>/dev/null || true
	@kubectl wait --for=condition=available deployment/exercise-config-service-deployment --timeout=120s 2>/dev/null || true
	@echo "k8s deploy done"

k8s-delete: ## Delete all Kubernetes resources
	@echo "Removing from Kubernetes..."
	kubectl delete -R -f k8s/ --ignore-not-found=true

k8s-logs: ## Print logs from all Kubernetes pods
	@kubectl logs -l app=web --tail=100 || true
	@kubectl logs -l app=team19-web --tail=100 || true
	@kubectl logs -l app=naorobotapi --tail=100 || true
	@kubectl logs -l app=skeletonfinderapi --tail=100 || true
	@kubectl logs -l app=translator --tail=100 || true
	@kubectl logs -l app=voicecommandapi --tail=100 || true
	@kubectl logs -l app=exercise-config-service --tail=100 || true

k8s-status: ## Show status of all Kubernetes pods/services
	@kubectl get nodes || true
	@kubectl get deployments,services,pods -o wide || true

k8s-get-urls: ## Show all Kubernetes service URLs
	@kubectl get svc -o wide || true

k8s-restart: ## Restart all Kubernetes deployments
	@kubectl rollout restart deployment web-deployment || true
	@kubectl rollout restart deployment team19-web-deployment || true
	@kubectl rollout restart deployment naorobotapi-deployment || true
	@kubectl rollout restart deployment skeletonfinderapi-deployment || true
	@kubectl rollout restart deployment voicecommandapi-deployment || true
	@kubectl rollout restart deployment exercise-config-service-deployment || true
