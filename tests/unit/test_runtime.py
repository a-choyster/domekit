"""Unit tests for the DomeKit runtime server (Phase 0)."""

from __future__ import annotations

import json
import os
import tempfile
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from contracts.api import ChatRequest, Message, Role, ToolCall, ToolCallFunction
from contracts.manifest import (
    AppInfo,
    AuditConfig,
    Manifest,
    ModelsConfig,
    Policy,
    ToolsPolicy,
)
from contracts.audit import AuditEvent
from contracts.tool_sdk import ToolContext, ToolOutput

from runtime.audit.logger import JsonlAuditLogger
from runtime.model_adapters.ollama import OllamaAdapter
from runtime.policy import DomeKitPolicyEngine
from runtime.tool_router import ToolRouter
from runtime.tools.registry import create_default_registry


# ── Helpers ──────────────────────────────────────────────────────────


def _make_manifest(
    allowed_tools: list[str] | None = None,
    audit_path: str = "test_audit.jsonl",
) -> Manifest:
    """Create a minimal test manifest."""
    return Manifest(
        app=AppInfo(name="test-app", version="0.0.1"),
        policy=Policy(tools=ToolsPolicy(allow=allowed_tools or ["sql_query", "read_file", "write_file"])),
        models=ModelsConfig(default="test-model"),
        audit=AuditConfig(path=audit_path),
    )


def _make_manifest_file(path: str, allowed_tools: list[str] | None = None) -> None:
    """Write a domekit.yaml for the test app."""
    import yaml

    m = _make_manifest(allowed_tools=allowed_tools, audit_path=os.path.join(os.path.dirname(path), "test_audit.jsonl"))
    data = {
        "app": {"name": m.app.name, "version": m.app.version},
        "policy": {"tools": {"allow": m.policy.tools.allow}},
        "models": {"default": "test-model"},
        "audit": {"path": m.audit.path},
    }
    with open(path, "w") as f:
        yaml.dump(data, f)


# ── Test: health endpoint ────────────────────────────────────────────


class TestHealthEndpoint:
    def test_health_returns_ok(self, tmp_path: Any) -> None:
        manifest_path = str(tmp_path / "domekit.yaml")
        _make_manifest_file(manifest_path)

        os.environ["DOMEKIT_MANIFEST"] = manifest_path
        try:
            # Re-import to pick up env var in lifespan
            from runtime.app import app

            with TestClient(app) as client:
                resp = client.get("/v1/domekit/health")
                assert resp.status_code == 200
                body = resp.json()
                assert body["status"] == "ok"
                assert body["version"] == "0.1.0"
        finally:
            os.environ.pop("DOMEKIT_MANIFEST", None)


# ── Test: Ollama adapter ────────────────────────────────────────────


class TestOllamaAdapter:
    def test_to_ollama_message(self) -> None:
        msg = Message(role=Role.USER, content="hello")
        result = OllamaAdapter._to_ollama_message(msg)
        assert result == {"role": "user", "content": "hello"}

    def test_to_ollama_message_with_tool_calls(self) -> None:
        msg = Message(
            role=Role.ASSISTANT,
            tool_calls=[
                ToolCall(
                    id="call_0",
                    function=ToolCallFunction(name="test", arguments='{"a": 1}'),
                )
            ],
        )
        result = OllamaAdapter._to_ollama_message(msg)
        assert result["tool_calls"][0]["function"]["name"] == "test"
        assert result["tool_calls"][0]["function"]["arguments"] == {"a": 1}

    def test_from_ollama_response_content(self) -> None:
        data = {"message": {"role": "assistant", "content": "Hello!"}}
        msg = OllamaAdapter._from_ollama_response(data)
        assert msg.role == Role.ASSISTANT
        assert msg.content == "Hello!"
        assert msg.tool_calls is None

    def test_from_ollama_response_tool_calls(self) -> None:
        data = {
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"function": {"name": "sql_query", "arguments": {"query": "SELECT 1"}}}
                ],
            }
        }
        msg = OllamaAdapter._from_ollama_response(data)
        assert msg.tool_calls is not None
        assert len(msg.tool_calls) == 1
        assert msg.tool_calls[0].function.name == "sql_query"


# ── Test: tool router ───────────────────────────────────────────────


class TestToolRouter:
    @pytest.fixture()
    def setup(self, tmp_path: Any) -> dict[str, Any]:
        audit_path = str(tmp_path / "audit.jsonl")
        manifest = _make_manifest(audit_path=audit_path)

        policy = DomeKitPolicyEngine()
        policy.load_manifest(manifest)

        registry = create_default_registry()
        logger = JsonlAuditLogger(audit_path)
        adapter = OllamaAdapter()

        router = ToolRouter(
            policy=policy,
            registry=registry,
            logger=logger,
            adapter=adapter,
        )
        return {
            "router": router,
            "manifest": manifest,
            "logger": logger,
            "adapter": adapter,
            "audit_path": audit_path,
        }

    @pytest.mark.asyncio
    async def test_simple_chat(self, setup: dict[str, Any]) -> None:
        """Model returns content, no tool calls."""
        router: ToolRouter = setup["router"]
        manifest = setup["manifest"]

        reply = Message(role=Role.ASSISTANT, content="Hi there!")

        with patch.object(
            setup["adapter"], "chat", new_callable=AsyncMock, return_value=reply
        ):
            request = ChatRequest(messages=[Message(role=Role.USER, content="hello")])
            response = await router.run(request, manifest)

        assert response.choices[0].message.content == "Hi there!"
        assert response.trace is not None
        assert response.trace.tools_used == []

    @pytest.mark.asyncio
    async def test_tool_calling_loop(self, setup: dict[str, Any]) -> None:
        """Model requests a tool call, then returns content."""
        router: ToolRouter = setup["router"]
        manifest = setup["manifest"]

        tool_response = Message(
            role=Role.ASSISTANT,
            tool_calls=[
                ToolCall(
                    id="call_0",
                    function=ToolCallFunction(
                        name="read_file",
                        arguments='{"path": "/tmp/test.txt"}',
                    ),
                )
            ],
        )
        final_response = Message(role=Role.ASSISTANT, content="File contents: test")

        mock_chat = AsyncMock(side_effect=[tool_response, final_response])

        with patch.object(setup["adapter"], "chat", mock_chat):
            # Also mock the tool execution since we don't have the file
            with patch(
                "runtime.tools.read_file.ReadFileTool.run",
                new_callable=AsyncMock,
                return_value=ToolOutput(
                    call_id="call_0",
                    tool_name="read_file",
                    result="test content",
                    success=True,
                ),
            ):
                request = ChatRequest(
                    messages=[Message(role=Role.USER, content="read /tmp/test.txt")]
                )
                response = await router.run(request, manifest)

        assert response.choices[0].message.content == "File contents: test"
        assert "read_file" in response.trace.tools_used

    @pytest.mark.asyncio
    async def test_policy_blocks_tool(self, setup: dict[str, Any]) -> None:
        """Policy denies a tool not in allow list."""
        audit_path = setup["audit_path"]
        manifest = _make_manifest(
            allowed_tools=["read_file"],  # sql_query NOT allowed
            audit_path=audit_path,
        )

        policy = DomeKitPolicyEngine()
        policy.load_manifest(manifest)

        router = ToolRouter(
            policy=policy,
            registry=setup["router"]._registry,
            logger=setup["logger"],
            adapter=setup["adapter"],
        )

        tool_response = Message(
            role=Role.ASSISTANT,
            tool_calls=[
                ToolCall(
                    id="call_0",
                    function=ToolCallFunction(
                        name="sql_query",
                        arguments='{"db_path": "test.db", "query": "SELECT 1"}',
                    ),
                )
            ],
        )
        final_response = Message(
            role=Role.ASSISTANT, content="Sorry, that tool is blocked."
        )

        mock_chat = AsyncMock(side_effect=[tool_response, final_response])

        with patch.object(setup["adapter"], "chat", mock_chat):
            request = ChatRequest(
                messages=[Message(role=Role.USER, content="query db")]
            )
            response = await router.run(request, manifest)

        assert response.choices[0].message.content == "Sorry, that tool is blocked."

        # Check audit log for policy.block event
        entries = setup["logger"].query_by_request(response.trace.request_id)
        events = [e.event for e in entries]
        assert AuditEvent.POLICY_BLOCK in events

    @pytest.mark.asyncio
    async def test_audit_trail(self, setup: dict[str, Any]) -> None:
        """Verify request.start and request.end are logged."""
        router: ToolRouter = setup["router"]
        manifest = setup["manifest"]

        reply = Message(role=Role.ASSISTANT, content="done")

        with patch.object(
            setup["adapter"], "chat", new_callable=AsyncMock, return_value=reply
        ):
            request = ChatRequest(messages=[Message(role=Role.USER, content="hi")])
            response = await router.run(request, manifest)

        entries = setup["logger"].query_by_request(response.trace.request_id)
        events = [e.event for e in entries]
        assert AuditEvent.REQUEST_START in events
        assert AuditEvent.REQUEST_END in events

    @pytest.mark.asyncio
    async def test_max_iterations(self, setup: dict[str, Any]) -> None:
        """Router stops after MAX_ITERATIONS even if model keeps requesting tools."""
        router: ToolRouter = setup["router"]
        manifest = setup["manifest"]

        # Model always returns tool calls
        perpetual_tool_call = Message(
            role=Role.ASSISTANT,
            tool_calls=[
                ToolCall(
                    id="call_0",
                    function=ToolCallFunction(
                        name="read_file",
                        arguments='{"path": "/tmp/x.txt"}',
                    ),
                )
            ],
        )

        mock_chat = AsyncMock(return_value=perpetual_tool_call)

        with patch.object(setup["adapter"], "chat", mock_chat):
            with patch(
                "runtime.tools.read_file.ReadFileTool.run",
                new_callable=AsyncMock,
                return_value=ToolOutput(
                    call_id="call_0",
                    tool_name="read_file",
                    result="data",
                    success=True,
                ),
            ):
                request = ChatRequest(
                    messages=[Message(role=Role.USER, content="loop")]
                )
                response = await router.run(request, manifest)

        # Should have been called exactly MAX_ITERATIONS times
        assert mock_chat.call_count == 5
        # The response should still have tool_calls (never got plain content)
        assert response.choices[0].message.tool_calls is not None


# ── Test: FastAPI app integration ────────────────────────────────────


class TestFastAPIApp:
    def test_chat_completions_mocked(self, tmp_path: Any) -> None:
        manifest_path = str(tmp_path / "domekit.yaml")
        _make_manifest_file(manifest_path)
        os.environ["DOMEKIT_MANIFEST"] = manifest_path

        try:
            from runtime.app import app

            with TestClient(app) as client:
                # Mock the OllamaAdapter.chat to avoid real network calls
                reply = Message(role=Role.ASSISTANT, content="Mocked response")
                with patch.object(
                    OllamaAdapter,
                    "chat",
                    new_callable=AsyncMock,
                    return_value=reply,
                ):
                    resp = client.post(
                        "/v1/chat/completions",
                        json={
                            "messages": [{"role": "user", "content": "test"}],
                        },
                    )
                    assert resp.status_code == 200
                    body = resp.json()
                    assert body["choices"][0]["message"]["content"] == "Mocked response"
                    assert "trace" in body
        finally:
            os.environ.pop("DOMEKIT_MANIFEST", None)

    def test_audit_endpoint(self, tmp_path: Any) -> None:
        manifest_path = str(tmp_path / "domekit.yaml")
        _make_manifest_file(manifest_path)
        os.environ["DOMEKIT_MANIFEST"] = manifest_path

        try:
            from runtime.app import app

            with TestClient(app) as client:
                resp = client.get("/v1/domekit/audit/nonexistent-id")
                assert resp.status_code == 200
                assert resp.json() == []
        finally:
            os.environ.pop("DOMEKIT_MANIFEST", None)
