from __future__ import annotations

from typing import List

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.core.config import get_settings

settings = get_settings()


class HallucinationChecker:
    """Lightweight self-consistency check by asking the model to critique its own answer."""

    def __init__(self, model: str | None = None) -> None:
        chosen_model = model or settings.default_primary_model
        self.client = ChatOpenAI(model=chosen_model, api_key=settings.openai_api_key, timeout=12)

    async def check(self, question: str, answer: str) -> bool:
        prompt = (
            "You are checking an assistant's answer for factuality. "
            "Given the question and answer, return YES if the answer is factual and consistent, otherwise NO. "
            "Respond with only YES or NO."
        )
        messages: List = [
            SystemMessage(content=prompt),
            HumanMessage(content=f"Question: {question}\nAnswer: {answer}"),
        ]
        try:
            resp = await self.client.ainvoke(messages)
            verdict = resp.content.strip().lower()
            return verdict.startswith("yes")
        except Exception:
            return False
