from __future__ import annotations

from typing import List

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.core.config import get_settings

settings = get_settings()


class OpenAIProvider:
    def __init__(self, model: str) -> None:
        self.model = model
        self.client = ChatOpenAI(model=model, api_key=settings.openai_api_key, timeout=15)

    async def generate(self, messages: List[dict], temperature: float) -> str:
        lc_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg["content"]
            if role == "system":
                lc_messages.append(SystemMessage(content=content))
            else:
                lc_messages.append(HumanMessage(content=content))
        response = await self.client.ainvoke(lc_messages, temperature=temperature)
        return response.content
