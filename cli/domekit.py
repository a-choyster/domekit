"""DomeKit CLI — validate manifests, run the server, and query audit logs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure project root is importable when running as script
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def cmd_validate(args: argparse.Namespace) -> None:
    """Validate a domekit.yaml manifest."""
    from runtime.manifest_loader import load_manifest

    path = args.manifest
    try:
        manifest = load_manifest(path)
    except FileNotFoundError:
        print(f"Error: manifest not found: {path}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"Error: invalid manifest: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Manifest OK: {manifest.app.name} v{manifest.app.version}")
    print(f"  Policy mode:  {manifest.runtime.policy_mode.value}")
    print(f"  Model backend: {manifest.models.backend}")
    print(f"  Default model: {manifest.models.default or '(none)'}")
    print(f"  Allowed tools: {', '.join(manifest.policy.tools.allow) or '(none)'}")
    print(f"  Audit path:   {manifest.audit.path}")

    # Validate tool references exist
    from runtime.tools.registry import create_default_registry

    registry = create_default_registry()
    available = set(registry.list_tools())
    for tool_name in manifest.policy.tools.allow:
        if tool_name not in available:
            print(f"  Warning: tool '{tool_name}' is not a known built-in tool")


def cmd_run(args: argparse.Namespace) -> None:
    """Start the DomeKit runtime server."""
    import os

    os.environ["DOMEKIT_MANIFEST"] = args.manifest

    # Validate first
    from runtime.manifest_loader import load_manifest

    try:
        manifest = load_manifest(args.manifest)
    except Exception as exc:
        print(f"Error loading manifest: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Starting DomeKit runtime for '{manifest.app.name}'...")
    print(f"  Manifest: {args.manifest}")
    print(f"  Host:     {args.host}")
    print(f"  Port:     {args.port}")
    print(f"  Policy:   {manifest.runtime.policy_mode.value}")
    print()

    import uvicorn

    uvicorn.run(
        "runtime.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


def cmd_logs(args: argparse.Namespace) -> None:
    """Query audit logs."""
    from runtime.audit.query import query_by_request, query_by_event, tail
    from contracts.audit import AuditEvent

    log_path = args.log_path

    if not Path(log_path).exists():
        print(f"No audit log found at {log_path}", file=sys.stderr)
        sys.exit(1)

    if args.request_id:
        entries = query_by_request(log_path, args.request_id)
    elif args.event:
        try:
            event = AuditEvent(args.event)
        except ValueError:
            valid = ", ".join(e.value for e in AuditEvent)
            print(f"Unknown event type: {args.event}", file=sys.stderr)
            print(f"Valid events: {valid}", file=sys.stderr)
            sys.exit(1)
        entries = query_by_event(log_path, event, limit=args.limit)
    else:
        entries = tail(log_path, n=args.limit)

    if not entries:
        print("No matching audit entries.")
        return

    for entry in entries:
        record = json.loads(entry.model_dump_json())
        if args.json:
            print(json.dumps(record))
        else:
            ts = record["ts"][:19]
            event = record["event"]
            rid = record["request_id"][:8]
            detail = json.dumps(record.get("detail", {}))
            print(f"{ts}  [{event:16s}]  {rid}  {detail}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="domekit",
        description="DomeKit — local-first AI runtime CLI",
    )
    sub = parser.add_subparsers(dest="command")

    # validate
    p_val = sub.add_parser("validate", help="Validate a domekit.yaml manifest")
    p_val.add_argument(
        "manifest", nargs="?", default="domekit.yaml", help="Path to manifest"
    )
    p_val.set_defaults(func=cmd_validate)

    # run
    p_run = sub.add_parser("run", help="Start the DomeKit runtime server")
    p_run.add_argument(
        "manifest", nargs="?", default="domekit.yaml", help="Path to manifest"
    )
    p_run.add_argument("--host", default="127.0.0.1", help="Bind address")
    p_run.add_argument("--port", type=int, default=8080, help="Port")
    p_run.add_argument("--reload", action="store_true", help="Enable auto-reload")
    p_run.set_defaults(func=cmd_run)

    # logs
    p_logs = sub.add_parser("logs", help="Query audit logs")
    p_logs.add_argument("log_path", help="Path to audit JSONL file")
    p_logs.add_argument("--request-id", "-r", help="Filter by request ID")
    p_logs.add_argument("--event", "-e", help="Filter by event type")
    p_logs.add_argument("--limit", "-n", type=int, default=20, help="Max entries")
    p_logs.add_argument("--json", action="store_true", help="Output raw JSON")
    p_logs.set_defaults(func=cmd_logs)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
