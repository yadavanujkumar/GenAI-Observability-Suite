from __future__ import annotations

import time
from typing import List

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Settings, get_settings
from app.providers.anthropic_provider import AnthropicProvider
from app.providers.openai_provider import OpenAIProvider
from app.schemas.chat import ChatRequest, ChatResponse, FeedbackRequest
from app.services.fallback_manager import FallbackManager
from app.services.hallucination_checker import HallucinationChecker
from app.services.observability_logger import ObservabilityLogger
from app.services.pii_redaction import PiiRedactor
from app.services.semantic_cache import SemanticCache

app = FastAPI(title="LLM Observability & Governance Gateway", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def get_cache() -> SemanticCache:
    return SemanticCache()


async def get_redactor() -> PiiRedactor:
    return PiiRedactor()


async def get_logger() -> ObservabilityLogger:
    return ObservabilityLogger()


async def get_hallucination_checker(settings: Settings = Depends(get_settings)) -> HallucinationChecker:
    return HallucinationChecker(model=settings.default_primary_model)


async def build_fallback_manager(settings: Settings = Depends(get_settings)) -> FallbackManager:
    providers: List[tuple[str, callable]] = []
    if settings.openai_api_key:
        providers.append((settings.default_primary_model, OpenAIProvider(settings.default_primary_model).generate))
        for model in settings.default_fallback_models:
            providers.append((model, OpenAIProvider(model).generate))
    if settings.anthropic_api_key:
        providers.append(("anthropic", AnthropicProvider().generate))
    if not providers:
        raise HTTPException(status_code=500, detail="No providers configured")
    return FallbackManager(providers)


@app.get("/health")
async def healthcheck() -> dict:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    cache: SemanticCache = Depends(get_cache),
    redactor: PiiRedactor = Depends(get_redactor),
    logger: ObservabilityLogger = Depends(get_logger),
    fallback: FallbackManager = Depends(build_fallback_manager),
    checker: HallucinationChecker = Depends(get_hallucination_checker),
    settings: Settings = Depends(get_settings),
) -> ChatResponse:
    start = time.monotonic()
    last_user_message = next((m.content for m in reversed(payload.messages) if m.role == "user"), "")
    redacted_prompt, _ = redactor.redact(last_user_message)

    cached = await cache.get(redacted_prompt)
    if cached:
        latency = (time.monotonic() - start) * 1000
        trace_id = logger.log_interaction(
            user_id=payload.user_id,
            prompt=redacted_prompt,
            response=cached["answer"],
            model=cached["model"],
            latency_ms=latency,
            cached=True,
            hallucination_ok=True,
            metadata=payload.metadata,
        )
        return ChatResponse(
            answer=cached["answer"],
            model=cached["model"],
            latency_ms=latency,
            cached=True,
            hallucination_flag=False,
            trace_id=trace_id,
        )

    try:
        answer, model_used = await fallback.generate(
            messages=[{"role": m.role, "content": m.content} for m in payload.messages],
            temperature=payload.temperature,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"All providers failed: {exc}") from exc

    ok = await checker.check(question=redacted_prompt, answer=answer)

    latency = (time.monotonic() - start) * 1000
    await cache.set(redacted_prompt, answer, model_used)
    trace_id = logger.log_interaction(
        user_id=payload.user_id,
        prompt=redacted_prompt,
        response=answer,
        model=model_used,
        latency_ms=latency,
        cached=False,
        hallucination_ok=ok,
        metadata=payload.metadata,
    )

    return ChatResponse(
        answer=answer,
        model=model_used,
        latency_ms=latency,
        cached=False,
        hallucination_flag=not ok,
        trace_id=trace_id,
    )


@app.post("/feedback")
async def feedback(payload: FeedbackRequest, logger: ObservabilityLogger = Depends(get_logger)) -> dict:
    logger.log_feedback(trace_id=payload.trace_id, score=payload.score, comment=payload.comment)
    return {"status": "recorded"}
