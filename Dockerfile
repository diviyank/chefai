# ---- CSS build stage (Tailwind standalone, no Node) ----
FROM debian:bookworm-slim AS css
WORKDIR /build
RUN apt-get update && apt-get install -y curl ca-certificates && rm -rf /var/lib/apt/lists/*
ARG TARGETARCH
COPY tailwind.config.js ./
COPY app/templates ./app/templates
COPY app/static/css/input.css ./app/static/css/input.css
COPY app/static/js ./app/static/js
# Pin Tailwind v3: the v3-style input.css (@tailwind directives) + tailwind.config.js
# only produce theme color utilities (bg-green-600, text-amber-600, …) under v3.
# "latest" now resolves to v4, which silently drops those color utilities.
ARG TAILWIND_VERSION=v3.4.17
RUN case "$TARGETARCH" in \
      amd64) TWARCH=x64 ;; arm64) TWARCH=arm64 ;; arm) TWARCH=armv7 ;; *) TWARCH=x64 ;; esac && \
    curl -sL "https://github.com/tailwindlabs/tailwindcss/releases/download/${TAILWIND_VERSION}/tailwindcss-linux-${TWARCH}" -o /usr/local/bin/tailwindcss && \
    chmod +x /usr/local/bin/tailwindcss && \
    tailwindcss -c tailwind.config.js -i app/static/css/input.css -o /build/app.css --minify

# ---- Runtime stage ----
FROM python:3.11-slim AS runtime
WORKDIR /app
ENV PYTHONUNBUFFERED=1 CHEFAI_DB_PATH=/data/chefai.db
COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir .
COPY --from=css /build/app.css ./app/static/css/app.css
# Vendor htmx/alpine at build time so the image is CDN-free.
RUN apt-get update && apt-get install -y curl && \
    mkdir -p app/static/vendor && \
    curl -sL https://unpkg.com/htmx.org@1.9.12/dist/htmx.min.js -o app/static/vendor/htmx.min.js && \
    curl -sL https://unpkg.com/alpinejs@3.14.1/dist/cdn.min.js -o app/static/vendor/alpine.min.js && \
    apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*
VOLUME ["/data"]
EXPOSE 1212
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "1212"]
