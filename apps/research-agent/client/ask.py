"""CLI client for the research-agent demo — ask questions about R&D data.

Usage:
    python apps/research-agent/client/ask.py "What are our active research projects?"
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

# Add project root so we can import shared contracts.
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from contracts.api import ChatRequest, Message, Role  # noqa: E402

BASE_URL = "http://127.0.0.1:8080"

SYSTEM_PROMPT = (
    "You are a research data analyst. You have access to a SQLite database at "
    "apps/research-agent/data/research.db with the following tables:\n\n"
    "- projects (id, name, status, lead, budget, start_date, description)\n"
    "- findings (id, project_id, date, summary, confidential)\n\n"
    "You can also read markdown project briefs in apps/research-agent/data/ "
    "and perform vector searches against the 'research-notes' collection.\n\n"
    "Use the sql_query tool for structured data, read_file for documents, "
    "and vector_search for semantic lookups. Write valid SQLite SQL. "
    "Return concise, helpful answers. Flag any confidential findings clearly."
)


def ask(question: str) -> None:
    """Send a question to the DomeKit runtime and print the response."""
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
        print("Make sure the server is running: domekit run apps/research-agent")
        sys.exit(1)
    except httpx.HTTPStatusError as exc:
        print(f"Error: HTTP {exc.response.status_code}")
        print(exc.response.text)
        sys.exit(1)

    data = resp.json()

    # Print the model's answer.
    answer = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    print("\n" + answer + "\n")

    # Print trace metadata when available.
    trace = data.get("trace")
    if trace:
        print("---")
        print(f"  request_id:     {trace.get('request_id', 'n/a')}")
        print(f"  tools_used:     {trace.get('tools_used', [])}")
        print(f"  tables_queried: {trace.get('tables_queried', [])}")
        print(f"  policy_mode:    {trace.get('policy_mode', 'n/a')}")
        print(f"  model:          {trace.get('model', 'n/a')}")


def main() -> None:
    if len(sys.argv) < 2:
        print('Usage: python apps/research-agent/client/ask.py "Your question here"')
        sys.exit(1)
    question = " ".join(sys.argv[1:])
    ask(question)


if __name__ == "__main__":
    main()
