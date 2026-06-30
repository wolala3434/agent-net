# Agent Internet - Generic Agent Runner
# This Dockerfile can run any agent by setting AGENT_NAME environment variable
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared package
COPY shared/ ./shared/
RUN pip install --no-cache-dir -e shared/

# Copy SDK
COPY agent-side/sdk/ ./agent-side/sdk/
RUN pip install --no-cache-dir -e agent-side/sdk/

# Copy all agents
COPY agent-side/agents/ ./agents/

# Default environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    AGENT_NAME=echo \
    AGENT_PORT=9123 \
    REGISTRY_URL=http://backend:8000

EXPOSE 9123

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${AGENT_PORT}/health')" || exit 1

# Run the specified agent
CMD python agents/${AGENT_NAME}/run.py --port ${AGENT_PORT} --registry ${REGISTRY_URL}
