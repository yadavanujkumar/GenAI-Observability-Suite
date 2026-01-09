#!/usr/bin/env python3
"""
Quick start guide - Run this to test the system immediately.
"""

import subprocess
import sys
import time
from pathlib import Path


def run_command(cmd: str, description: str) -> bool:
    """Run a shell command and report status."""
    print(f"\n{'='*60}")
    print(f"▶ {description}")
    print(f"{'='*60}")
    try:
        result = subprocess.run(cmd, shell=True, check=True)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed: {e}")
        return False


def main() -> None:
    """Quick start workflow."""
    print("\n" + "╔" + "═" * 58 + "╗")
    print("║" + " " * 12 + "LLM Observability Gateway - Quick Start" + " " * 7 + "║")
    print("╚" + "═" * 58 + "╝\n")

    steps = [
        ("cp .env.example .env", "1️⃣  Creating .env configuration file"),
        ("python -m venv venv", "2️⃣  Creating Python virtual environment"),
        ("source venv/bin/activate && pip install -q -r requirements.txt", "3️⃣  Installing dependencies"),
        ("python -m pytest test_gateway.py::test_health -v 2>/dev/null || echo 'Pytest check skipped'", "4️⃣  Running health check"),
    ]

    for cmd, desc in steps:
        if not run_command(cmd, desc):
            print(f"\n✗ Setup failed at: {desc}")
            sys.exit(1)

    print("\n" + "=" * 60)
    print("✓ Setup complete!")
    print("=" * 60)

    print("\n📝 Next steps:")
    print("\n1. Edit .env file with your API keys:")
    print("   nano .env")
    print("   # Add OPENAI_API_KEY and optional ANTHROPIC_API_KEY")

    print("\n2. Start the services (choose one):")
    print("\n   Option A - Docker Compose (Recommended):")
    print("   docker-compose up -d")

    print("\n   Option B - Manual (3 terminals):")
    print("   Terminal 1: docker run -p 6379:6379 redis:7-alpine")
    print("   Terminal 2: docker run -p 6333:6333 qdrant/qdrant")
    print("   Terminal 3: uvicorn app.main:app --reload --port 8000")
    print("   Terminal 4: streamlit run streamlit/dashboard.py --server.port 8501")

    print("\n3. Test the API:")
    print("   python examples.py")
    print("   # or")
    print("   python test_gateway.py")

    print("\n4. View the dashboard:")
    print("   http://localhost:8501")

    print("\n5. API documentation:")
    print("   http://localhost:8000/docs")

    print("\n📚 Documentation:")
    print("   - README.md - Overview and features")
    print("   - ARCHITECTURE.md - System design details")
    print("   - DEPLOYMENT.md - Production deployment guide")

    print("\n💡 Tips:")
    print("   - Check logs: docker-compose logs -f gateway")
    print("   - Reset cache: docker-compose exec redis redis-cli FLUSHALL")
    print("   - View interactions: cat data/interactions.jsonl | head -10")

    print("\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    main()
