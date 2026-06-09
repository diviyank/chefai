# chefai

chefai is a phone-first local web app for managing your kitchen — pantry/groceries (with expiry),
your household & dietary profile, tools, and skills — and turning that state into **ready-to-paste
LLM prompts** for recipe ideas and multi-day meal plans. chefai never calls an LLM itself: you copy
its prompt into the assistant of your choice, and (for plans/recipes) paste the structured reply
back so chefai can store plans, build store-grouped shopping lists, and run a guided cooking mode.
The UI is in French.

## Quick start (Docker)

The default `docker-compose.yml` is **runtime / pull-based** — it runs the published multi-arch
image, no source or build needed:

```bash
# edit docker-compose.yml: set image: ghcr.io/OWNER/chefai:latest (your GitHub owner)
docker compose pull && docker compose up -d
# open http://<host>:8000
```

To build from source locally instead, merge the build override:

```bash
docker compose -f docker-compose.yml -f docker-compose.build.yml up -d --build
```

### Configuration

| Variable | Default | Purpose |
|---|---|---|
| `CHEFAI_DB_PATH` | `/data/chefai.db` | SQLite database location (kept on a volume) |
| Port | `8000` | Change the left side of `ports:` in compose |

Data persists in the named volume `chefai-data` (mounted at `/data`), surviving rebuilds and reboots.

## Deploy on a DietPi (LAN)

1. Install Docker: `dietpi-software` → install **Docker** + **Docker Compose**.
2. Copy this repo (or just `docker-compose.yml`) to the DietPi.
3. The published image is **multi-arch** (`amd64`, `arm64`, `armv7`), so it runs on Pi-class boards:
   ```bash
   docker compose pull && docker compose up -d
   ```
4. Find the DietPi's LAN address: `hostname -I`.
5. On your phone (same Wi-Fi), open `http://<dietpi-ip>:8000`.
6. **Add to home screen** for an app-like icon (Chrome/Safari → Share → "Sur l'écran d'accueil").

## Backup / restore

The whole app state is one SQLite file.

```bash
# Backup
docker run --rm -v chefai-data:/data -v "$PWD":/backup alpine \
  cp /data/chefai.db /backup/chefai-backup.db
# Restore
docker run --rm -v chefai-data:/data -v "$PWD":/backup alpine \
  cp /backup/chefai-backup.db /data/chefai.db
docker compose restart
```

## Offline shopping mode

"Mode courses" renders the list client-side and stores tick-state in your browser's `localStorage`,
so it works at the store with no connection to the DietPi. Open it once on home Wi-Fi before leaving.

## Advanced: HTTPS + full offline PWA (optional)

Over plain LAN HTTP there is no service worker (browsers require a secure context). To make the whole
app installable and reliably offline — and to enable future camera/barcode features — put chefai behind
HTTPS with a self-signed certificate (e.g. via a Caddy reverse proxy) and trust the cert once on your
phone, then register a service worker. This is optional and not required for daily use.

## Development

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest -q
uvicorn app.main:app --reload
```
