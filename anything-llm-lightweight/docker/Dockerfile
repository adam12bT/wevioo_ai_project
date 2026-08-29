# Lightweight Dockerfile for the stripped-down AnythingLLM fork (no frontend).
# Node version is pinned here — safe to change without touching your host machine's Node at all.
FROM node:20-bookworm-slim

# NOTE: node:*-slim images already ship with a built-in "node" user at UID/GID 1000 —
# we reuse it instead of creating a new one (which previously collided: "groupadd: GID
# '1000' already exists"). If you ever need a different UID/GID (e.g. to match your host
# user for volume permissions), change these to something unused, like 1001.
ARG ARG_UID=1000
ARG ARG_GID=1000

# System dependencies needed by native modules still in use
# (canvas/chartjs-node-canvas need these font/graphics libs; build-essential + python3 for node-gyp)
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -yq --no-install-recommends \
        build-essential python3 git curl ca-certificates \
        libcairo2 libcairo2-dev libpango-1.0-0 libpangocairo-1.0-0 \
        libjpeg62-turbo libgif7 librsvg2-2 \
        netcat-openbsd && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Only create the user/group if the requested UID/GID differ from the image's
# built-in "node" user (1000:1000) — otherwise just reuse it directly.
RUN if [ "$ARG_UID" != "1000" ] || [ "$ARG_GID" != "1000" ]; then \
        groupadd -g "$ARG_GID" anythingllm && \
        useradd -l -u "$ARG_UID" -m -d /app -s /bin/bash -g anythingllm anythingllm; \
    else \
        usermod -d /app -l anythingllm node && \
        groupmod -n anythingllm node; \
    fi && \
    mkdir -p /app/server /app/collector && chown -R anythingllm:anythingllm /app

COPY ./docker/docker-entrypoint.sh /usr/local/bin/
COPY ./docker/docker-healthcheck.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh /usr/local/bin/docker-healthcheck.sh

USER anythingllm
WORKDIR /app

# --- Server ---
COPY --chown=anythingllm:anythingllm ./server /app/server/
WORKDIR /app/server
RUN npm install --legacy-peer-deps && npm cache clean --force

# --- Collector ---
WORKDIR /app
COPY --chown=anythingllm:anythingllm ./collector/ ./collector/
WORKDIR /app/collector
# Skip Puppeteer's ~200-300MB Chromium download — it's only used by the generic
# website-link scraper (collector/processLink/convert/generic.js), which this
# project doesn't use (we process uploaded PDF/DOCX tenders, not URLs). This is
# very likely what made the collector's npm install take 20+ minutes.
ENV PUPPETEER_SKIP_DOWNLOAD=true
RUN npm install --legacy-peer-deps --loglevel http && npm cache clean --force
WORKDIR /app
ENV NODE_ENV=production
ENV STORAGE_DIR="/app/server/storage"
EXPOSE 3001

HEALTHCHECK --interval=1m --timeout=10s --start-period=1m \
  CMD /bin/bash /usr/local/bin/docker-healthcheck.sh || exit 1

ENTRYPOINT ["/bin/bash", "/usr/local/bin/docker-entrypoint.sh"]