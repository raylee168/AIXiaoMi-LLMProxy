"""initial llm proxy schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-07
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _id_type() -> sa.types.TypeEngine:
    return sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "llm_model_configs",
        sa.Column("id", _id_type(), primary_key=True, autoincrement=True),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("model_type", sa.String(32), nullable=False),
        sa.Column("model_name", sa.String(128), nullable=False),
        sa.Column("base_url", sa.String(512)),
        sa.Column("api_key_env_name", sa.String(128)),
        sa.Column("enabled", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("supports_json", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("charged_token_multiplier", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("min_charged_tokens", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("pricing_json", sa.JSON()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("provider", "model_type", "model_name", name="uq_llm_model"),
    )
    op.create_index("ix_llm_model_configs_provider", "llm_model_configs", ["provider"])
    op.create_index("ix_llm_model_configs_model_type", "llm_model_configs", ["model_type"])

    op.create_table(
        "llm_business_scenarios",
        sa.Column("id", _id_type(), primary_key=True, autoincrement=True),
        sa.Column("business_scenario", sa.String(96), nullable=False),
        sa.Column("purpose", sa.String(96), nullable=False),
        sa.Column("model_type", sa.String(32), nullable=False, server_default="text_llm"),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("model_name", sa.String(128), nullable=False),
        sa.Column("enabled", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("charge_policy_json", sa.JSON()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("business_scenario", "purpose", name="uq_llm_scenario_purpose"),
    )
    op.create_index("ix_llm_business_scenarios_business_scenario", "llm_business_scenarios", ["business_scenario"])
    op.create_index("ix_llm_business_scenarios_purpose", "llm_business_scenarios", ["purpose"])

    op.create_table(
        "llm_call_sessions",
        sa.Column("id", _id_type(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(128), nullable=False),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("business_scenario", sa.String(96), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("request_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("input_tokens", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("charged_tokens", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("cost_yuan", sa.Numeric(14, 6), nullable=False, server_default="0"),
        sa.Column("first_request_at", sa.DateTime()),
        sa.Column("last_request_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("session_id"),
    )
    op.create_index("ix_llm_call_sessions_session_id", "llm_call_sessions", ["session_id"])
    op.create_index("ix_llm_call_sessions_user_id", "llm_call_sessions", ["user_id"])
    op.create_index("ix_llm_call_sessions_business_scenario", "llm_call_sessions", ["business_scenario"])

    op.create_table(
        "llm_call_records",
        sa.Column("id", _id_type(), primary_key=True, autoincrement=True),
        sa.Column("call_id", sa.String(64), nullable=False),
        sa.Column("request_id", sa.String(128)),
        sa.Column("session_id", sa.String(128)),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("business_scenario", sa.String(96), nullable=False),
        sa.Column("purpose", sa.String(96), nullable=False),
        sa.Column("model_type", sa.String(32), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("model_name", sa.String(128), nullable=False),
        sa.Column("endpoint", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("input_tokens", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("image_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("charged_tokens", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("cost_yuan", sa.Numeric(14, 6), nullable=False, server_default="0"),
        sa.Column("request_json", sa.JSON()),
        sa.Column("response_json", sa.JSON()),
        sa.Column("error_json", sa.JSON()),
        sa.Column("provider_request_id", sa.String(128)),
        sa.Column("raw_response_excerpt", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("call_id"),
        sa.UniqueConstraint("request_id"),
    )
    op.create_index("ix_llm_call_records_call_id", "llm_call_records", ["call_id"])
    op.create_index("ix_llm_call_records_request_id", "llm_call_records", ["request_id"])
    op.create_index("ix_llm_call_records_session_id", "llm_call_records", ["session_id"])
    op.create_index("ix_llm_call_records_user_id", "llm_call_records", ["user_id"])
    op.create_index("ix_llm_call_records_business_scenario", "llm_call_records", ["business_scenario"])
    op.create_index("ix_llm_call_records_purpose", "llm_call_records", ["purpose"])
    op.create_index("ix_llm_call_records_status", "llm_call_records", ["status"])


def downgrade() -> None:
    op.drop_table("llm_call_records")
    op.drop_table("llm_call_sessions")
    op.drop_table("llm_business_scenarios")
    op.drop_table("llm_model_configs")
