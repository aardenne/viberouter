# ═══════════════════════════════════════════════════
# VibeRouter Docker Image
# ═══════════════════════════════════════════════════
# Build: docker build -t viberouter:latest .
# Run:   docker run -p 8080:8080 -p 9090:9090 -v $(pwd)/config.yaml:/app/config.yaml viberouter:latest
# ═══════════════════════════════════════════════════

FROM python:3.12-slim AS builder

WORKDIR /build
COPY pyproject.toml .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --no-deps .

FROM python:3.12-slim

# Install runtime deps
RUN pip install --no-cache-dir uvicorn httpx

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages

WORKDIR /app

# Copy source
COPY src/viberouter/ ./viberouter/
COPY config.yaml.example ./config.yaml.example

EXPOSE 8080
EXPOSE 9090

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

# Start the API server
CMD ["uvicorn", "viberouter.api:app", "--host", "0.0.0.0", "--port", "8080"]
