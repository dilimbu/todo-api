# ==========================================
# Multi-Stage Dockerfile
# ==========================================
# STAGE 1: Builder (Install tools and build venv)
# ==========================================
FROM python:3.13-slim AS builder

# Set working directory (this get's created inside docker image (if not exists)
# and set's as current working dir for all subsequent instructions
WORKDIR /app

# Install system dependencies:
# apt-get - package manager to install update software packages
# installs:
# gcc - C compiler (needed for packages like uv)
# libpq-dev - PostgreSQL client development files
# -y - automatically answer "yes" to prompts
#  --no-install-recommends - installs only required packages
# rm -rf /var/lib/apt/lists/* - cleans up package cache to reduce image size
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files:
# pyproject.toml - contains desired / minimum vesions
# uv.lock - exact versions of every package and their dependencies
# ./ - copies to current working directory i.e. /app
COPY pyproject.toml uv.lock ./

# Install uv and dependencies:
# NOTE: Docker will reuse cached layers if nothing changed in previous steps
# Install uv using the official pre-built binaries (faster/more reliable than pip install uv)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install dependencies only (cached unless lock changes)
# --frozen - tells uv to use the exact versions from uv.lock
# -no-dev - keeps production image small and secure
RUN uv sync --frozen --no-dev --no-install-project

# Copy the actual application code
COPY todo/ ./todo/
COPY workers/ ./workers/

# Copy main file to current working folder
COPY main.py ./

# Build the project into the venv safely without local symlinks
RUN uv sync --frozen --no-dev --no-editable


# ==========================================
# STAGE 2: Runner (lean prod image)
# ==========================================
# Production stage
# Each stage is independent, has its own filesystem and working directory
# -slim - minial version / much smaller
FROM python:3.13-slim AS runner

# wokring dir for Stage 2
WORKDIR /app

# Runtime Postgres client lib only (no gcc)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# copy virtual environment form builder stage into the final production image
COPY --from=builder /app/.venv /app/.venv

# Copy source files
COPY --from=builder /app/todo /app/todo
COPY --from=builder /app/main.py /app/main.py
COPY --from=builder /app/workers /app/workers

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Expose port
# this documents that the container listens on port 8000, does not actually open port to public
EXPOSE 8000

# HEALTHCHECK - Docker instruction that tells Docker daemon to check if container is healthy
# Every 30 seconds (default interval / customizable) it calls the endpont specified, if status
# is success, container is marked healthy if ti fails (non 2xx or connection error), container is
# marked unhealthy. Orchestrators (Kubernetes, Docker Swarm etc.) can use this to: restart unhealthy
# containers, remove unhealthy instances from load balancers and show health status
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')" || exit 1

# Run the application:
# this will be executed when conatiner starts, equivalent to running in terminal:
# uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2
# can be used by Docker Compose / Kubernetes
# can override in docker run command
# eg. docker run todo-api : runs with CMD
# docker run todo-api uvicorn main:app --workers 4 --reload : override
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]

# If you are running just the Dockerfile (and not other services or docker-compose):

# Build the image
# docker build -t todo-api .

# Run the container
# docker run -p 8000:8000 todo-api