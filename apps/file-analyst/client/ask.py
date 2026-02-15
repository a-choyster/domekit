#!/usr/bin/env python3
"""Simple client for the file-analyst demo.

Sends a question to the DomeKit runtime via its OpenAI-compatible API
and prints the response.

Usage:
    python apps/file-analyst/client/ask.py "Summarize the Q4 report"
    python apps/file-analyst/client/ask.py "What security issues were found?"
"""

import sys
import json
import urllib.request
import urllib.error

DOMEKIT_URL = "http://localhost:8080/v1/chat/completions"
MODEL = "llama3.1:8b"

SYSTEM_PROMPT = (
    "You are a file analyst agent. You can search for files using the sql_query tool "
    "against the index database, and read file contents using the read_file tool. "
    "Files are located in the apps/file-analyst/data/reports/ directory. "
    "Answer questions based on the contents of the available reports."
)


def ask(question: str) -> None:
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        DOMEKIT_URL,
        data=data,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            message = body["choices"][0]["message"]["content"]
            print(message)
    except urllib.error.URLError as exc:
        print(f"Error connecting to DomeKit at {DOMEKIT_URL}", file=sys.stderr)
        print(f"Is the runtime running? (domekit run --app apps/file-analyst)", file=sys.stderr)
        print(f"Details: {exc}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python apps/file-analyst/client/ask.py \"<question>\"", file=sys.stderr)
        print("Example: python apps/file-analyst/client/ask.py \"Summarize the Q4 report\"", file=sys.stderr)
        sys.exit(1)

    question = " ".join(sys.argv[1:])
    ask(question)


if __name__ == "__main__":
    main()
