# Build stage
FROM python:3.11-slim-bookworm AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies into a virtual environment
# --frozen ensures we use the lockfile exactly
# --no-dev excludes development dependencies
ENV UV_COMPILE_BYTECODE=1
RUN uv sync --frozen --no-dev

# Copy the rest of the application
COPY . .

# Final stage
FROM gcr.io/distroless/python3-debian12

WORKDIR /app

# Copy the virtual environment from the builder
# We only need the site-packages if we use the system python
COPY --from=builder /app/.venv/lib/python3.11/site-packages /app/site-packages
COPY --from=builder /app /app

# Set PYTHONPATH to use the installed packages
ENV PYTHONPATH=/app/site-packages

# Run the application
# We use the python interpreter provided by the distroless image
CMD ["app.py"]
