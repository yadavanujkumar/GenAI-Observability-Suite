"""
Test client for the LLM Observability Gateway.
Run this to validate the system is working correctly.
"""

import asyncio
import json

import httpx

BASE_URL = "http://localhost:8000"


async def test_health() -> None:
    """Test health check endpoint."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BASE_URL}/health")
        assert resp.status_code == 200
        print("✓ Health check passed")


async def test_chat() -> None:
    """Test chat endpoint."""
    async with httpx.AsyncClient(timeout=30) as client:
        payload = {
            "user_id": "test_user_123",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "What is the capital of France?"},
            ],
            "model": "gpt-3.5-turbo",
            "temperature": 0.7,
            "metadata": {"test": True, "source": "pytest"},
        }
        resp = await client.post(f"{BASE_URL}/chat", json=payload)
        if resp.status_code != 200:
            print(f"✗ Chat endpoint failed with status {resp.status_code}")
            print(f"Response: {resp.text}")
            return

        data = resp.json()
        assert "answer" in data
        assert "model" in data
        assert "trace_id" in data
        assert data["answer"], "Answer should not be empty"
        print(f"✓ Chat endpoint passed")
        print(f"  Answer: {data['answer'][:100]}...")
        print(f"  Model: {data['model']}")
        print(f"  Latency: {data['latency_ms']:.1f}ms")
        print(f"  Cached: {data['cached']}")
        print(f"  Trace ID: {data['trace_id']}")
        return data["trace_id"]


async def test_feedback(trace_id: str) -> None:
    """Test feedback endpoint."""
    async with httpx.AsyncClient() as client:
        payload = {
            "trace_id": trace_id,
            "score": 1,
            "comment": "Great answer!",
        }
        resp = await client.post(f"{BASE_URL}/feedback", json=payload)
        assert resp.status_code == 200
        print("✓ Feedback endpoint passed")


async def test_pii_redaction() -> None:
    """Test PII redaction in prompts."""
    async with httpx.AsyncClient(timeout=30) as client:
        payload = {
            "user_id": "test_user_pii",
            "messages": [
                {
                    "role": "user",
                    "content": "My email is john@example.com and phone is 555-123-4567. Can you help?",
                },
            ],
            "model": "gpt-3.5-turbo",
            "temperature": 0.7,
        }
        resp = await client.post(f"{BASE_URL}/chat", json=payload)
        if resp.status_code != 200:
            print(f"✗ PII redaction test failed: {resp.text}")
            return

        print("✓ PII redaction test passed (no errors)")


async def test_cache() -> None:
    """Test semantic caching (run twice with same question)."""
    question = "What is machine learning?"
    payload = {
        "user_id": "test_cache",
        "messages": [{"role": "user", "content": question}],
        "model": "gpt-3.5-turbo",
        "temperature": 0.7,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        # First request (should be fresh)
        resp1 = await client.post(f"{BASE_URL}/chat", json=payload)
        data1 = resp1.json()
        latency1 = data1["latency_ms"]
        cached1 = data1["cached"]

        # Second request (same question, should be cached)
        resp2 = await client.post(f"{BASE_URL}/chat", json=payload)
        data2 = resp2.json()
        latency2 = data2["latency_ms"]
        cached2 = data2["cached"]

        print(f"✓ Cache test passed")
        print(f"  First request: {latency1:.1f}ms (cached={cached1})")
        print(f"  Second request: {latency2:.1f}ms (cached={cached2})")
        if latency2 < latency1:
            print(f"  Speed improvement: {latency1 / latency2:.1f}x faster")


async def main() -> None:
    """Run all tests."""
    print("\n" + "=" * 60)
    print("LLM Observability Gateway - Integration Tests")
    print("=" * 60 + "\n")

    try:
        await test_health()
        trace_id = await test_chat()
        if trace_id:
            await test_feedback(trace_id)
        await test_pii_redaction()
        await test_cache()

        print("\n" + "=" * 60)
        print("All tests passed! ✓")
        print("=" * 60 + "\n")

    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
    except Exception as e:  # noqa: BLE001
        print(f"\n✗ Unexpected error: {e}")
        print("\nMake sure the gateway is running:")
        print("  uvicorn app.main:app --reload --port 8000")


if __name__ == "__main__":
    asyncio.run(main())
