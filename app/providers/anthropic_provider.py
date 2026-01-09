from __future__ import annotations

from typing import List

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from app.core.config import get_settings

settings = get_settings()


class AnthropicProvider:
    def __init__(self, model: str = "claude-3-sonnet-20240229") -> None:
        self.model = model
        self.client = ChatAnthropic(model=model, api_key=settings.anthropic_api_key, timeout=15)

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
