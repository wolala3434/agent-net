.PHONY: demo install test clean lint format dev-backend dev-dashboard dev-agents

# Default Python interpreter
PYTHON := python
PYTEST := pytest

# Ports
BACKEND_PORT := 8000
DASHBOARD_PORT := 8501
AGENT_PORT_CREDIT_RISK := 9121
AGENT_PORT_SUPPLY_CHAIN := 9122
AGENT_PORT_ECHO := 9123

REGISTRY_URL := http://localhost:$(BACKEND_PORT)

# ---------------------------------------------------------------------------
# Install
# ---------------------------------------------------------------------------
install:
	$(PYTHON) -m pip install -r requirements.txt
	$(PYTHON) -m pip install -e shared/
	$(PYTHON) -m pip install -e platform/backend/
	$(PYTHON) -m pip install -e agent-side/sdk/

install-dev: install
	$(PYTHON) -m pip install -r requirements-dev.txt
	npm --prefix dashboard install

# ---------------------------------------------------------------------------
# Demo — one-command startup
# ---------------------------------------------------------------------------
demo: install
	@echo "============================================"
	@echo " Agent Internet Demo — starting all services"
	@echo "============================================"
	@echo ""
	@echo " Backend    → http://localhost:$(BACKEND_PORT)"
	@echo " Dashboard  → http://localhost:$(DASHBOARD_PORT)"
	@echo " Agents     → :$(AGENT_PORT_CREDIT_RISK) :$(AGENT_PORT_SUPPLY_CHAIN) :$(AGENT_PORT_ECHO)"
	@echo ""
	bash platform/scripts/start_all.sh $(BACKEND_PORT) $(DASHBOARD_PORT) \
		$(AGENT_PORT_CREDIT_RISK) $(AGENT_PORT_SUPPLY_CHAIN) $(AGENT_PORT_ECHO)

# ---------------------------------------------------------------------------
# Individual service targets
# ---------------------------------------------------------------------------
dev-backend:
	cd platform/backend && $(PYTHON) -m uvicorn src.platform.main:app \
		--host 0.0.0.0 --port $(BACKEND_PORT) --reload

dev-dashboard:
	npm --prefix dashboard run dev -- --host 0.0.0.0 --port $(DASHBOARD_PORT)

dev-agent-credit-risk:
	cd agent-side/agents/credit-risk-analyst && $(PYTHON) run.py \
		--port $(AGENT_PORT_CREDIT_RISK) --registry $(REGISTRY_URL)

dev-agent-supply-chain:
	cd agent-side/agents/supply-chain-expert && $(PYTHON) run.py \
		--port $(AGENT_PORT_SUPPLY_CHAIN) --registry $(REGISTRY_URL)

dev-agent-echo:
	cd agent-side/agents/echo && $(PYTHON) run.py \
		--port $(AGENT_PORT_ECHO) --registry $(REGISTRY_URL)

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
db-init:
	$(PYTHON) -c "import os, sqlite3; os.makedirs('data', exist_ok=True); conn = sqlite3.connect('data/registry.db'); \
		conn.executescript(open('platform/database/schema.sql').read()); \
		conn.executescript(open('platform/database/migrations/001_fix_domains_index.sql').read()); \
		conn.commit(); conn.close()"
	@echo "Database initialized at data/registry.db"

db-reset:
	$(PYTHON) -c "import os; os.remove('data/registry.db') if os.path.exists('data/registry.db') else None"
	$(MAKE) db-init

# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------
seed: db-init
	$(PYTHON) platform/scripts/seed_demo_agents.py --registry $(REGISTRY_URL)

# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------
test:
	$(PYTEST) platform/backend/tests/ agent-side/sdk/src/agent_internet/tests/ -v

test-dashboard:
	npm --prefix dashboard run build

test-e2e:
	$(PYTHON) platform/scripts/test_e2e.py

# ---------------------------------------------------------------------------
# Quality
# ---------------------------------------------------------------------------
lint:
	$(PYTHON) -m ruff check platform/ agent-side/

format:
	$(PYTHON) -m ruff format platform/ agent-side/

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------
clean:
	$(PYTHON) -c "import os, shutil; \
		[os.remove(f) for f in ['data/registry.db'] if os.path.exists(f)]; \
		[shutil.rmtree(d) for d in ['.pytest_cache'] if os.path.isdir(d)]; \
		for r, dirs, _ in os.walk('.'): \
			[shutil.rmtree(os.path.join(r, d)) for d in dirs if d == '__pycache__']"
	for d in *.egg-info; do [ -d "$$d" ] && rm -rf "$$d"; done 2>/dev/null; true

clean-all: clean
	rm -rf .venv/
	rm -rf dist/

# ---------------------------------------------------------------------------
# Docker
# ---------------------------------------------------------------------------
docker-build:
	docker-compose build

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

docker-clean:
	docker-compose down -v
	docker system prune -f
