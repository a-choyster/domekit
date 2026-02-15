"""DomeKit FastAPI runtime server (Phase 0)."""

from __future__ import annotations

import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from contracts.api import ChatRequest, ChatResponse
from contracts.audit import AuditEntry, AuditEvent

from runtime.audit.logger import JsonlAuditLogger
from runtime.audit.query import query_filtered, stream_tail, _read_all
from runtime.manifest_loader import load_manifest
from runtime.metrics import compute_metrics
from runtime.model_adapters.ollama import OllamaAdapter
from runtime.policy import DomeKitPolicyEngine
from runtime.security import detect_alerts
from runtime.tool_router import ToolRouter
from runtime.tools.registry import create_default_registry

# ── Module-level state (set during lifespan) ─────────────────────────

_router: ToolRouter | None = None
_logger: JsonlAuditLogger | None = None
_manifest: Any = None
_start_time: float = 0.0


def _create_embedding_adapter(manifest: Any) -> Any:
    """Create an embedding adapter from manifest config."""
    backend = manifest.embedding.backend
    if backend == "ollama":
        from runtime.embedding_adapters.ollama import OllamaEmbeddingAdapter
        return OllamaEmbeddingAdapter(model=manifest.embedding.model)
    return None


def _create_vector_adapter(manifest: Any) -> Any:
    """Create a vector DB adapter from manifest config."""
    backend = manifest.vector_db.backend
    if backend == "chroma":
        try:
            from runtime.vector_adapters.chroma import ChromaVectorAdapter
            return ChromaVectorAdapter(persist_path=".domekit/vector_db")
        except ImportError:
            return None
    if backend == "lance":
        try:
            from runtime.vector_adapters.lance import LanceVectorAdapter
            return LanceVectorAdapter(db_path=".domekit/vector_db")
        except ImportError:
            return None
    return None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialise all components on startup."""
    global _router, _logger, _manifest, _start_time  # noqa: PLW0603

    _start_time = time.time()

    manifest_path = os.environ.get("DOMEKIT_MANIFEST", "./domekit.yaml")
    _manifest = load_manifest(manifest_path)

    policy = DomeKitPolicyEngine()
    policy.load_manifest(_manifest)

    embedding_adapter = _create_embedding_adapter(_manifest)
    vector_adapter = _create_vector_adapter(_manifest)

    registry = create_default_registry(
        embedding_adapter=embedding_adapter,
        vector_adapter=vector_adapter,
    )

    _logger = JsonlAuditLogger(_manifest.audit.path)

    adapter = OllamaAdapter(base_url="http://localhost:11434")

    _router = ToolRouter(
        policy=policy,
        registry=registry,
        logger=_logger,
        adapter=adapter,
    )

    yield


app = FastAPI(title="DomeKit Runtime", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Endpoints ────────────────────────────────────────────────────────


@app.get("/v1/domekit/health")
async def health() -> dict[str, Any]:
    """Extended health-check endpoint."""
    result: dict[str, Any] = {"status": "ok", "version": "0.1.0"}

    # Uptime
    result["uptime_seconds"] = round(time.time() - _start_time, 1) if _start_time else 0

    # Manifest summary
    if _manifest:
        result["manifest"] = {
            "app": _manifest.app.name,
            "app_version": _manifest.app.version,
            "policy_mode": _manifest.runtime.policy_mode.value,
            "allowed_tools": _manifest.policy.tools.allow,
            "model_backend": _manifest.models.backend,
            "default_model": _manifest.models.default,
        }

    # Audit log size
    if _manifest:
        log_path = Path(_manifest.audit.path)
        if log_path.exists():
            result["audit_log_size_bytes"] = log_path.stat().st_size
            result["audit_log_entries"] = len(_read_all(log_path))

    # Ollama status
    ollama_status: dict[str, Any] = {"reachable": False, "models": []}
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get("http://localhost:11434/api/tags")
            if resp.status_code == 200:
                ollama_status["reachable"] = True
                data = resp.json()
                ollama_status["models"] = [
                    m.get("name", "") for m in data.get("models", [])
                ]
    except Exception:
        pass
    result["ollama"] = ollama_status

    return result


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatRequest) -> ChatResponse:
    """OpenAI-compatible chat completions."""
    if _router is None or _manifest is None:
        raise HTTPException(status_code=503, detail="Runtime not initialised")
    return await _router.run(request, _manifest)


@app.get("/v1/domekit/audit/logs")
async def audit_logs(
    event: AuditEvent | None = Query(None),
    since: datetime | None = Query(None),
    until: datetime | None = Query(None),
    request_id: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """Filtered, paginated audit log query."""
    if _manifest is None:
        raise HTTPException(status_code=503, detail="Runtime not initialised")

    entries, total = query_filtered(
        _manifest.audit.path,
        event=event,
        since=since,
        until=until,
        request_id=request_id,
        limit=limit,
        offset=offset,
    )
    return {"entries": [e.model_dump(mode="json") for e in entries], "total": total}


@app.get("/v1/domekit/audit/stream")
async def audit_stream():
    """SSE endpoint for real-time log tailing."""
    if _manifest is None:
        raise HTTPException(status_code=503, detail="Runtime not initialised")

    async def event_generator():
        async for entry in stream_tail(_manifest.audit.path):
            data = entry.model_dump_json()
            yield f"data: {data}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/v1/domekit/audit/{request_id}")
async def audit_query(request_id: str) -> list[AuditEntry]:
    """Return audit entries for a given request_id."""
    if _logger is None:
        raise HTTPException(status_code=503, detail="Runtime not initialised")
    return _logger.query_by_request(request_id)


@app.get("/v1/domekit/security/alerts")
async def security_alerts(
    since: datetime | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
) -> dict[str, Any]:
    """Data leakage / threat alerts from heuristic analysis."""
    if _manifest is None:
        raise HTTPException(status_code=503, detail="Runtime not initialised")

    alerts = detect_alerts(_manifest.audit.path, since=since, limit=limit)
    return {"alerts": alerts, "total": len(alerts)}


@app.get("/v1/domekit/metrics")
async def metrics(
    since: datetime | None = Query(None),
    window: int = Query(60, ge=1, le=3600, description="Bucket window in seconds"),
) -> dict[str, Any]:
    """Aggregated observability metrics."""
    if _manifest is None:
        raise HTTPException(status_code=503, detail="Runtime not initialised")

    return compute_metrics(_manifest.audit.path, since=since, window_seconds=window)


# ── Static dashboard mount (must be last to avoid catching API routes) ──

_dashboard_dir = Path(__file__).resolve().parent.parent / "dashboard"
if _dashboard_dir.is_dir():
    app.mount("/dashboard", StaticFiles(directory=str(_dashboard_dir), html=True), name="dashboard")
