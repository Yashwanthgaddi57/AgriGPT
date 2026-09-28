-- =====================================================================
-- AgriSphere AI — Supabase PostgreSQL schema (baseline)
-- Run in Supabase SQL Editor (or psql) before first backend start.
-- Alembic manages migrations going forward.
-- =====================================================================

create extension if not exists "pgcrypto";
create extension if not exists "uuid-ossp";

-- ---------------------------------------------------------------------
-- Updated-at trigger helper
-- ---------------------------------------------------------------------
create or replace function set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

-- ---------------------------------------------------------------------
-- Enums
-- ---------------------------------------------------------------------
create type soil_type as enum (
  'black', 'alluvial', 'loamy', 'clay', 'sandy', 'silt', 'laterite', 'red', 'peaty', 'unknown'
);
create type water_availability as enum ('rainfed', 'canal', 'borewell', 'well', 'river', 'pond', 'none');
create type notification_type as enum ('weather', 'disease', 'market', 'profit', 'system');
create type notification_channel as enum ('push', 'email', 'in_app');
create type agent_name as enum (
  'coordinator', 'crop_recommendation', 'disease_detection', 'weather',
  'market_forecast', 'profit_optimization', 'advisor'
);
create type agent_log_level as enum ('debug', 'info', 'warning', 'error');
create type chat_role as enum ('user', 'assistant', 'system');
create type severity_level as enum ('low', 'medium', 'high', 'critical');

-- ---------------------------------------------------------------------
-- users (profile; auth handled by Supabase Auth -> auth.users)
-- ---------------------------------------------------------------------
create table users (
  id uuid primary key references auth.users(id) on delete cascade,
  email text not null unique,
  name text not null,
  phone text,
  district text,
  state text,
  village text,
  latitude numeric(9, 6),
  longitude numeric(9, 6),
  location_source text check (location_source in ('gps', 'map_pin', 'geocoded')),
  farm_size_acres numeric(10, 2) not null default 0 check (farm_size_acres >= 0),
  soil_type soil_type not null default 'unknown',
  water_availability water_availability not null default 'rainfed',
  language text not null default 'en',
  avatar_url text,
  role text not null default 'farmer', -- farmer | consultant | cooperative | government | admin
  onboarding_completed boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create trigger trg_users_updated_at before update on users
  for each row execute function set_updated_at();

-- ---------------------------------------------------------------------
-- farms
-- ---------------------------------------------------------------------
create table farms (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id) on delete cascade,
  name text not null,
  district text,
  state text,
  village text,
  area_acres numeric(10, 2) not null default 0 check (area_acres >= 0),
  soil_type soil_type not null default 'unknown',
  water_source water_availability not null default 'rainfed',
  current_crop text,
  current_season text, -- kharif | rabi | zaid
  latitude numeric(9, 6),
  longitude numeric(9, 6),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create trigger trg_farms_updated_at before update on farms
  for each row execute function set_updated_at();
create index idx_farms_user on farms(user_id);

-- ---------------------------------------------------------------------
-- recommendations (crop recommendation engine results)
-- ---------------------------------------------------------------------
create table recommendations (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id) on delete cascade,
  farm_id uuid references farms(id) on delete set null,
  location text not null,
  season text not null,
  farm_size_acres numeric(10, 2) not null default 0,
  soil_type soil_type not null default 'unknown',
  water_source water_availability not null default 'rainfed',
  budget_inr numeric(14, 2) not null default 0,
  crops jsonb not null default '[]'::jsonb, -- array of crop objects
  model text,
  prompt_tokens integer,
  completion_tokens integer,
  created_at timestamptz not null default now()
);
create index idx_recommendations_user on recommendations(user_id, created_at desc);

-- ---------------------------------------------------------------------
-- disease_reports
-- ---------------------------------------------------------------------
create table disease_reports (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id) on delete cascade,
  farm_id uuid references farms(id) on delete set null,
  crop text not null,
  image_path text, -- Supabase Storage path
  image_url text,
  disease_name text not null,
  is_healthy boolean not null default false,
  confidence numeric(5, 2) not null default 0 check (confidence >= 0 and confidence <= 100),
  severity severity_level not null default 'low',
  severity_score numeric(5, 2) not null default 0,
  symptoms text,
  cause text,
  treatment text,
  prevention text,
  spread_risk text,
  model text,
  created_at timestamptz not null default now()
);
create index idx_disease_user on disease_reports(user_id, created_at desc);
create index idx_disease_crop on disease_reports(crop);

-- ---------------------------------------------------------------------
-- profit_predictions
-- ---------------------------------------------------------------------
create table profit_predictions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id) on delete cascade,
  farm_id uuid references farms(id) on delete set null,
  crop text not null,
  farm_size_acres numeric(10, 2) not null default 0,
  season text,
  seed_cost numeric(14, 2) not null default 0,
  labor_cost numeric(14, 2) not null default 0,
  fertilizer_cost numeric(14, 2) not null default 0,
  irrigation_cost numeric(14, 2) not null default 0,
  transportation_cost numeric(14, 2) not null default 0,
  other_cost numeric(14, 2) not null default 0,
  total_cost numeric(14, 2) not null default 0,
  expected_yield_quintals numeric(12, 2) not null default 0,
  expected_price_per_quintal numeric(12, 2) not null default 0,
  expected_revenue numeric(14, 2) not null default 0,
  expected_profit numeric(14, 2) not null default 0,
  roi numeric(8, 2) not null default 0, -- percent
  risk_score numeric(5, 2) not null default 0,
  confidence_score numeric(5, 2) not null default 0,
  scenarios jsonb not null default '{}'::jsonb, -- best | average | worst
  model text,
  created_at timestamptz not null default now()
);
create index idx_profit_user on profit_predictions(user_id, created_at desc);

-- ---------------------------------------------------------------------
-- market_predictions
-- ---------------------------------------------------------------------
create table market_predictions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id) on delete cascade,
  crop text not null,
  market text,
  current_price numeric(12, 2) not null default 0, -- INR per quintal
  price_unit text not null default 'INR/quintal',
  trend_weekly numeric(6, 2) not null default 0, -- percent change
  trend_monthly numeric(6, 2) not null default 0,
  trend_quarterly numeric(6, 2) not null default 0,
  demand_forecast text, -- rising | stable | falling
  supply_forecast text,
  price_forecast_7d numeric(12, 2) not null default 0,
  price_forecast_14d numeric(12, 2) not null default 0,
  price_forecast_30d numeric(12, 2) not null default 0,
  recommendation text not null default 'hold', -- sell_now | wait_1_week | wait_2_weeks
  confidence numeric(5, 2) not null default 0,
  reasoning text,
  price_history jsonb not null default '[]'::jsonb,
  model text,
  created_at timestamptz not null default now()
);
create index idx_market_user on market_predictions(user_id, created_at desc);
create index idx_market_crop on market_predictions(crop, created_at desc);

-- ---------------------------------------------------------------------
-- weather_records
-- ---------------------------------------------------------------------
create table weather_records (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id) on delete cascade,
  farm_id uuid references farms(id) on delete set null,
  location text,
  latitude numeric(9, 6),
  longitude numeric(9, 6),
  record_date date not null,
  temp_c numeric(6, 2),
  feels_like_c numeric(6, 2),
  humidity numeric(6, 2),
  wind_kph numeric(6, 2),
  precip_mm numeric(8, 2),
  precip_probability numeric(5, 2),
  condition text,
  alert text,
  ai_recommendation text,
  action text, -- plant_now | delay_planting | harvest_now | irrigate | none
  model text,
  created_at timestamptz not null default now()
);
create index idx_weather_user_date on weather_records(user_id, record_date desc);

-- ---------------------------------------------------------------------
-- chat_sessions
-- ---------------------------------------------------------------------
create table chat_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id) on delete cascade,
  title text not null default 'New conversation',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create trigger trg_chat_sessions_updated_at before update on chat_sessions
  for each row execute function set_updated_at();
create index idx_chat_sessions_user on chat_sessions(user_id, updated_at desc);

-- ---------------------------------------------------------------------
-- chat_messages
-- ---------------------------------------------------------------------
create table chat_messages (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references chat_sessions(id) on delete cascade,
  user_id uuid not null references users(id) on delete cascade,
  role chat_role not null,
  content text not null,
  agent text, -- which agent produced an assistant reply
  tokens integer,
  created_at timestamptz not null default now()
);
create index idx_chat_messages_session on chat_messages(session_id, created_at);

-- ---------------------------------------------------------------------
-- notifications
-- ---------------------------------------------------------------------
create table notifications (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id) on delete cascade,
  type notification_type not null default 'system',
  channel notification_channel not null default 'in_app',
  title text not null,
  body text not null,
  link text,
  is_read boolean not null default false,
  sent_at timestamptz,
  created_at timestamptz not null default now()
);
create index idx_notifications_user on notifications(user_id, created_at desc);

-- ---------------------------------------------------------------------
-- activities (audit / feed)
-- ---------------------------------------------------------------------
create table activities (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id) on delete cascade,
  action text not null,
  entity_type text,
  entity_id uuid,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index idx_activities_user on activities(user_id, created_at desc);

-- ---------------------------------------------------------------------
-- agent_logs (LangGraph observability)
-- ---------------------------------------------------------------------
create table agent_logs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references users(id) on delete set null,
  agent agent_name not null,
  level agent_log_level not null default 'info',
  action text not null,
  input jsonb,
  output jsonb,
  latency_ms integer,
  tokens integer,
  error text,
  created_at timestamptz not null default now()
);
create index idx_agent_logs_agent on agent_logs(agent, created_at desc);
create index idx_agent_logs_user on agent_logs(user_id, created_at desc);

-- ---------------------------------------------------------------------
-- mandis (APMC market directory for location-aware price intelligence)
-- ---------------------------------------------------------------------
create table mandis (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  city text,
  district text,
  state text,
  latitude numeric(9, 6) not null,
  longitude numeric(9, 6) not null,
  major_crops jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now()
);
create index idx_mandis_district on mandis(district);

-- ---------------------------------------------------------------------
-- vendors (agri-input shops & produce buyers directory)
-- ---------------------------------------------------------------------
create table vendors (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  category text not null check (category in ('seeds', 'fertilizer', 'pesticide', 'equipment', 'produce_buyer')),
  description text,
  phone text,
  address text,
  city text,
  district text,
  state text,
  latitude numeric(9, 6) not null,
  longitude numeric(9, 6) not null,
  crops jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now()
);
create index idx_vendors_category on vendors(category);
create index idx_vendors_district on vendors(district);
