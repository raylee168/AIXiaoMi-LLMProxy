import json
import os
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import LlmBusinessScenario, LlmCallRecord, LlmCallSession, LlmModelConfig
from app.schemas import (
    BillingRequestRecord,
    ChatCompletionRequest,
    Cost,
    ErrorPayload,
    LlmResponse,
    RequestBillingResponse,
    SessionBillingResponse,
    Usage,
    VisionAnalyzeRequest,
)


@dataclass(frozen=True)
class ModelRoute:
    provider: str
    model_type: str
    model_name: str
    base_url: str | None
    api_key_env_name: str | None
    min_charged_tokens: int
    charged_token_multiplier: int


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:24]}"


def _business_scenario(payload: ChatCompletionRequest | VisionAnalyzeRequest) -> str:
    return payload.business_scenario or get_settings().default_business_scenario


def _response_request_id(payload: ChatCompletionRequest | VisionAnalyzeRequest, prefix: str) -> str:
    return payload.request_id or _id(prefix)


def _last_user_json(payload: ChatCompletionRequest) -> dict:
    for message in reversed(payload.messages):
        if message.role == "user":
            try:
                parsed = json.loads(message.content)
                return parsed if isinstance(parsed, dict) else {}
            except Exception:
                return {}
    return {}


def _default_route(payload: ChatCompletionRequest | VisionAnalyzeRequest) -> ModelRoute:
    settings = get_settings()
    if payload.provider and payload.model:
        provider = payload.provider
        model = payload.model
    elif payload.purpose == "moments_album_copywriting":
        provider = settings.moments_copywriting_provider if not settings.mock_mode else "mock"
        model = settings.moments_copywriting_model if provider == "deepseek" else settings.default_text_model
    elif payload.model_type == "image_vlm":
        provider = "mock"
        model = settings.default_vlm_model
    else:
        provider = "mock"
        model = settings.default_text_model

    if provider == "deepseek":
        return ModelRoute(
            provider="deepseek",
            model_type=payload.model_type,
            model_name=model or settings.deepseek_default_model,
            base_url=settings.deepseek_base_url,
            api_key_env_name="DEEPSEEK_API_KEY",
            min_charged_tokens=settings.charged_tokens_per_copy_request
            if payload.purpose == "moments_album_copywriting"
            else settings.charged_tokens_per_text_request,
            charged_token_multiplier=1,
        )
    min_tokens = (
        settings.charged_tokens_per_copy_request
        if payload.purpose == "moments_album_copywriting"
        else settings.charged_tokens_per_text_request
    )
    return ModelRoute(
        provider="mock",
        model_type=payload.model_type,
        model_name=model or settings.default_text_model,
        base_url=None,
        api_key_env_name=None,
        min_charged_tokens=min_tokens,
        charged_token_multiplier=1,
    )


def resolve_route(db: Session, payload: ChatCompletionRequest | VisionAnalyzeRequest) -> ModelRoute:
    scenario_name = _business_scenario(payload)
    scenario = db.scalar(
        select(LlmBusinessScenario).where(
            LlmBusinessScenario.business_scenario == scenario_name,
            LlmBusinessScenario.purpose == payload.purpose,
            LlmBusinessScenario.enabled == 1,
        )
    )
    if scenario and not payload.provider and not payload.model:
        model = db.scalar(
            select(LlmModelConfig).where(
                LlmModelConfig.provider == scenario.provider,
                LlmModelConfig.model_type == scenario.model_type,
                LlmModelConfig.model_name == scenario.model_name,
                LlmModelConfig.enabled == 1,
            )
        )
        policy = scenario.charge_policy_json or {}
        return ModelRoute(
            provider=scenario.provider,
            model_type=scenario.model_type,
            model_name=scenario.model_name,
            base_url=model.base_url if model else None,
            api_key_env_name=model.api_key_env_name if model else None,
            min_charged_tokens=int(policy.get("min_charged_tokens") or (model.min_charged_tokens if model else 0) or 0),
            charged_token_multiplier=int(
                policy.get("charged_token_multiplier") or (model.charged_token_multiplier if model else 1) or 1
            ),
        )
    route = _default_route(payload)
    model = db.scalar(
        select(LlmModelConfig).where(
            LlmModelConfig.provider == route.provider,
            LlmModelConfig.model_type == route.model_type,
            LlmModelConfig.model_name == route.model_name,
            LlmModelConfig.enabled == 1,
        )
    )
    if not model:
        return route
    return ModelRoute(
        provider=route.provider,
        model_type=route.model_type,
        model_name=route.model_name,
        base_url=model.base_url or route.base_url,
        api_key_env_name=model.api_key_env_name or route.api_key_env_name,
        min_charged_tokens=model.min_charged_tokens or route.min_charged_tokens,
        charged_token_multiplier=model.charged_token_multiplier or route.charged_token_multiplier,
    )


def _mock_decision(payload: ChatCompletionRequest, route: ModelRoute) -> LlmResponse:
    settings = get_settings()
    summary = _last_user_json(payload)
    photo_ids = summary.get("photo_ids") or []
    if not photo_ids:
        photo_ids = [f"photo_{idx:03d}" for idx in range(min(summary.get("usable_photo_count", 0), 9))]
    usable_count = int(summary.get("usable_photo_count") or summary.get("photo_count") or len(photo_ids))
    decision = "should_generate" if usable_count >= 6 else "wait_more_photos"
    input_tokens = settings.decision_input_token_cost
    output_tokens = settings.decision_output_token_cost
    return LlmResponse(
        request_id=_response_request_id(payload, "llm_req"),
        session_id=payload.session_id,
        business_scenario=_business_scenario(payload),
        provider=route.provider,
        model=route.model_name,
        model_type=route.model_type,
        purpose=payload.purpose,
        content={
            "decision": decision,
            "reason": "可用照片数量充足，适合生成朋友圈相册。" if decision == "should_generate" else "当前照片还不够，继续等待更多照片。",
            "confidence": 0.86 if decision == "should_generate" else 0.62,
            "selected_photo_ids": photo_ids[:9],
            "keep_photo_ids": photo_ids[9:],
            "reject_photo_ids": [],
            "reject_reasons": {},
            "template_matches": [{"template_id": "mvp_grid_001", "score": 0.9}],
        },
        usage=Usage(input_tokens=input_tokens, output_tokens=output_tokens, total_tokens=input_tokens + output_tokens),
        cost=Cost(cost_yuan=0.012, charged_tokens=settings.charged_tokens_per_text_request),
    )


def _mock_copywriting(payload: ChatCompletionRequest, route: ModelRoute) -> LlmResponse:
    settings = get_settings()
    input_tokens = settings.copy_input_token_cost
    output_tokens = settings.copy_output_token_cost
    return LlmResponse(
        request_id=_response_request_id(payload, "llm_req"),
        session_id=payload.session_id,
        business_scenario=_business_scenario(payload),
        provider=route.provider,
        model=route.model_name,
        model_type=route.model_type,
        purpose=payload.purpose,
        content={
            "title": "把今天装进相册里",
            "copy_options": [
                {"style": "daily", "text": "今天的照片已经替我把开心记录好了。"},
                {"style": "cultural", "text": "光影有声，日子有回响。"},
                {"style": "funny", "text": "本来只是随手一拍，结果还挺能发。"},
            ],
        },
        usage=Usage(input_tokens=input_tokens, output_tokens=output_tokens, total_tokens=input_tokens + output_tokens),
        cost=Cost(cost_yuan=0.02, charged_tokens=settings.charged_tokens_per_copy_request),
    )


def _mock_chat(payload: ChatCompletionRequest, route: ModelRoute) -> LlmResponse:
    if payload.purpose == "moments_album_decision":
        return _mock_decision(payload, route)
    if payload.purpose == "moments_album_copywriting":
        return _mock_copywriting(payload, route)
    return LlmResponse(
        request_id=_response_request_id(payload, "llm_req"),
        session_id=payload.session_id,
        business_scenario=_business_scenario(payload),
        provider=route.provider,
        model=route.model_name,
        model_type=route.model_type,
        purpose=payload.purpose,
        content={"text": ""},
        usage=Usage(),
        cost=Cost(),
    )


def _extract_json_content(text: str) -> dict:
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            parsed = json.loads(text[start : end + 1])
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    return {"text": text}


def _deepseek_cost_yuan(usage: Usage) -> float:
    settings = get_settings()
    input_cost = usage.input_tokens * settings.deepseek_cost_yuan_per_1k_input_tokens / 1000
    output_cost = usage.output_tokens * settings.deepseek_cost_yuan_per_1k_output_tokens / 1000
    return round(input_cost + output_cost, 6)


def _charged_tokens(route: ModelRoute, usage: Usage) -> int:
    return max(route.min_charged_tokens, usage.total_tokens * route.charged_token_multiplier)


def _deepseek_chat(payload: ChatCompletionRequest, route: ModelRoute) -> LlmResponse:
    settings = get_settings()
    key_name = route.api_key_env_name or "DEEPSEEK_API_KEY"
    api_key = os.getenv(key_name) or settings.deepseek_api_key
    if not api_key:
        raise RuntimeError("deepseek_api_key_missing")
    base_url = (route.base_url or settings.deepseek_base_url).rstrip("/")
    messages = [message.model_dump() for message in payload.messages]
    if not any(message.get("role") == "system" for message in messages):
        if payload.purpose == "moments_album_copywriting":
            messages.insert(
                0,
                {
                    "role": "system",
                    "content": (
                        "你是朋友圈文案助手。请只输出 JSON："
                        '{"title":"短标题","copy_options":[{"style":"daily","text":"文案"},'
                        '{"style":"cultural","text":"文案"},{"style":"funny","text":"文案"}]}。'
                        "不要输出解释。"
                    ),
                },
            )
        elif payload.purpose == "moments_album_decision":
            messages.insert(
                0,
                {
                    "role": "system",
                    "content": (
                        "你是朋友圈相册智能决策助手。请只输出 JSON，包含 decision、reason、confidence、"
                        "selected_photo_ids、keep_photo_ids、reject_photo_ids、reject_reasons、template_matches。"
                    ),
                },
            )
    request_json: dict = {
        "model": route.model_name,
        "messages": messages,
        "stream": False,
    }
    if payload.response_format == "json":
        request_json["response_format"] = {"type": "json_object"}
    with httpx.Client(timeout=settings.request_timeout_seconds) as client:
        response = client.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=request_json,
        )
        response.raise_for_status()
        data = response.json()
    usage_data = data.get("usage") or {}
    usage = Usage(
        input_tokens=int(usage_data.get("prompt_tokens") or usage_data.get("input_tokens") or 0),
        output_tokens=int(usage_data.get("completion_tokens") or usage_data.get("output_tokens") or 0),
        total_tokens=int(usage_data.get("total_tokens") or 0),
    )
    if not usage.total_tokens:
        usage.total_tokens = usage.input_tokens + usage.output_tokens
    message = ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    content = _extract_json_content(message)
    if payload.purpose == "moments_album_copywriting":
        options = content.get("copy_options") if isinstance(content, dict) else None
        if not content.get("title") or not isinstance(options, list) or not options:
            text = content.get("text") if isinstance(content, dict) else ""
            content = {
                "title": "把今天装进相册里",
                "copy_options": [
                    {"style": "daily", "text": text or "今天的照片已经替我把开心记录好了。"},
                    {"style": "cultural", "text": "光影有声，日子有回响。"},
                    {"style": "funny", "text": "本来只是随手一拍，结果还挺能发。"},
                ],
            }
    return LlmResponse(
        request_id=_response_request_id(payload, "llm_req"),
        session_id=payload.session_id,
        business_scenario=_business_scenario(payload),
        provider=route.provider,
        model=route.model_name,
        model_type=route.model_type,
        purpose=payload.purpose,
        content=content,
        usage=usage,
        cost=Cost(cost_yuan=_deepseek_cost_yuan(usage), charged_tokens=_charged_tokens(route, usage)),
    )


def _mock_vision(payload: VisionAnalyzeRequest, route: ModelRoute) -> LlmResponse:
    settings = get_settings()
    image_count = len(payload.images)
    keep_ids = [image.photo_id for image in payload.images]
    input_tokens = image_count * settings.charged_tokens_per_vlm_image
    output_tokens = 400 if image_count else 0
    return LlmResponse(
        request_id=_response_request_id(payload, "vlm_req"),
        session_id=payload.session_id,
        business_scenario=_business_scenario(payload),
        provider=route.provider,
        model=route.model_name,
        model_type=route.model_type,
        purpose=payload.purpose,
        content={
            "scene": "daily_life",
            "mood": "happy",
            "atmosphere": "画面明亮、日常轻松，适合生成朋友圈内容。",
            "suggested_main_photo_id": keep_ids[0] if keep_ids else None,
            "keep_photo_ids": keep_ids,
            "reject_photo_ids": [],
            "reject_reasons": {},
            "confidence": 0.82,
        },
        usage=Usage(input_tokens=input_tokens, output_tokens=output_tokens, total_tokens=input_tokens + output_tokens, image_count=image_count),
        cost=Cost(cost_yuan=round(image_count * 0.02, 4), charged_tokens=input_tokens),
    )


def _record_to_response(record: LlmCallRecord, cached: bool = False) -> LlmResponse:
    data = record.response_json or {}
    response = LlmResponse.model_validate(data)
    response.cached = cached
    return response


def _record_to_request_billing(record: LlmCallRecord) -> RequestBillingResponse:
    return RequestBillingResponse(
        request_id=record.request_id,
        call_id=record.call_id,
        session_id=record.session_id,
        user_id=record.user_id,
        business_scenario=record.business_scenario,
        purpose=record.purpose,
        provider=record.provider,
        model=record.model_name,
        status=record.status,
        usage=Usage(
            input_tokens=record.input_tokens,
            output_tokens=record.output_tokens,
            total_tokens=record.total_tokens,
            image_count=record.image_count or None,
        ),
        cost=Cost(cost_yuan=float(record.cost_yuan or 0), charged_tokens=record.charged_tokens),
        response=record.response_json,
        error=record.error_json,
    )


def _save_record(
    db: Session,
    payload: ChatCompletionRequest | VisionAnalyzeRequest,
    route: ModelRoute,
    endpoint: str,
    response: LlmResponse,
    error: ErrorPayload | None = None,
) -> None:
    now = datetime.utcnow()
    usage = response.usage or Usage()
    cost = response.cost or Cost()
    record = LlmCallRecord(
        call_id=_id("call"),
        request_id=response.request_id,
        session_id=payload.session_id,
        user_id=payload.user_id,
        business_scenario=_business_scenario(payload),
        purpose=payload.purpose,
        model_type=payload.model_type,
            provider=response.provider or route.provider,
            model_name=response.model or route.model_name,
        endpoint=endpoint,
        status="failed" if error else "success",
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        total_tokens=usage.total_tokens,
        image_count=usage.image_count or 0,
        charged_tokens=cost.charged_tokens,
        cost_yuan=Decimal(str(cost.cost_yuan)),
        request_json=payload.model_dump(mode="json"),
        response_json=response.model_dump(mode="json"),
        error_json=error.model_dump(mode="json") if error else None,
    )
    db.add(record)
    if payload.session_id:
        session = db.scalar(select(LlmCallSession).where(LlmCallSession.session_id == payload.session_id))
        if not session:
            session = LlmCallSession(
                session_id=payload.session_id,
                user_id=payload.user_id,
                business_scenario=_business_scenario(payload),
                first_request_at=now,
            )
            db.add(session)
        session.request_count = (session.request_count or 0) + 1
        if error:
            session.failed_count = (session.failed_count or 0) + 1
        else:
            session.success_count = (session.success_count or 0) + 1
        session.input_tokens = (session.input_tokens or 0) + usage.input_tokens
        session.output_tokens = (session.output_tokens or 0) + usage.output_tokens
        session.total_tokens = (session.total_tokens or 0) + usage.total_tokens
        session.charged_tokens = (session.charged_tokens or 0) + cost.charged_tokens
        session.cost_yuan = Decimal(str(session.cost_yuan or 0)) + Decimal(str(cost.cost_yuan))
        session.last_request_at = now
    db.commit()


def _cached_response(db: Session, request_id: str | None) -> LlmResponse | None:
    if not request_id:
        return None
    record = db.scalar(select(LlmCallRecord).where(LlmCallRecord.request_id == request_id))
    if not record or not record.response_json:
        return None
    return _record_to_response(record, cached=True)


def chat_completion(db: Session, payload: ChatCompletionRequest) -> LlmResponse:
    cached = _cached_response(db, payload.request_id)
    if cached:
        return cached
    route = resolve_route(db, payload)
    try:
        if get_settings().mock_mode or route.provider == "mock":
            response = _mock_chat(payload, route)
        elif route.provider == "deepseek":
            response = _deepseek_chat(payload, route)
        else:
            raise RuntimeError(f"unsupported_provider:{route.provider}")
    except Exception as exc:
        if not get_settings().fallback_to_mock_on_provider_error:
            error = ErrorPayload(code="provider_call_failed", message=str(exc), retryable=True)
            response = LlmResponse(
                request_id=_response_request_id(payload, "llm_req"),
                session_id=payload.session_id,
                business_scenario=_business_scenario(payload),
                provider=route.provider,
                model=route.model_name,
                model_type=route.model_type,
                purpose=payload.purpose,
                usage=Usage(),
                cost=Cost(),
                error=error,
            )
            _save_record(db, payload, route, "/v1/chat/completions", response, error)
            return response
        fallback_route = ModelRoute(
            provider="mock-fallback",
            model_type=payload.model_type,
            model_name=get_settings().default_text_model,
            base_url=None,
            api_key_env_name=None,
            min_charged_tokens=route.min_charged_tokens,
            charged_token_multiplier=route.charged_token_multiplier,
        )
        response = _mock_chat(payload, fallback_route)
    _save_record(db, payload, route, "/v1/chat/completions", response)
    return response


def vision_analyze(db: Session, payload: VisionAnalyzeRequest) -> LlmResponse:
    cached = _cached_response(db, payload.request_id)
    if cached:
        return cached
    route = resolve_route(db, payload)
    response = _mock_vision(payload, route)
    _save_record(db, payload, route, "/v1/vision/analyze", response)
    return response


def get_session_billing(db: Session, session_id: str) -> SessionBillingResponse | None:
    session = db.scalar(select(LlmCallSession).where(LlmCallSession.session_id == session_id))
    if not session:
        return None
    records = list(
        db.scalars(select(LlmCallRecord).where(LlmCallRecord.session_id == session_id).order_by(LlmCallRecord.created_at))
    )
    return SessionBillingResponse(
        session_id=session.session_id,
        user_id=session.user_id,
        business_scenario=session.business_scenario,
        status=session.status,
        request_count=session.request_count,
        success_count=session.success_count,
        failed_count=session.failed_count,
        usage=Usage(
            input_tokens=session.input_tokens,
            output_tokens=session.output_tokens,
            total_tokens=session.total_tokens,
        ),
        cost=Cost(cost_yuan=float(session.cost_yuan or 0), charged_tokens=session.charged_tokens),
        records=[
            BillingRequestRecord(
                request_id=record.request_id,
                call_id=record.call_id,
                purpose=record.purpose,
                provider=record.provider,
                model=record.model_name,
                status=record.status,
                usage=Usage(
                    input_tokens=record.input_tokens,
                    output_tokens=record.output_tokens,
                    total_tokens=record.total_tokens,
                    image_count=record.image_count or None,
                ),
                cost=Cost(cost_yuan=float(record.cost_yuan or 0), charged_tokens=record.charged_tokens),
            )
            for record in records
        ],
    )


def get_request_billing(db: Session, request_id: str) -> RequestBillingResponse | None:
    record = db.scalar(select(LlmCallRecord).where(LlmCallRecord.request_id == request_id))
    if not record:
        return None
    return _record_to_request_billing(record)


def list_routes(db: Session) -> dict:
    models = list(db.scalars(select(LlmModelConfig).order_by(LlmModelConfig.provider, LlmModelConfig.model_name)))
    scenarios = list(
        db.scalars(select(LlmBusinessScenario).order_by(LlmBusinessScenario.business_scenario, LlmBusinessScenario.purpose))
    )
    return {
        "defaults": {
            "mock_mode": get_settings().mock_mode,
            "moments_copywriting_provider": get_settings().moments_copywriting_provider,
            "moments_copywriting_model": get_settings().moments_copywriting_model,
            "deepseek_base_url": get_settings().deepseek_base_url,
        },
        "models": [
            {
                "provider": item.provider,
                "model_type": item.model_type,
                "model_name": item.model_name,
                "base_url": item.base_url,
                "api_key_env_name": item.api_key_env_name,
                "enabled": bool(item.enabled),
                "min_charged_tokens": item.min_charged_tokens,
                "charged_token_multiplier": item.charged_token_multiplier,
            }
            for item in models
        ],
        "business_scenarios": [
            {
                "business_scenario": item.business_scenario,
                "purpose": item.purpose,
                "model_type": item.model_type,
                "provider": item.provider,
                "model_name": item.model_name,
                "enabled": bool(item.enabled),
                "charge_policy": item.charge_policy_json or {},
            }
            for item in scenarios
        ],
    }
