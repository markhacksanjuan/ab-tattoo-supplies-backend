FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Cloud Run uses PORT env var (default 8000)
ENV PORT=8000
EXPOSE ${PORT}

# Health check (used locally / docker-compose; Cloud Run uses its own probes)
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:${PORT}/api/health || exit 1

# Run the application - Cloud Run sets PORT env var automatically
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT} --workers 2
