# Agent Internet Platform Backend
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for building Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy root requirements first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy shared package (protocol models) and install
COPY shared/ ./shared/
RUN pip install --no-cache-dir -e shared/

# Copy SDK package (agents depend on it) and install
COPY agent-side/sdk/ ./agent-side/sdk/
RUN pip install --no-cache-dir -e agent-side/sdk/

# Copy backend package and install
COPY platform/backend/ ./platform/backend/
RUN pip install --no-cache-dir -e platform/backend/

# Copy database schema files (needed at runtime)
COPY platform/database/ ./platform/database/

# Create data directory for SQLite
RUN mkdir -p /app/data

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    REGISTRY_HOST=0.0.0.0 \
    REGISTRY_PORT=8000 \
    REGISTRY_DATABASE_URL=sqlite+aiosqlite:////app/data/registry.db

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Run from platform/backend/ directory so src.platform.main resolves
WORKDIR /app/platform/backend
CMD ["python", "-m", "uvicorn", "src.platform.main:app", "--host", "0.0.0.0", "--port", "8000"]
