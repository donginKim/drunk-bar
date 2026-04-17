FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files first (layer cache)
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-dev

# Copy application
COPY app/ app/
COPY agent/ agent/
COPY static/ static/
COPY skill/ skill/
COPY personas/ personas/
COPY main.py .

# Create directories
RUN mkdir -p history static/photos

# Expose port
EXPOSE 8888

# Run — single worker for WebSocket + in-memory state consistency
CMD ["uv", "run", "uvicorn", "app.server:app", \
     "--host", "0.0.0.0", \
     "--port", "8888", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "*"]
