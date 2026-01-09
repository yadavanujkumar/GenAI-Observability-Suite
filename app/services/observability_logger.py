from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from langfuse import Langfuse

from app.core.config import get_settings

settings = get_settings()


class ObservabilityLogger:
    def __init__(self) -> None:
        self.log_path = Path(settings.log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.langfuse = (
            Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.langfuse_host,
            )
            if settings.langfuse_public_key and settings.langfuse_secret_key
            else None
        )

    def _write_local(self, record: Dict[str, Any]) -> None:
        with self.log_path.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(record) + "\n")

    def log_interaction(
        self,
        user_id: str,
        prompt: str,
        response: str,
        model: str,
        latency_ms: float,
        cached: bool,
        hallucination_ok: bool,
        metadata: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
    ) -> str:
        trace = trace_id or str(uuid.uuid4())
        record = {
            "trace_id": trace,
            "user_id": user_id,
            "prompt": prompt,
            "response": response,
            "model": model,
            "latency_ms": latency_ms,
            "cached": cached,
            "hallucination_ok": hallucination_ok,
            "metadata": metadata or {},
            "ts": time.time(),
        }
        self._write_local(record)

        if self.langfuse:
            lf_trace = self.langfuse.trace(
                name="chat-interaction",
                trace_id=trace,
                user_id=user_id,
                metadata=record,
            )
            lf_trace.span(name="llm-response", input=prompt, output=response, model=model, latency_ms=latency_ms)
            lf_trace.flush()

        return trace

    def log_feedback(self, trace_id: str, score: int, comment: Optional[str]) -> None:
        record = {"trace_id": trace_id, "feedback": score, "comment": comment, "ts": time.time()}
        self._write_local(record)

        if self.langfuse:
            self.langfuse.score(trace_id=trace_id, name="user_feedback", value=score, comment=comment)
