"""Initial AgriSphere schema

Revision ID: 0001
Revises:
Create Date: 2026-09-22
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels = None
depends_on = None


def _enum(name: str, values) -> postgresql.ENUM:
    return postgresql.ENUM(*values, name=name, create_type=True)


soil_enum = _enum("soil_type", ("black", "alluvial", "loamy", "clay", "sandy", "silt", "laterite", "red", "peaty", "unknown"))
water_enum = _enum("water_availability", ("rainfed", "canal", "borewell", "well", "river", "pond", "none"))

UUID = postgresql.UUID(as_uuid=True)
TS = sa.DateTime(timezone=True)
NOW = sa.func.now()


def upgrade() -> None:
    op.execute('create extension if not exists "pgcrypto"')

    op.create_table(
        "users",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("email", sa.Text(), nullable=False, unique=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("phone", sa.Text()),
        sa.Column("district", sa.Text()),
        sa.Column("state", sa.Text()),
        sa.Column("village", sa.Text()),
        sa.Column("farm_size_acres", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("soil_type", soil_enum, nullable=False, server_default="unknown"),
        sa.Column("water_availability", water_enum, nullable=False, server_default="rainfed"),
        sa.Column("language", sa.Text(), nullable=False, server_default="en"),
        sa.Column("avatar_url", sa.Text()),
        sa.Column("role", sa.Text(), nullable=False, server_default="farmer"),
        sa.Column("onboarding_completed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", TS, server_default=NOW, nullable=False),
        sa.Column("updated_at", TS, server_default=NOW, nullable=False),
    )

    op.create_table(
        "farms",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("district", sa.Text()),
        sa.Column("state", sa.Text()),
        sa.Column("village", sa.Text()),
        sa.Column("area_acres", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("soil_type", soil_enum, nullable=False, server_default="unknown"),
        sa.Column("water_source", water_enum, nullable=False, server_default="rainfed"),
        sa.Column("current_crop", sa.Text()),
        sa.Column("current_season", sa.Text()),
        sa.Column("latitude", sa.Numeric(9, 6)),
        sa.Column("longitude", sa.Numeric(9, 6)),
        sa.Column("created_at", TS, server_default=NOW, nullable=False),
        sa.Column("updated_at", TS, server_default=NOW, nullable=False),
    )
    op.create_index("idx_farms_user", "farms", ["user_id"])

    op.create_table(
        "recommendations",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("farm_id", UUID, sa.ForeignKey("farms.id", ondelete="SET NULL")),
        sa.Column("location", sa.Text(), nullable=False),
        sa.Column("season", sa.Text(), nullable=False),
        sa.Column("farm_size_acres", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("soil_type", soil_enum, nullable=False, server_default="unknown"),
        sa.Column("water_source", water_enum, nullable=False, server_default="rainfed"),
        sa.Column("budget_inr", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("crops", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("model", sa.Text()),
        sa.Column("prompt_tokens", sa.Integer()),
        sa.Column("completion_tokens", sa.Integer()),
        sa.Column("created_at", TS, server_default=NOW, nullable=False),
    )
    op.create_index("idx_recommendations_user", "recommendations", ["user_id", "created_at"])

    op.create_table(
        "disease_reports",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("farm_id", UUID, sa.ForeignKey("farms.id", ondelete="SET NULL")),
        sa.Column("crop", sa.Text(), nullable=False),
        sa.Column("image_path", sa.Text()),
        sa.Column("image_url", sa.Text()),
        sa.Column("disease_name", sa.Text(), nullable=False),
        sa.Column("is_healthy", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("confidence", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("severity", sa.Text(), nullable=False, server_default="low"),
        sa.Column("severity_score", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("symptoms", sa.Text()),
        sa.Column("cause", sa.Text()),
        sa.Column("treatment", sa.Text()),
        sa.Column("prevention", sa.Text()),
        sa.Column("spread_risk", sa.Text()),
        sa.Column("model", sa.Text()),
        sa.Column("created_at", TS, server_default=NOW, nullable=False),
    )
    op.create_index("idx_disease_user", "disease_reports", ["user_id", "created_at"])
    op.create_index("idx_disease_crop", "disease_reports", ["crop"])

    op.create_table(
        "profit_predictions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("farm_id", UUID, sa.ForeignKey("farms.id", ondelete="SET NULL")),
        sa.Column("crop", sa.Text(), nullable=False),
        sa.Column("farm_size_acres", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("season", sa.Text()),
        sa.Column("seed_cost", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("labor_cost", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("fertilizer_cost", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("irrigation_cost", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("transportation_cost", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("other_cost", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("total_cost", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("expected_yield_quintals", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("expected_price_per_quintal", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("expected_revenue", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("expected_profit", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("roi", sa.Numeric(8, 2), nullable=False, server_default="0"),
        sa.Column("risk_score", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("confidence_score", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("scenarios", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("model", sa.Text()),
        sa.Column("created_at", TS, server_default=NOW, nullable=False),
    )
    op.create_index("idx_profit_user", "profit_predictions", ["user_id", "created_at"])

    op.create_table(
        "market_predictions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("crop", sa.Text(), nullable=False),
        sa.Column("market", sa.Text()),
        sa.Column("current_price", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("price_unit", sa.Text(), nullable=False, server_default="INR/quintal"),
        sa.Column("trend_weekly", sa.Numeric(6, 2), nullable=False, server_default="0"),
        sa.Column("trend_monthly", sa.Numeric(6, 2), nullable=False, server_default="0"),
        sa.Column("trend_quarterly", sa.Numeric(6, 2), nullable=False, server_default="0"),
        sa.Column("demand_forecast", sa.Text()),
        sa.Column("supply_forecast", sa.Text()),
        sa.Column("price_forecast_7d", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("price_forecast_14d", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("price_forecast_30d", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("recommendation", sa.Text(), nullable=False, server_default="hold"),
        sa.Column("confidence", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("reasoning", sa.Text()),
        sa.Column("price_history", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("model", sa.Text()),
        sa.Column("created_at", TS, server_default=NOW, nullable=False),
    )
    op.create_index("idx_market_user", "market_predictions", ["user_id", "created_at"])
    op.create_index("idx_market_crop", "market_predictions", ["crop", "created_at"])

    op.create_table(
        "weather_records",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("farm_id", UUID, sa.ForeignKey("farms.id", ondelete="SET NULL")),
        sa.Column("location", sa.Text()),
        sa.Column("latitude", sa.Numeric(9, 6)),
        sa.Column("longitude", sa.Numeric(9, 6)),
        sa.Column("record_date", sa.Date(), nullable=False),
        sa.Column("temp_c", sa.Numeric(6, 2)),
        sa.Column("feels_like_c", sa.Numeric(6, 2)),
        sa.Column("humidity", sa.Numeric(6, 2)),
        sa.Column("wind_kph", sa.Numeric(6, 2)),
        sa.Column("precip_mm", sa.Numeric(8, 2)),
        sa.Column("precip_probability", sa.Numeric(5, 2)),
        sa.Column("condition", sa.Text()),
        sa.Column("alert", sa.Text()),
        sa.Column("ai_recommendation", sa.Text()),
        sa.Column("action", sa.Text()),
        sa.Column("model", sa.Text()),
        sa.Column("created_at", TS, server_default=NOW, nullable=False),
    )
    op.create_index("idx_weather_user_date", "weather_records", ["user_id", "record_date"])

    op.create_table(
        "chat_sessions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.Text(), nullable=False, server_default="New conversation"),
        sa.Column("created_at", TS, server_default=NOW, nullable=False),
        sa.Column("updated_at", TS, server_default=NOW, nullable=False),
    )
    op.create_index("idx_chat_sessions_user", "chat_sessions", ["user_id", "updated_at"])

    op.create_table(
        "chat_messages",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("session_id", UUID, sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("agent", sa.Text()),
        sa.Column("tokens", sa.Integer()),
        sa.Column("created_at", TS, server_default=NOW, nullable=False),
    )
    op.create_index("idx_chat_messages_session", "chat_messages", ["session_id", "created_at"])

    op.create_table(
        "notifications",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.Text(), nullable=False, server_default="system"),
        sa.Column("channel", sa.Text(), nullable=False, server_default="in_app"),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("link", sa.Text()),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("sent_at", TS),
        sa.Column("created_at", TS, server_default=NOW, nullable=False),
    )
    op.create_index("idx_notifications_user", "notifications", ["user_id", "created_at"])

    op.create_table(
        "activities",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.Text()),
        sa.Column("entity_id", UUID),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", TS, server_default=NOW, nullable=False),
    )
    op.create_index("idx_activities_user", "activities", ["user_id", "created_at"])

    op.create_table(
        "agent_logs",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("agent", sa.Text(), nullable=False),
        sa.Column("level", sa.Text(), nullable=False, server_default="info"),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("input", postgresql.JSONB),
        sa.Column("output", postgresql.JSONB),
        sa.Column("latency_ms", sa.Integer()),
        sa.Column("tokens", sa.Integer()),
        sa.Column("error", sa.Text()),
        sa.Column("created_at", TS, server_default=NOW, nullable=False),
    )
    op.create_index("idx_agent_logs_agent", "agent_logs", ["agent", "created_at"])
    op.create_index("idx_agent_logs_user", "agent_logs", ["user_id", "created_at"])

    op.execute("""
    create or replace function set_updated_at()
    returns trigger as $$
    begin
      new.updated_at = now();
      return new;
    end;
    $$ language plpgsql;
    """)
    for table in ("users", "farms", "chat_sessions"):
        op.execute(
            f"create trigger trg_{table}_updated_at before update on {table} "
            f"for each row execute function set_updated_at();"
        )


def downgrade() -> None:
    for table in ("chat_sessions", "farms", "users"):
        op.execute(f"drop trigger if exists trg_{table}_updated_at on {table};")
    op.execute("drop function if exists set_updated_at();")
    for table in (
        "agent_logs", "activities", "notifications", "chat_messages", "chat_sessions",
        "weather_records", "market_predictions", "profit_predictions", "disease_reports",
        "recommendations", "farms", "users",
    ):
        op.drop_table(table)
    soil_enum.drop(op.get_bind(), checkfirst=True)
    water_enum.drop(op.get_bind(), checkfirst=True)
