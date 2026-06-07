from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas import (
    ChatCompletionRequest,
    LlmResponse,
    RequestBillingResponse,
    SessionBillingResponse,
    VisionAnalyzeRequest,
)
from app.services import chat_completion, get_request_billing, get_session_billing, list_routes, vision_analyze

app = FastAPI(title="AIXiaoMi LLM Proxy", version="0.2.0")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "aixiaomi-llm-proxy"}


@app.post("/v1/chat/completions", response_model=LlmResponse)
def post_chat_completions(payload: ChatCompletionRequest, db: Session = Depends(get_db)) -> LlmResponse:
    return chat_completion(db, payload)


@app.post("/v1/vision/analyze", response_model=LlmResponse)
def post_vision_analyze(payload: VisionAnalyzeRequest, db: Session = Depends(get_db)) -> LlmResponse:
    return vision_analyze(db, payload)


@app.get("/v1/billing/sessions/{session_id}", response_model=SessionBillingResponse)
def read_session_billing(session_id: str, db: Session = Depends(get_db)) -> SessionBillingResponse:
    payload = get_session_billing(db, session_id)
    if not payload:
        raise HTTPException(status_code=404, detail="session_not_found")
    return payload


@app.get("/v1/billing/requests/{request_id}", response_model=RequestBillingResponse)
def read_request_billing(request_id: str, db: Session = Depends(get_db)) -> RequestBillingResponse:
    payload = get_request_billing(db, request_id)
    if not payload:
        raise HTTPException(status_code=404, detail="request_not_found")
    return payload


@app.get("/v1/routes")
def read_routes(db: Session = Depends(get_db)) -> dict:
    return list_routes(db)
