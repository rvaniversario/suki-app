# Suki: one container that serves the app and keeps its own prices up to date.
#
#   docker compose up -d --build        # http://localhost:8080
#
# nginx serves the built PWA; the scraper runs alongside it, fills the /data volume on first
# start (HISTORY_DAYS, default 365) and refreshes it every day (REFRESH_UTC, default 2 =
# 10:00 Manila). New prices show up in the app with no rebuild or redeploy.
#
# Mount a volume at /data so prices survive restarts. Listens on $PORT (default 80).
# Optional app backend settings are build args (Vite inlines them):
#   VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY, VITE_VAPID_PUBLIC_KEY

# ---------------------------------------------------------------- app build
FROM node:22-alpine AS app-build
WORKDIR /src/app
COPY app/package.json app/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY app/ ./
ARG VITE_SUPABASE_URL=
ARG VITE_SUPABASE_ANON_KEY=
ARG VITE_VAPID_PUBLIC_KEY=
ENV VITE_SUPABASE_URL=$VITE_SUPABASE_URL \
    VITE_SUPABASE_ANON_KEY=$VITE_SUPABASE_ANON_KEY \
    VITE_VAPID_PUBLIC_KEY=$VITE_VAPID_PUBLIC_KEY
RUN npm run build

# ---------------------------------------------------------------- runtime
FROM python:3.12-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends nginx wget \
 && rm -rf /var/lib/apt/lists/* /etc/nginx/sites-enabled/default
WORKDIR /srv
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    SUKI_DATA_DIR=/data \
    PORT=80
COPY scraper/requirements.txt scraper/requirements.txt
RUN pip install -r scraper/requirements.txt
COPY scraper/ scraper/
RUN rm -rf scraper/tests
COPY docker/nginx.conf /etc/nginx/conf.d/suki.conf.template
COPY docker/scraper.sh docker/start.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/scraper.sh /usr/local/bin/start.sh
COPY --from=app-build /src/app/dist /usr/share/nginx/html
VOLUME /data
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s CMD wget -qO- "http://127.0.0.1:${PORT}/healthz" || exit 1
CMD ["start.sh"]
