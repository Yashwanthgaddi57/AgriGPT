<div align="center">

# 🌱 AgriGPT

**AI-Powered Farmer Income Optimization Platform**

Crop recommendations · Disease detection · Profit prediction · Live mandi prices · Weather advisories · Multi-agent AI copilot

`Next.js 15` · `FastAPI` · `Claude Sonnet (Bedrock)` · `LangGraph` · `Supabase` · `PostgreSQL` · `Docker`

</div>

---

## What it does

AgriGPT routes every farmer question through a **LangGraph multi-agent system** — a Coordinator that classifies intent and six specialists that answer with numeric rigor:

| Agent | Capability |
|---|---|
| 🌾 Crop Recommendation | 5 ranked crops by expected profit for soil/water/budget/season |
| 🔬 Disease Detection | Claude Vision on leaf photos → severity, treatment, prevention |
| 💰 Profit Optimization | Best/average/worst-case yield, revenue, ROI scenarios |
| 📈 Market Forecast | Price trends, demand/supply, sell-now vs wait guidance |
| ⛅ Weather Agent | 7-day agro-meteorology → plant/irrigate/harvest actions |
| 💬 Advisor | Conversational copilot with full farm context memory |

Everything the AI produces is **persisted** (recommendations, reports, predictions, forecasts, chat, agent logs) and surfaced through dashboards, history pages and analytics KPIs.

### Realtime market intelligence

- **Live mandi price ticker** on the dashboard — price chips with weekly ▲▼ trend for the farmer's crops, auto-refreshing every 5 min (`GET /api/v1/market/ticker`, no AI calls, cached 1h).
- **Real Agmarknet data** via data.gov.in: commodity aliases (cotton → "Kapas"), fuzzy district matching, tiered scope (market > district > state > national), and a circuit breaker that fails fast to a documented synthetic baseline when the free API throttles.
- **Alert scheduler** (APScheduler): weather alerts, market price-move notifications ("Tomato down 12% this week — consider selling now") and agro-action advisories (irrigate / delay harvest) with same-day dedup.
- Prices degrade gracefully: keyed feed → keyless scrape → labeled estimate.

## Architecture

```
┌─────────────────┐      HTTPS/JWT      ┌──────────────────┐
│  Next.js 15     │ ──────────────────► │  FastAPI         │
│                 │                     │  ├─ Routers      │
│  Tailwind/shadcn│                     │  ├─ Services     │
│  TanStack Query │                     │  ├─ LangGraph ▸──┼──► Claude Sonnet (Bedrock)
│  Recharts       │                     │  │   6 agents    │
└─────────────────┘                     │  └─ SQLAlchemy   │
                                        └───────┬──────────┘
        data.gov.in (Agmarknet) ◄───────────────┤
        Open-Meteo (weather) ◄──────────────────┤
                                                ▼
                            ┌───────────────────────────────┐
                            │ Supabase: Postgres + Auth +   │
                            │ Storage (disease-images) + RLS│
                            └───────────────┬───────────────┘
                                            ▼
                                Redis or in-process cache
```

## Repository layout

```
agrigpt/
├── backend/
│   ├── app/
│   │   ├── ai/                 # claude_client, prompts, weather_client, LangGraph agents
│   │   ├── core/               # config, database, security(JWT), middleware, cache, deps
│   │   ├── models/             # 12 SQLAlchemy models
│   │   ├── schemas/            # Pydantic request/response schemas
│   │   ├── services/           # crop, disease, profit, market, weather, chat, notifications,
│   │   │                       #   analytics, dashboard, agmarknet_client (live mandi prices)
│   │   ├── routers/            # auth, users, dashboard, crops, disease, profit, market, weather,
│   │   │                       #   chat, notifications, analytics, admin
│   │   ├── main.py             # FastAPI app + lifespan scheduler
│   │   └── scheduler.py        # APScheduler: weather + market + agro-action alerts
│   ├── alembic/                # migrations (0001 initial schema)
│   ├── tests/                  # pytest suite (54 tests, no external services)
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/                # landing, auth/* (incl. reset-password), dashboard/* (8 feature pages)
│   │   ├── components/         # ui/* (shadcn-style), dashboard/price-ticker, landing/*
│   │   ├── contexts/           # auth (Supabase + backend profile sync)
│   │   ├── hooks/              # use-api (TanStack Query for every endpoint), use-toast
│   │   ├── lib/                # api (axios + refresh), supabase, utils
│   │   └── types/              # shared TS types
│   └── Dockerfile
├── supabase/
│   ├── schema.sql              # full DDL: enums, 12 tables, indexes, triggers
│   └── policies.sql            # RLS + storage bucket policies
├── docs/API.md                 # full endpoint reference
├── docker-compose.yml          # postgres + redis + backend + frontend (local)
└── .env.example
```

## Quick start (local)

### Prerequisites
- Python 3.12, Node 20+
- A Supabase project (free tier works) — or use docker-compose Postgres for pure-local dev

### 1. Supabase setup (recommended)
1. Create a project at [supabase.com](https://supabase.com).
2. SQL Editor → run `supabase/schema.sql`, then `supabase/policies.sql`.
3. Auth → disable "Confirm email" if you want instant logins in dev.
4. Copy `Settings → API` values into your env.

### 2. Backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt      # Windows
# source .venv/bin/activate && pip install -r requirements.txt

cp ../.env.example .env                            # fill in values
.venv/Scripts/alembic upgrade head                 # plain-Postgres deployments
# (on Supabase, schema.sql already created everything; still run alembic to stamp)

.venv/Scripts/uvicorn app.main:app --reload --port 8000
```

Swagger: http://localhost:8000/docs

### 3. Frontend

```bash
cd frontend
npm install
cp ../.env.example .env.local                      # fill NEXT_PUBLIC_* values
npm run dev
```

App: http://localhost:3000

### 4. Or run everything with Docker

```bash
cp .env.example .env
docker compose up --build
# frontend :3000, backend :8000, postgres :5432, redis :6379
```

## Environment variables

See [.env.example](.env.example). Key values:

| Var | Where | Purpose |
|---|---|---|
| `AI_PROVIDER` / `BEDROCK_API_KEY` (or `ANTHROPIC_API_KEY`) | backend | Claude Sonnet for all agents |
| `SUPABASE_URL` / `SERVICE_KEY` / `ANON_KEY` / `JWT_SECRET` | backend | DB, auth verification, storage |
| `SUPABASE_DB_URL` | backend | SQLAlchemy connection string (use the Supabase **pooler** URI) |
| `DATA_GOV_API_KEY` | backend | Live Agmarknet mandi prices — free key at [data.gov.in/user/register](https://data.gov.in/user/register); empty → synthetic baseline |
| `FRONTEND_APP_URL` | backend | Base URL used for password-reset email links |
| `REDIS_URL` | backend | optional — cache + rate limiting (in-process fallback is automatic) |
| `NEXT_PUBLIC_SUPABASE_URL` / `ANON_KEY` | frontend | browser auth |
| `NEXT_PUBLIC_API_URL` | frontend | FastAPI base URL |

## Deployment

The repo ships container-ready Docker images for both halves (see `Dockerfile` and `backend/Dockerfile`), plus `docker-compose.yml` for a full local stack. Deploy the two services on any platform that runs containers (Fly.io, Railway, ECS, Cloud Run, a VPS, ...) and wire them together with environment variables — no platform-specific config files are committed.

### 1 · Create the database schema on Supabase (one time)
1. Supabase → SQL Editor → run `supabase/schema.sql`, then `supabase/policies.sql` (or `alembic upgrade head`).
2. Grab from **Settings → API**: project URL, anon key, service-role key, JWT secret.

### 2 · Provision the two services
- **Backend** — build the repo root `Dockerfile`, expose `$PORT`, health check `/health`.
- **Frontend** — build `frontend/Dockerfile`, expose port 3000.
- Required backend env: `ENVIRONMENT=production`, Supabase keys, `SUPABASE_DB_URL`, AI keys, `BACKEND_CORS_ORIGINS`, `FRONTEND_APP_URL`, `RESEND_API_KEY`.
- Required frontend env: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_APP_URL`.

### 3 · The database URL (common gotcha)
If your host is IPv4-only, use Supabase's **Transaction pooler** URI (port 6543) — the direct `db.<ref>.supabase.co` host is IPv6-only:

```
postgresql+psycopg://postgres.<PROJECT_REF>:PASSWORD@aws-0-<REGION>.pooler.supabase.com:6543/postgres
```

### 4 · URLs must match
- backend: `BACKEND_CORS_ORIGINS` (must include the frontend origin), `FRONTEND_APP_URL`
- frontend: `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_APP_URL`

### 5 · Post-deploy checklist
- [ ] `https://<api-url>/health` returns 200
- [ ] Supabase → Auth → **URL Configuration**: Site URL = frontend URL; add `/*/auth/callback` and `/*/auth/reset-password` redirects
- [ ] Supabase → Auth → Providers → Email → keep **"Confirm email"** enabled (the backend emails its own 6-digit code via Resend)
- [ ] Google OAuth: add `https://<frontend-url>/auth/callback` to the Google Cloud redirect URIs
- [ ] Sign up, log in, check the dashboard price ticker

### Operations notes
- Keep **one** uvicorn worker — APScheduler must run exactly once, or alerts duplicate.
- Redis is optional: the cache and rate limiter fall back to in-process automatically. Add a managed Redis later and set `REDIS_URL`.
- `DATA_GOV_API_KEY` ships with data.gov.in's public trial key for convenience — register your own free key for production rate limits.

## Testing

```bash
cd backend && .venv/Scripts/python -m pytest tests/ -v     # 54 tests
cd frontend && npm run typecheck && npm run build          # type-safe production build
```

Backend tests run fully offline: SQLite in-memory DB, auth overridden, no Claude/Redis calls.

## Security model

- **Auth**: Supabase Auth issues JWTs; FastAPI verifies via JWKS (RS256/ES256) with HS256 fallback; profile rows auto-provision on first request.
- **RLS**: every table locked to `auth.uid()` for anon/authenticated clients; the backend alone holds the service-role key.
- **Storage**: `disease-images` bucket — public read, owner-scoped writes under `{user_id}/` prefix.
- **Rate limiting**: Redis fixed-window per IP (120 req/min), fail-open (in-process fallback otherwise).
- **Secrets**: environment-only; `.env*` git-ignored and never committed.

## Roadmap

- Personal registered data.gov.in key + eNAM coverage beyond the trial key's rate limits
- Bilingual UI (Hindi/Marathi) beyond the copilot
- WhatsApp bot surface for the copilot
- Field-level satellite NDVI overlays
- Web-push delivery (VAPID scaffolding already present) for alerts with the app closed
