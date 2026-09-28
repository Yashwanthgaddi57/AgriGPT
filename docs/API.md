# AgriSphere AI — API Documentation

Base URL: `{API_URL}/api/v1` · Interactive docs: `{API_URL}/docs` (Swagger UI)

## Authentication

All endpoints except `/auth/*` and `/health` require a Supabase JWT:

```
Authorization: Bearer <access_token>
```

Tokens come from `POST /auth/login` (password grant) or Supabase client SDK flows.
On `401`, refresh via Supabase `grant_type=refresh_token` and retry once.

Error contract:

```json
{ "error": { "code": "NotFoundError", "detail": "Resource not found", "path": "/api/v1/farms/x" } }
```

---

## Auth

| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/auth/register` | `{email, password, name, phone?, district?, state?, village?, farm_size_acres?, soil_type?, water_availability?}` | `{message}` (201) |
| POST | `/auth/login` | `{email, password}` | `{access_token, refresh_token, expires_in, token_type, user}` |
| POST | `/auth/forgot-password` | `{email}` | `{message}` |

## Profile & Farms

| Method | Path | Body / Params | Response |
|---|---|---|---|
| GET | `/profile` | — | `Profile` |
| PATCH | `/profile` | partial `Profile` | `Profile` |
| GET | `/farms` | — | `Farm[]` |
| POST | `/farms` | `{name, area_acres, soil_type?, water_source?, ...}` | `Farm` (201) |
| GET/PATCH/DELETE | `/farms/{farm_id}` | — | `Farm` / `204` |

## Dashboard

| Method | Path | Response |
|---|---|---|
| GET | `/dashboard` | `{widgets: {current_crop, current_season, expected_revenue, expected_profit, risk_score, disease_alerts, weather_alerts, weather_action, market_recommendations}, charts: {revenue_projection, profit_projection, yield_estimation, demand_forecast, weather_forecast}}` |

## Crop Recommendation

| Method | Path | Body / Params | Response |
|---|---|---|---|
| POST | `/crops/recommend` | `{location, farm_size_acres, soil_type, water_source, budget_inr, season, farm_id?}` | `Recommendation` with 5 ranked `crops[]` |
| GET | `/crops/history` | `?page&page_size` | `{items: Recommendation[], total, page, page_size}` |

Each crop item: `{crop_name, investment_inr, expected_revenue_inr, expected_profit_inr, risk_score (0-100), confidence_score (0-100), yield_quintals_per_acre, duration_days, why_recommended, risks[]}`

## Disease Detection

| Method | Path | Body / Params | Response |
|---|---|---|---|
| POST | `/disease/analyze` | `multipart/form-data`: `image` (file ≤10MB), `crop` (form field), `farm_id?` | `DiseaseReport` |
| GET | `/disease/reports` | `?page&page_size` | `{items, total, ...}` |
| GET | `/disease/reports/{id}` | — | `DiseaseReport` |
| GET | `/disease/analytics` | — | `{total_reports, healthy_count, diseased_count, top_diseases, by_crop, by_severity, monthly_volume, avg_confidence}` |

`DiseaseReport`: `{id, crop, image_url, disease_name, is_healthy, confidence, severity (low\|medium\|high\|critical), severity_score, symptoms, cause, treatment, prevention, spread_risk, created_at}`

## Profit Prediction

| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/profit/predict` | `{crop, farm_size_acres, season?, seed_cost, labor_cost, fertilizer_cost, irrigation_cost, transportation_cost, other_cost?, farm_id?}` | `ProfitPrediction` |
| GET | `/profit/predictions` | `?page&page_size` | `{items, total, ...}` |

`ProfitPrediction` includes `scenarios: {best, average, worst}` each `{yield_quintals, price_per_quintal, revenue_inr, profit_inr, roi_percent}`.

## Market Intelligence

| Method | Path | Body / Params | Response |
|---|---|---|---|
| POST | `/market/analyze` | `{crop, market?}` | `MarketPrediction` |
| GET | `/market/predictions` | `?page&page_size` | `{items, total, ...}` |
| GET | `/market/history` | `?crop&limit` | `{items}` |

`MarketPrediction` includes trends (weekly/monthly/quarterly %), forecasts (7/14/30d), `recommendation` (`sell_now`/`wait_1_week`/`wait_2_weeks`), `confidence`, `reasoning`, 90-day `price_history`.

## Weather

| Method | Path | Params | Response |
|---|---|---|---|
| GET | `/weather` | `?location` (defaults to profile district) | `{location, days[7], ai_recommendation, action, alerts[]}` |
| GET | `/weather/history` | `?limit` | `{items}` |

`action` ∈ `plant_now | delay_planting | harvest_now | irrigate | none`

## Chat (AI Farm Copilot)

| Method | Path | Body / Params | Response |
|---|---|---|---|
| GET | `/chat/sessions` | — | `ChatSession[]` |
| POST | `/chat/sessions` | `{title?}` | `ChatSession` (201) |
| GET | `/chat/sessions/{id}/messages` | — | `ChatMessage[]` |
| DELETE | `/chat/sessions/{id}` | — | `204` |
| POST | `/chat/messages` | `{content, agent?}` | `{session_id, message: ChatMessage, agent}` |

`agent` is optional; when provided it bypasses the coordinator router (`crop`, `disease`, `weather`, `market`, `profit`, `advisor`). Otherwise the LangGraph coordinator classifies intent and routes to specialists.

## Notifications

| Method | Path | Body / Params | Response |
|---|---|---|---|
| GET | `/notifications` | `?unread_only&limit` | `{items, unread_count}` |
| POST | `/notifications/mark-read` | `{ids: string[]}` | `{marked}` |
| GET | `/notifications/unread-count` | — | `{count}` |

## Analytics

| Method | Path | Response |
|---|---|---|
| GET | `/analytics/kpis` | `{expected_revenue, expected_profit, disease_frequency, yield_growth, profit_growth, weather_risk, recommendation_accuracy, profit_prediction_accuracy}` |
| GET | `/analytics/activities` | `?page&page_size` → `{items, total, ...}` |

## Admin (role=admin)

| Method | Path | Response |
|---|---|---|
| GET | `/admin/agent-logs` | `{items, total, page, page_size}` — LangGraph observability |
| GET | `/admin/users/{user_id}/agent-logs` | `{items, total, ...}` |

## Subscription & Plans

| Method | Path | Response |
|---|---|---|
| GET | `/subscription/plans` | `{plans: [{id, name, price_inr, period, description, features, limits}], payments_enabled}` — public pricing source of truth |
| GET | `/subscription` | `{plan, meta, limits, usage: {feature: {used, limit}}}` (auth) |
| POST | `/subscription/checkout` | `501` until a payment provider is integrated — never fakes success |

Plan limits are enforced server-side on `POST /crops/recommend`,
`/disease/analyze`, `/market/analyze`, `/profit/predict` (monthly) and
`/chat/messages[/stream]` (daily). Exceeding a limit returns **429** with an
upgrade hint. Limits/config live in `backend/app/core/plans.py` only.

## Disease follow-up

| Method | Path | Body | Response |
|---|---|---|---|
| PATCH | `/disease/reports/{id}` | `{followup_status?: open\|monitoring\|treated\|resolved, notes?: str}` | `DiseaseReport` |

Reports may include `alternatives` (other plausible explanations),
`followup_status` and farmer `notes`. Confidence < 40 is an inconclusive scan.

## Analytics events

| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/analytics/events` | `{event, metadata?}` | `{tracked}` — allowlist-only funnel events |

## Chat extras

`POST /chat/messages` and `/chat/messages/stream` accept an optional
`language` hint (`en|hi|te|ta|kn|mr`). The reply language is chosen from this
hint, falling back to the profile language.

## System

| Method | Path | Response |
|---|---|---|
| GET | `/health` | `{status, service, environment}` |
