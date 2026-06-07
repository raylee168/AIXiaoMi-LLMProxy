from typing import Any

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str
    content: str


class BaseLlmRequest(BaseModel):
    model_type: str
    purpose: str
    user_id: str
    business_scenario: str | None = None
    session_id: str | None = None
    request_id: str | None = None
    model: str | None = None
    provider: str | None = None
    response_format: str = "json"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatCompletionRequest(BaseLlmRequest):
    model_type: str = "text_llm"
    messages: list[ChatMessage]


class Usage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    image_count: int | None = None


class Cost(BaseModel):
    cost_yuan: float = 0
    charged_tokens: int = 0


class ErrorPayload(BaseModel):
    code: str
    message: str
    retryable: bool = False


class LlmResponse(BaseModel):
    request_id: str
    session_id: str | None = None
    business_scenario: str | None = None
    provider: str | None = None
    model: str | None = None
    model_type: str | None = None
    purpose: str | None = None
    content: dict[str, Any] | None = None
    usage: Usage | None = None
    cost: Cost | None = None
    error: ErrorPayload | None = None
    cached: bool = False


class VisionImage(BaseModel):
    photo_id: str
    image_path: str


class VisionAnalyzeRequest(BaseLlmRequest):
    model_type: str = "image_vlm"
    purpose: str = "moments_album_image_review"
    summary: dict[str, Any] | str
    images: list[VisionImage] = Field(default_factory=list)


class BillingRequestRecord(BaseModel):
    request_id: str | None
    call_id: str
    purpose: str
    provider: str
    model: str
    status: str
    usage: Usage
    cost: Cost


class SessionBillingResponse(BaseModel):
    session_id: str
    user_id: str
    business_scenario: str
    status: str
    request_count: int
    success_count: int
    failed_count: int
    usage: Usage
    cost: Cost
    records: list[BillingRequestRecord] = Field(default_factory=list)


class RequestBillingResponse(BaseModel):
    request_id: str | None
    call_id: str
    session_id: str | None
    user_id: str
    business_scenario: str
    purpose: str
    provider: str
    model: str
    status: str
    usage: Usage
    cost: Cost
    response: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
