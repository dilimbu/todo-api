# ==========================================
# Multi-Stage Dockerfile
# ==========================================
# STAGE 1: Builder (Install tools and build venv)
# ==========================================
FROM python:3.13-slim AS builder

# Set working directory (this get's created inside docker image (if not exists)
# and set's as current working dir for all subsequent instructions
# working dir for Stage 1
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
# we copy both: pyproject.toml - contains desired / minimum vesions
# and uv.lock - exact versions of every package and their dependencies
# ./ - copies to current working directory i.e. /app

COPY pyproject.toml uv.lock ./

# Install uv and dependencies
# installs the uv tool inside builder stage
# --frozen - tells uv to use the exact versions from uv.lock
# -no-dev - keeps production image small and secure
# NOTE: Docker will reuse cached layers if nothing changed in previous steps
# or if you use --no-cahe flag

# NOTE: this did not work, instead install uv directly as below
# RUN pip install uv
# RUN uv sync --frozen --no-dev

# Install uv using the official pre-built binaries (much faster than pip install uv)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install dependencies ONLY (This creates a heavily cached layer)
RUN uv sync --frozen --no-dev --no-install-project

# Copy the actual application code
COPY todo/ ./todo/

# Copy main file to current working folder
COPY main2.py ./

# # Build the project into the venv safely without local symlinks
RUN uv sync --frozen --no-dev --no-editable


# ==========================================
# STAGE 2: Final Runner (Small, secure, lean)
# ==========================================
# Production stage
# Note: each stage is independent, has its own filesystem and working directory
# eg. builder stage above and the final stage, this one starts completely fresh
# from python:3.13-slim
# -slim - minial version / much smaller
FROM python:3.13-slim AS runner

# wokring dir for Stage 2: production
WORKDIR /app

# Best practice: Explicitly provide slim runtime libraries just in case
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy completely self-contained virtual environment from builder
# copies only the virtual environment form builder stage into the final production image
# in builder stage, we installed all dependencies using uv sync (which cireate .venv)
# in the final stage, we want a clean, minimal image, which would be much smaller and faster
COPY --from=builder /app/.venv /app/.venv

# Best practice: Copy source files so container pathing matches expectations
COPY --from=builder /app/todo /app/todo
COPY --from=builder /app/main2.py /app/main2.py

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Expose port
# this documents that the container listens on port 8000, does not actually open port to public
# while running container still need to map the port: docker run -p 8000:8000 todo-api
# -p 8000:8000 - maps host port 8000 to container port 8000
EXPOSE 8000

# Health check
# HEALTHCHECK - Docker instruction that tells Docker daemon to check if container is healthy
# Every 30 seconds (default interval / customizable) it calls the endpont specified, if status
# is success, container is marked healthy if ti fails (non 2xx or connection error), container is
# marked unhealthy. Orchestrators (Kubernetes, Docker Swarm etc.) can use this to: restart unhealthy
# containers, remove unhealthy instances from load balancers and show health status
# some params to go in healthcheck cmd --interval=30s --timeout=5s --retries=3
# -fail - makes curl return non-zero exit code (failure) if the HTTP response is not successful
# exit 1 - tells docker the health check failed
# i.e. if healthcheck endpoint returns anything other than 2xx(success) -> curl --fail fails
# Then || exit 1 makes the whole command fail -> Docker makes the container as unhealthy

HEALTHCHECK CMD curl --fail http://localhost:8000/health || exit 1

# Run the application
# this will be executed when conatiner starts, equivalent to running in terminal:
# uvicorn main2:app --host 0.0.0.0 --port 8000 --workers 2
# can be used by Docker Compose / Kubernetes
# can override in docker run command
# eg. docker run todo-api : runs with CMD
# docker run todo-api uvicorn main2:app --workers 4 --reload : override

# Best Practice: Run using 'uv run', which automatically manages the path context
CMD ["uvicorn", "main2:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]

# CMD ["/app/.venv/bin/uvicorn", "main2:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]

# If you are running just the Dockerfile (and not other services or docker-compose):

# Build the image
# docker build -t todo-api .

# Run the container
# docker run -p 8000:8000 todo-api