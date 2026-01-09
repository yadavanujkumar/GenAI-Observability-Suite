from __future__ import annotations

import hashlib
import json
from typing import Optional

import redis.asyncio as redis
from langchain_openai import OpenAIEmbeddings
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from app.core.config import get_settings

settings = get_settings()


class SemanticCache:
    """Hybrid semantic cache using Redis for exact lookups and Qdrant for similarity."""

    def __init__(self) -> None:
        self.redis = redis.from_url(settings.redis_url, decode_responses=True)
        self.embeddings = OpenAIEmbeddings(api_key=settings.openai_api_key) if settings.openai_api_key else None
        self.qdrant = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key) if settings.qdrant_url else None
        self.collection_name = "semantic_cache"
        if self.qdrant:
            self._init_collection()

    def _init_collection(self) -> None:
        if self.qdrant is None or self.embeddings is None:
            return
        dim = len(self.embeddings.embed_query("ping"))
        try:
            self.qdrant.get_collection(self.collection_name)
        except Exception:
            self.qdrant.recreate_collection(
                collection_name=self.collection_name,
                vectors_config=qmodels.VectorParams(size=dim, distance=qmodels.Distance.COSINE),
            )

    @staticmethod
    def _hash_prompt(prompt: str) -> str:
        return hashlib.sha256(prompt.encode("utf-8")).hexdigest()

    async def get(self, prompt: str, similarity_threshold: float = 0.90) -> Optional[dict]:
        cache_key = f"chat:{self._hash_prompt(prompt)}"
        cached = await self.redis.get(cache_key)
        if cached:
            return json.loads(cached) | {"cached": True}

        if self.qdrant and self.embeddings:
            vector = self.embeddings.embed_query(prompt)
            search = self.qdrant.search(
                collection_name=self.collection_name,
                query_vector=vector,
                limit=1,
                score_threshold=similarity_threshold,
            )
            if search:
                payload = search[0].payload or {}
                answer = payload.get("answer")
                model = payload.get("model")
                if answer and model:
                    return {"answer": answer, "model": model, "cached": True}
        return None

    async def set(self, prompt: str, answer: str, model: str) -> None:
        payload = {"answer": answer, "model": model}
        cache_key = f"chat:{self._hash_prompt(prompt)}"
        await self.redis.set(cache_key, json.dumps(payload), ex=settings.cache_ttl_seconds)

        if self.qdrant and self.embeddings:
            vector = self.embeddings.embed_query(prompt)
            self.qdrant.upsert(
                collection_name=self.collection_name,
                points=[
                    qmodels.PointStruct(
                        id=self._hash_prompt(prompt),
                        vector=vector,
                        payload={"prompt": prompt, "answer": answer, "model": model},
                    )
                ],
            )
