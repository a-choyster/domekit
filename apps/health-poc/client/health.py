"""CLI client for the DomeKit health PoC — asks questions about health data."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

# Add project root to path so we can import contracts
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from contracts.api import ChatRequest, Message, Role  # noqa: E402

BASE_URL = "http://127.0.0.1:8080"

SYSTEM_PROMPT = (
    "You are a health data assistant. Use the sql_query tool to answer "
    "questions about the user's health data. The SQLite database is at "
    "apps/health-poc/data/health.db with the following tables:\n\n"
    "- activities (id, date, type, duration_min, distance_km, avg_hr, calories)\n"
    "- daily_metrics (id, date, steps, resting_hr, sleep_hours, active_minutes, stress_score)\n\n"
    "Always write valid SQL for SQLite. Return concise, helpful answers."
)


def ask(question: str) -> None:
    """Send a question to the DomeKit runtime and display the response."""
    request = ChatRequest(
        model="default",
        messages=[
            Message(role=Role.SYSTEM, content=SYSTEM_PROMPT),
            Message(role=Role.USER, content=question),
        ],
    )

    try:
        resp = httpx.post(
            f"{BASE_URL}/v1/chat/completions",
            json=json.loads(request.model_dump_json()),
            timeout=60.0,
        )
        resp.raise_for_status()
    except httpx.ConnectError:
        print("Error: Cannot connect to DomeKit runtime at", BASE_URL)
        print("Make sure the server is running: python -m runtime.app")
        sys.exit(1)
    except httpx.HTTPStatusError as exc:
        print(f"Error: HTTP {exc.response.status_code}")
        print(exc.response.text)
        sys.exit(1)

    data = resp.json()

    # Print the model's answer
    answer = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    print("\n" + answer + "\n")

    # Print trace metadata if present
    trace = data.get("trace")
    if trace:
        print("---")
        print(f"  request_id:     {trace.get('request_id', 'n/a')}")
        print(f"  tools_used:     {trace.get('tools_used', [])}")
        print(f"  tables_queried: {trace.get('tables_queried', [])}")
        print(f"  policy_mode:    {trace.get('policy_mode', 'n/a')}")
        print(f"  model:          {trace.get('model', 'n/a')}")


def main() -> None:
    if len(sys.argv) < 3 or sys.argv[1] != "ask":
        print("Usage: python apps/health-poc/client/health.py ask \"<question>\"")
        sys.exit(1)
    question = " ".join(sys.argv[2:])
    ask(question)


if __name__ == "__main__":
    main()
