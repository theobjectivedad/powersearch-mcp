# syntax=docker/dockerfile:1.7
# Multi-stage image for PowerSearch MCP
# - Builds the wheel with uv
# - Prefetches Camoufox assets into a shared cache
# - Ships a non-root runtime that can run HTTP (default) or STDIO without external configs

############################
# Builder
############################
FROM python:3.13-slim AS builder

ARG VERSION=0.0.0

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    XDG_CACHE_HOME=/var/cache/powersearch \
    SETUPTOOLS_SCM_PRETEND_VERSION_FOR_POWERSEARCH_MCP=${VERSION} \
    SETUPTOOLS_SCM_PRETEND_VERSION=${VERSION}

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        git \
        libffi-dev \
        libxml2-dev \
        libxslt-dev \
        libssl-dev \
        zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Bring in sources and lockfile for reproducible builds
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src

# Install uv for builds and tooling
RUN pip install --no-cache-dir uv

# Install deps (from lock) into a local environment and prefetch Camoufox assets
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen

RUN --mount=type=cache,target=/root/.cache/uv \
    uv run camoufox fetch --browserforge

# Build distribution artifacts
RUN --mount=type=cache,target=/root/.cache/uv \
    uv build

############################
# Runtime
############################
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    XDG_CACHE_HOME=/var/cache/powersearch

WORKDIR /app

# Runtime system deps for Camoufox/Playwright and HTTP server
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        at-spi2-core \
        ca-certificates \
        curl \
        dbus \
        fonts-dejavu-core \
        libasound2 \
        libgtk-3-0 \
        libnss3 \
        libpango-1.0-0 \
        libstdc++6 \
        tzdata \
        xvfb \
    && rm -rf /var/lib/apt/lists/*

# Create app and cache dirs up front
RUN mkdir -p /app /var/cache/powersearch

# Install built wheel
COPY --from=builder /app/dist/powersearch_mcp*.whl /tmp/
RUN pip install --no-cache-dir /tmp/powersearch_mcp*.whl && rm /tmp/powersearch_mcp*.whl

# Copy source tree for direct module entrypoint (no external config)
COPY --from=builder /app/src /app/src

# Copy pre-fetched Camoufox cache
COPY --from=builder /var/cache/powersearch /var/cache/powersearch

# Copy entrypoint script
COPY entrypoint.sh /usr/local/bin/powersearch-entrypoint
RUN chmod +x /usr/local/bin/powersearch-entrypoint

# Drop privileges (Debian syntax)
RUN groupadd --system powersearch \
    && useradd --system --gid powersearch --create-home --home-dir /home/powersearch powersearch \
    && chown -R powersearch:powersearch /app /var/cache/powersearch
USER powersearch

EXPOSE 8099

ENTRYPOINT ["/usr/local/bin/powersearch-entrypoint"]
