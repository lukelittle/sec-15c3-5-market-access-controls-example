.PHONY: help build build-lambdas build-spark deploy destroy clean test-local

help:
	@echo "Streaming Risk Controls - Build Commands"
	@echo ""
	@echo "  make build          - Build all Lambda packages and Spark job"
	@echo "  make build-lambdas  - Build Lambda deployment packages"
	@echo "  make build-spark    - Package Spark job"
	@echo "  make deploy         - Deploy to AWS (requires terraform init)"
	@echo "  make destroy        - Destroy AWS infrastructure"
	@echo "  make test-local     - Run local Docker Compose environment"
	@echo "  make clean          - Clean build artifacts"

build: build-lambdas build-spark

build-lambdas:
	@echo "Building Lambda packages..."
	@cd services/order_generator && ./build.sh
	@cd services/killswitch_aggregator && ./build.sh
	@cd services/order_router && ./build.sh
	@cd services/operator_console && ./build.sh
	@echo "✓ Lambda packages built"

build-spark:
	@echo "Packaging Spark job..."
	@cd spark/risk_job && ./package.sh
	@echo "✓ Spark job packaged"

deploy:
	@echo "Deploying to AWS..."
	@cd terraform/envs/dev && terraform apply
	@echo "✓ Infrastructure deployed"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Create Kafka topics: ./tools/create-topics.sh"
	@echo "  2. Deploy Spark job: ./tools/deploy-spark-job.sh"
	@echo "  3. Run demo: see docs/03-run-demo.md"

destroy:
	@echo "Destroying AWS infrastructure..."
	@cd terraform/envs/dev && terraform destroy
	@echo "✓ Infrastructure destroyed"

test-local:
	@echo "Starting local environment..."
	@cd local && docker-compose up -d
	@echo "✓ Local environment running"
	@echo ""
	@echo "Access AKHQ UI: http://localhost:8080"
	@echo "Stop with: cd local && docker-compose down"

clean:
	@echo "Cleaning build artifacts..."
	@rm -rf services/*/dist
	@rm -rf services/*/package
	@rm -rf spark/risk_job/dist
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete
	@echo "✓ Clean complete"
