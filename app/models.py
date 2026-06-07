from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

IdType = BigInteger().with_variant(Integer, "sqlite")


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class LlmModelConfig(Base, TimestampMixin):
    __tablename__ = "llm_model_configs"
    __table_args__ = (UniqueConstraint("provider", "model_type", "model_name", name="uq_llm_model"),)

    id: Mapped[int] = mapped_column(IdType, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    model_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    base_url: Mapped[str | None] = mapped_column(String(512))
    api_key_env_name: Mapped[str | None] = mapped_column(String(128))
    enabled: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    supports_json: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    charged_token_multiplier: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    min_charged_tokens: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    pricing_json: Mapped[dict | None] = mapped_column(JSON)


class LlmBusinessScenario(Base, TimestampMixin):
    __tablename__ = "llm_business_scenarios"
    __table_args__ = (UniqueConstraint("business_scenario", "purpose", name="uq_llm_scenario_purpose"),)

    id: Mapped[int] = mapped_column(IdType, primary_key=True, autoincrement=True)
    business_scenario: Mapped[str] = mapped_column(String(96), index=True, nullable=False)
    purpose: Mapped[str] = mapped_column(String(96), index=True, nullable=False)
    model_type: Mapped[str] = mapped_column(String(32), default="text_llm", nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    enabled: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    charge_policy_json: Mapped[dict | None] = mapped_column(JSON)


class LlmCallSession(Base, TimestampMixin):
    __tablename__ = "llm_call_sessions"

    id: Mapped[int] = mapped_column(IdType, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    business_scenario: Mapped[str] = mapped_column(String(96), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    request_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    success_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    input_tokens: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    charged_tokens: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    cost_yuan: Mapped[float] = mapped_column(Numeric(14, 6), default=0, nullable=False)
    first_request_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_request_at: Mapped[datetime | None] = mapped_column(DateTime)


class LlmCallRecord(Base, TimestampMixin):
    __tablename__ = "llm_call_records"

    id: Mapped[int] = mapped_column(IdType, primary_key=True, autoincrement=True)
    call_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    request_id: Mapped[str | None] = mapped_column(String(128), unique=True, index=True)
    session_id: Mapped[str | None] = mapped_column(String(128), index=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    business_scenario: Mapped[str] = mapped_column(String(96), index=True, nullable=False)
    purpose: Mapped[str] = mapped_column(String(96), index=True, nullable=False)
    model_type: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    input_tokens: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    image_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    charged_tokens: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    cost_yuan: Mapped[float] = mapped_column(Numeric(14, 6), default=0, nullable=False)
    request_json: Mapped[dict | None] = mapped_column(JSON)
    response_json: Mapped[dict | None] = mapped_column(JSON)
    error_json: Mapped[dict | None] = mapped_column(JSON)
    provider_request_id: Mapped[str | None] = mapped_column(String(128))
    raw_response_excerpt: Mapped[str | None] = mapped_column(Text)
