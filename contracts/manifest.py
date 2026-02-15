"""Manifest (domekit.yaml) schema — Pydantic models (Phase 0).

Mirrors the structure in the Phase 0 spec §10.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


# ── Top-level sections ──────────────────────────────────────────────


class AppInfo(BaseModel):
    name: str
    version: str = "0.0.1"


class PolicyMode(str, Enum):
    LOCAL_ONLY = "local_only"
    DEVELOPER = "developer"


class RuntimeConfig(BaseModel):
    base_url: str = "http://127.0.0.1:8080"
    policy_mode: PolicyMode = PolicyMode.LOCAL_ONLY


# ── Policy sub-sections ─────────────────────────────────────────────


class NetworkPolicy(BaseModel):
    outbound: str = "deny"  # "deny" | "allow"
    allow_domains: list[str] = []


class DataSqlitePolicy(BaseModel):
    allow: list[str] = []


class DataFilesystemPolicy(BaseModel):
    allow_read: list[str] = []
    allow_write: list[str] = []


class DataVectorPolicy(BaseModel):
    allow: list[str] = []          # allowed collection/DB paths (read)
    allow_write: list[str] = []    # paths where insert/update/delete is allowed


class DataPolicy(BaseModel):
    sqlite: DataSqlitePolicy = DataSqlitePolicy()
    filesystem: DataFilesystemPolicy = DataFilesystemPolicy()
    vector: DataVectorPolicy = DataVectorPolicy()


class ToolsPolicy(BaseModel):
    allow: list[str] = []


class Policy(BaseModel):
    network: NetworkPolicy = NetworkPolicy()
    tools: ToolsPolicy = ToolsPolicy()
    data: DataPolicy = DataPolicy()


# ── Models ───────────────────────────────────────────────────────────


class ModelEntry(BaseModel):
    id: str
    context_window: int = 8192


class ModelsConfig(BaseModel):
    backend: str = "ollama"
    default: str = ""
    map: dict[str, ModelEntry] = {}


# ── Per-tool config ──────────────────────────────────────────────────


class ToolConfig(BaseModel):
    type: str = "builtin"
    read_only: bool = False
    max_rows: int | None = None
    max_bytes: int | None = None


# ── Audit ────────────────────────────────────────────────────────────


class AuditConfig(BaseModel):
    path: str = "audit.jsonl"
    redact_prompt: bool = False
    redact_tool_outputs: bool = False


# ── Embedding + Vector DB config ─────────────────────────────────────


class EmbeddingConfig(BaseModel):
    backend: str = "ollama"
    model: str = "nomic-embed-text"


class VectorConfig(BaseModel):
    backend: str = "chroma"        # "chroma" or "lance"
    default_top_k: int = 10


# ── Root manifest ────────────────────────────────────────────────────


class Manifest(BaseModel):
    app: AppInfo
    runtime: RuntimeConfig = RuntimeConfig()
    policy: Policy = Policy()
    models: ModelsConfig = ModelsConfig()
    tools: dict[str, ToolConfig] = {}
    audit: AuditConfig = AuditConfig()
    embedding: EmbeddingConfig = EmbeddingConfig()
    vector_db: VectorConfig = VectorConfig()
