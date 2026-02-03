# FIS Situational Awareness System - Docker Image

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install MCP SDK and uvx for MCP server management
RUN pip install --no-cache-dir mcp uvx

# Install Tribe MCP server
# Note: In production, configure with Slack OAuth tokens via environment variables
RUN pip install --no-cache-dir mcp-server-tribe || echo "mcp-server-tribe will be installed via uvx at runtime"

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Expose metrics port
EXPOSE 9090

# Default command (run Temporal worker)
CMD ["python", "main.py"]
