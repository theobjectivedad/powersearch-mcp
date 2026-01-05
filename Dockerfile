############################
# Builder
############################
FROM python:3.13-slim AS builder

ARG VERSION=0.0.0

WORKDIR /build

RUN apt-get update -y \
    && apt-get install -y --no-install-recommends \
        build-essential \
        git

# Install uv
RUN pip install --no-cache-dir uv

COPY . ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv build

############################
# Runtime
############################
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

ENV APP_DIR=/app
ENV APP_USER=app
ENV APP_GROUP=app

# Install runtime system dependencies, update CA certificates
RUN apt-get update -y \
    && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates && \
    update-ca-certificates && \
    pip install --no-cache-dir uv && \
    rm -rf /var/lib/apt/lists/*

# Create application user and group
RUN groupadd --system ${APP_GROUP} && \
    useradd --system --gid ${APP_GROUP} --create-home --home-dir /home/${APP_USER} ${APP_USER} && \
    mkdir -p ${APP_DIR} && \
    chown -R ${APP_USER}:${APP_GROUP} ${APP_DIR}

# Install the built package from the builder stage
COPY --from=builder /build/dist/powersearch_mcp-*-py3-none-any.whl /tmp/
RUN pip install --no-cache-dir /tmp/powersearch_mcp-*-py3-none-any.whl && \
    rm /tmp/powersearch_mcp-*-py3-none-any.whl

# Install Playwright browsers
RUN mkdir -p ${PLAYWRIGHT_BROWSERS_PATH} && \
    uv run playwright install --with-deps

# Force Download of browserforge data, places files under
# /usr/local/lib/python3.13/site-packages/browserforge/headers/data
RUN scrapling extract stealthy-fetch https://www.google.com /tmp/out.html && \
    rm /tmp/out.html

# Add entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

USER ${APP_USER}

WORKDIR /app

# Expose the PowerSearch MCP default port
EXPOSE 8099

ENTRYPOINT ["/entrypoint.sh"]
