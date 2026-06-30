# Agent Internet Docker Commands
# Usage: make docker-up / docker-down / docker-build

.PHONY: docker-up docker-down docker-build docker-logs docker-clean

# Build all Docker images
docker-build:
	docker-compose build

# Start all services
docker-up:
	docker-compose up -d

# Stop all services
docker-down:
	docker-compose down

# View logs
docker-logs:
	docker-compose logs -f

# Clean up containers and volumes
docker-clean:
	docker-compose down -v
	docker system prune -f
