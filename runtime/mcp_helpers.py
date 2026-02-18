"""Shared initialisation logic for DomeKit HTTP and MCP servers."""

from __future__ import annotations

import os
from typing import Any

from contracts.manifest import Manifest
from runtime.audit.logger import JsonlAuditLogger
from runtime.manifest_loader import load_manifest
from runtime.policy import DomeKitPolicyEngine
from runtime.tools.registry import ToolRegistry, create_default_registry


def _create_embedding_adapter(manifest: Manifest) -> Any:
    """Create an embedding adapter from manifest config."""
    backend = manifest.embedding.backend
    if backend == "ollama":
        from runtime.embedding_adapters.ollama import OllamaEmbeddingAdapter
        return OllamaEmbeddingAdapter(model=manifest.embedding.model)
    return None


def _create_vector_adapter(manifest: Manifest) -> Any:
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


class DomeKitComponents:
    """Container for initialised DomeKit components."""

    def __init__(
        self,
        manifest: Manifest,
        policy: DomeKitPolicyEngine,
        registry: ToolRegistry,
        logger: JsonlAuditLogger,
    ) -> None:
        self.manifest = manifest
        self.policy = policy
        self.registry = registry
        self.logger = logger


def init_domekit(manifest_path: str | None = None) -> DomeKitComponents:
    """Load manifest and create policy engine, tool registry, and audit logger.

    Uses ``DOMEKIT_MANIFEST`` env var if *manifest_path* is not provided.
    """
    if manifest_path is None:
        manifest_path = os.environ.get("DOMEKIT_MANIFEST", "./domekit.yaml")

    manifest = load_manifest(manifest_path)

    policy = DomeKitPolicyEngine()
    policy.load_manifest(manifest)

    embedding_adapter = _create_embedding_adapter(manifest)
    vector_adapter = _create_vector_adapter(manifest)

    registry = create_default_registry(
        embedding_adapter=embedding_adapter,
        vector_adapter=vector_adapter,
    )

    logger = JsonlAuditLogger(manifest.audit.path)

    return DomeKitComponents(
        manifest=manifest,
        policy=policy,
        registry=registry,
        logger=logger,
    )
