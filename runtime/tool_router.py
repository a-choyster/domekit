"""Tool router — orchestrates the model ↔ tool calling loop (Phase 0)."""

from __future__ import annotations

import json
import uuid
from typing import Any

from contracts.api import (
    ChatRequest,
    ChatResponse,
    Choice,
    Message,
    Role,
    TraceMeta,
)
from contracts.audit import AuditEntry, AuditEvent
from contracts.manifest import Manifest
from contracts.policy import PolicyVerdict
from contracts.tool_sdk import ToolContext, ToolInput

from runtime.audit.logger import JsonlAuditLogger
from runtime.model_adapters.ollama import OllamaAdapter
from runtime.policy import DomeKitPolicyEngine
from runtime.tools.registry import ToolRegistry

MAX_ITERATIONS = 5


class ToolRouter:
    """Runs the model → tool-call → model loop with policy enforcement."""

    def __init__(
        self,
        policy: DomeKitPolicyEngine,
        registry: ToolRegistry,
        logger: JsonlAuditLogger,
        adapter: OllamaAdapter,
    ) -> None:
        self._policy = policy
        self._registry = registry
        self._logger = logger
        self._adapter = adapter

    async def run(self, request: ChatRequest, manifest: Manifest) -> ChatResponse:
        """Execute the chat completion with tool-calling loop."""
        request_id = str(uuid.uuid4())
        model = manifest.models.default or request.model
        policy_mode = manifest.runtime.policy_mode.value
        app_name = manifest.app.name

        tools_used: list[str] = []
        tables_queried: list[str] = []

        # Audit: request.start
        self._logger.log(
            AuditEntry(
                request_id=request_id,
                event=AuditEvent.REQUEST_START,
                app=app_name,
                model=model,
                policy_mode=policy_mode,
            )
        )

        # Build message list; prepend system prompt if absent
        messages = list(request.messages)
        if messages and messages[0].role != Role.SYSTEM:
            system_prompt = f"You are {app_name}, a DomeKit-powered assistant."
            messages.insert(0, Message(role=Role.SYSTEM, content=system_prompt))

        # Get tool definitions for the model
        tool_defs = self._registry.get_openai_definitions() or None

        # Tool-calling loop
        last_message = Message(role=Role.ASSISTANT, content="")
        for _ in range(MAX_ITERATIONS):
            last_message = await self._adapter.chat(messages, model, tools=tool_defs)

            if not last_message.tool_calls:
                break

            # Append assistant message with tool_calls
            messages.append(last_message)

            for tc in last_message.tool_calls:
                tool_name = tc.function.name
                try:
                    args: dict[str, Any] = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}

                tool_input = ToolInput(
                    tool_name=tool_name, arguments=args, call_id=tc.id
                )

                # Policy check
                decision = self._policy.check_tool(tool_input)

                if decision.verdict == PolicyVerdict.DENY:
                    # Log policy block
                    self._logger.log(
                        AuditEntry(
                            request_id=request_id,
                            event=AuditEvent.POLICY_BLOCK,
                            app=app_name,
                            model=model,
                            policy_mode=policy_mode,
                            detail={
                                "tool": tool_name,
                                "rule": decision.rule,
                                "reason": decision.reason,
                            },
                        )
                    )
                    messages.append(
                        Message(
                            role=Role.TOOL,
                            content=json.dumps(
                                {"error": f"Policy denied: {decision.reason}"}
                            ),
                            tool_call_id=tc.id,
                        )
                    )
                    continue

                # Audit: tool.call
                self._logger.log(
                    AuditEntry(
                        request_id=request_id,
                        event=AuditEvent.TOOL_CALL,
                        app=app_name,
                        model=model,
                        policy_mode=policy_mode,
                        detail={"tool": tool_name, "arguments": args},
                    )
                )

                # Execute tool
                sql_config = manifest.tools.get("sql_query")
                read_config = manifest.tools.get("read_file")
                ctx = ToolContext(
                    request_id=request_id,
                    app_name=app_name,
                    policy_mode=policy_mode,
                    manifest_data_paths={
                        "sqlite_allow": manifest.policy.data.sqlite.allow,
                        "fs_allow_read": manifest.policy.data.filesystem.allow_read,
                        "fs_allow_write": manifest.policy.data.filesystem.allow_write,
                        "max_rows": sql_config.max_rows if sql_config else 100,
                        "max_bytes": read_config.max_bytes if read_config else 65536,
                        "vector_allow": manifest.policy.data.vector.allow,
                        "vector_allow_write": manifest.policy.data.vector.allow_write,
                        "vector_backend": manifest.vector_db.backend,
                        "default_top_k": manifest.vector_db.default_top_k,
                    },
                )
                try:
                    tool = self._registry.get(tool_name)
                    output = await tool.run(ctx, args)
                except KeyError:
                    output_content = json.dumps(
                        {"error": f"Unknown tool: {tool_name}"}
                    )
                except Exception as exc:
                    output_content = json.dumps({"error": str(exc)})
                else:
                    output_content = json.dumps(
                        {"result": output.result, "success": output.success}
                    )
                    if output.error:
                        output_content = json.dumps(
                            {"error": output.error, "success": False}
                        )

                tools_used.append(tool_name)

                # Track tables for sql_query
                if tool_name == "sql_query":
                    table = args.get("table", "")
                    if table and table not in tables_queried:
                        tables_queried.append(table)

                # Audit: tool.result
                self._logger.log(
                    AuditEntry(
                        request_id=request_id,
                        event=AuditEvent.TOOL_RESULT,
                        app=app_name,
                        model=model,
                        policy_mode=policy_mode,
                        detail={"tool": tool_name, "call_id": tc.id},
                    )
                )

                messages.append(
                    Message(
                        role=Role.TOOL,
                        content=output_content,
                        tool_call_id=tc.id,
                    )
                )

        # Audit: request.end
        self._logger.log(
            AuditEntry(
                request_id=request_id,
                event=AuditEvent.REQUEST_END,
                app=app_name,
                model=model,
                policy_mode=policy_mode,
                detail={"tools_used": tools_used},
            )
        )

        trace = TraceMeta(
            request_id=request_id,
            tools_used=tools_used,
            tables_queried=tables_queried,
            policy_mode=policy_mode,
            model=model,
        )

        return ChatResponse(
            id=request_id,
            model=model,
            choices=[
                Choice(
                    index=0,
                    message=last_message,
                    finish_reason="stop",
                )
            ],
            trace=trace,
        )
