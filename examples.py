"""
Example client demonstrating how to use the LLM Observability Gateway.
"""

import asyncio
import json

import httpx

BASE_URL = "http://localhost:8000"


async def chat_with_feedback(user_id: str, question: str, model: str = "gpt-3.5-turbo") -> None:
    """Example: Ask a question and provide feedback."""
    print(f"\n{'='*60}")
    print(f"User: {question}")
    print(f"{'='*60}")

    async with httpx.AsyncClient(timeout=30) as client:
        # Send chat request
        payload = {
            "user_id": user_id,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful, concise assistant.",
                }
                ,
                {"role": "user", "content": question},
            ],
            "model": model,
            "temperature": 0.7,
            "metadata": {"example": True, "version": "1.0"},
        }

        print("\n[Request sent...]")
        resp = await client.post(f"{BASE_URL}/chat", json=payload)

        if resp.status_code != 200:
            print(f"Error: {resp.status_code}")
            print(resp.text)
            return

        data = resp.json()
        print(f"\nAssistant: {data['answer']}")
        print(f"\n{'─'*60}")
        print(f"📊 Metrics:")
        print(f"   Model: {data['model']}")
        print(f"   Latency: {data['latency_ms']:.1f}ms")
        print(f"   Cached: {'Yes' if data['cached'] else 'No'}")
        print(f"   Hallucination Flag: {'⚠️  Yes' if data['hallucination_flag'] else '✓ No'}")
        print(f"   Trace ID: {data['trace_id']}")

        # Send feedback
        feedback_payload = {
            "trace_id": data["trace_id"],
            "score": 1,  # 1 for thumbs up, -1 for thumbs down
            "comment": "Great response!",
        }
        feedback_resp = await client.post(f"{BASE_URL}/feedback", json=feedback_payload)
        if feedback_resp.status_code == 200:
            print(f"\n✓ Feedback recorded")


async def example_multi_turn() -> None:
    """Example: Multi-turn conversation."""
    user_id = "example_user"
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
    ]

    questions = [
        "What is Python?",
        "How is it different from Java?",
        "What are some popular Python libraries?",
    ]

    async with httpx.AsyncClient(timeout=30) as client:
        for i, question in enumerate(questions, 1):
            print(f"\n{'='*60}")
            print(f"Turn {i}: {question}")
            print(f"{'='*60}")

            messages.append({"role": "user", "content": question})

            payload = {
                "user_id": user_id,
                "messages": messages,
                "temperature": 0.7,
            }

            resp = await client.post(f"{BASE_URL}/chat", json=payload)
            data = resp.json()

            print(f"\nAssistant: {data['answer'][:200]}...")
            print(f"Latency: {data['latency_ms']:.1f}ms | Cached: {data['cached']}")

            messages.append({"role": "assistant", "content": data["answer"]})

            await asyncio.sleep(0.5)


async def example_pii_handling() -> None:
    """Example: PII is automatically redacted."""
    print(f"\n{'='*60}")
    print("PII Redaction Example")
    print(f"{'='*60}")
    print("\nOriginal prompt contains PII:")
    print("  Email: john@example.com")
    print("  Phone: 555-123-4567")

    async with httpx.AsyncClient(timeout=30) as client:
        payload = {
            "user_id": "pii_test",
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Hi, my email is john@example.com and phone is "
                        "555-123-4567. Can you help me with my account?"
                    ),
                },
            ],
        }

        resp = await client.post(f"{BASE_URL}/chat", json=payload)
        data = resp.json()
        print(f"\n✓ PII was automatically redacted before reaching the model")
        print(f"Response: {data['answer'][:150]}...")


async def main() -> None:
    """Run examples."""
    print("\n")
    print("╔" + "═" * 58 + "╗")
    print("║" + " " * 10 + "LLM Observability Gateway - Examples" + " " * 12 + "║")
    print("╚" + "═" * 58 + "╝")

    try:
        # Example 1: Simple chat with feedback
        await chat_with_feedback(
            user_id="example_user_1",
            question="Explain quantum computing in 2 sentences",
        )

        # Example 2: Multi-turn conversation
        print("\n\n[Starting multi-turn conversation example...]")
        await example_multi_turn()

        # Example 3: PII handling
        await example_pii_handling()

        print("\n\n" + "=" * 60)
        print("Examples completed!")
        print("Check the Streamlit dashboard at http://localhost:8501")
        print("=" * 60 + "\n")

    except Exception as e:  # noqa: BLE001
        print(f"\nError: {e}")
        print("\nMake sure the gateway is running:")
        print("  uvicorn app.main:app --reload --port 8000")


if __name__ == "__main__":
    asyncio.run(main())
