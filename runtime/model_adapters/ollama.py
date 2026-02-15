"""Ollama model adapter (Phase 0).

Proxies chat requests to a local Ollama instance via httpx.
Falls back to prompt-based tool calling for models that don't support native tools.
"""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

from contracts.api import Message, Role, ToolCall, ToolCallFunction

# Models known to NOT support Ollama native tool calling
_NO_NATIVE_TOOLS = {"gemma3", "gemma2", "gemma"}


def _model_family(model: str) -> str:
    """Extract model family from model name, e.g. 'gemma3:12b' -> 'gemma3'."""
    return model.split(":")[0].split("/")[-1]


def _build_tool_prompt(tools: list[dict[str, Any]]) -> str:
    """Build a system prompt section describing available tools."""
    lines = [
        "\n\n## Tool Calling",
        "You have access to the following tools. To call a tool, respond with a JSON block:",
        '```json\n{"tool_call": {"name": "tool_name", "arguments": {"arg": "value"}}}\n```',
        "You may include explanation text before or after the JSON block.",
        "Available tools:\n",
    ]
    for tool in tools:
        fn = tool.get("function", {})
        name = fn.get("name", "")
        desc = fn.get("description", "")
        params = fn.get("parameters", {})
        props = params.get("properties", {})
        required = params.get("required", [])
        param_lines = []
        for pname, pdef in props.items():
            req = " (required)" if pname in required else ""
            param_lines.append(f"    - {pname}: {pdef.get('type', 'any')} — {pdef.get('description', '')}{req}")
        lines.append(f"- **{name}**: {desc}")
        if param_lines:
            lines.append("\n".join(param_lines))
    return "\n".join(lines)


def _extract_tool_call_from_text(content: str) -> tuple[ToolCall | None, str | None]:
    """Try to extract a tool call JSON from text content.

    Returns (tool_call, remaining_content) or (None, original_content).
    """
    if not content:
        return None, content

    # Match ```json ... ``` blocks
    json_block = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
    if json_block:
        try:
            parsed = json.loads(json_block.group(1))
            tc = parsed.get("tool_call")
            if isinstance(tc, dict) and "name" in tc:
                args = tc.get("arguments", {})
                remaining = content[:json_block.start()].strip()
                if not remaining:
                    remaining = None
                return ToolCall(
                    id="call_0",
                    type="function",
                    function=ToolCallFunction(
                        name=tc["name"],
                        arguments=json.dumps(args) if isinstance(args, dict) else str(args),
                    ),
                ), remaining
        except (json.JSONDecodeError, KeyError):
            pass

    # Match bare JSON {"tool_call": ...}
    bare_match = re.search(r'\{"tool_call"\s*:\s*\{.*?\}\s*\}', content, re.DOTALL)
    if bare_match:
        try:
            parsed = json.loads(bare_match.group(0))
            tc = parsed.get("tool_call")
            if isinstance(tc, dict) and "name" in tc:
                args = tc.get("arguments", {})
                remaining = content[:bare_match.start()].strip()
                if not remaining:
                    remaining = None
                return ToolCall(
                    id="call_0",
                    type="function",
                    function=ToolCallFunction(
                        name=tc["name"],
                        arguments=json.dumps(args) if isinstance(args, dict) else str(args),
                    ),
                ), remaining
        except (json.JSONDecodeError, KeyError):
            pass

    return None, content


class OllamaAdapter:
    """Async adapter for the Ollama /api/chat endpoint."""

    def __init__(self, base_url: str = "http://localhost:11434") -> None:
        self._base_url = base_url.rstrip("/")

    async def chat(
        self,
        messages: list[Message],
        model: str,
        tools: list[dict[str, Any]] | None = None,
    ) -> Message:
        """Send messages to Ollama and return the assistant response."""
        family = _model_family(model)
        use_native_tools = tools and family not in _NO_NATIVE_TOOLS

        prompt_tools = not use_native_tools and bool(tools)
        payload: dict[str, Any] = {
            "model": model,
            "messages": self._build_messages(messages, prompt_tools),
            "stream": False,
        }

        # Inject tool definitions into system prompt for non-native models
        if not use_native_tools and tools:
            tool_prompt = _build_tool_prompt(tools)
            # Find system message and append tool info
            for msg in payload["messages"]:
                if msg["role"] == "system":
                    msg["content"] = (msg.get("content") or "") + tool_prompt
                    break
            else:
                # No system message — prepend one
                payload["messages"].insert(0, {"role": "system", "content": tool_prompt})

        if use_native_tools:
            payload["tools"] = tools

        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(f"{self._base_url}/api/chat", json=payload)
            resp.raise_for_status()

        data = resp.json()
        result = self._from_ollama_response(data)

        # For non-native tool models, extract tool calls from text
        if not use_native_tools and tools and result.content and not result.tool_calls:
            tc, remaining = _extract_tool_call_from_text(result.content)
            if tc:
                result = Message(
                    role=Role.ASSISTANT,
                    content=remaining,
                    tool_calls=[tc],
                )

        return result

    # ── format helpers ───────────────────────────────────────────────

    @staticmethod
    def _build_messages(messages: list[Message], prompt_tools: bool) -> list[dict[str, Any]]:
        """Convert DomeKit Messages to Ollama format.

        When prompt_tools=True (model doesn't support native tools):
        - Assistant messages with tool_calls → assistant message with JSON text
        - Tool result messages → user message with "Tool result: ..."
        """
        out: list[dict[str, Any]] = []
        for msg in messages:
            m: dict[str, Any] = {"role": msg.role.value}

            if msg.content is not None:
                m["content"] = msg.content

            if prompt_tools:
                # Convert tool-related messages to plain text
                if msg.role == Role.TOOL:
                    m["role"] = "user"
                    m["content"] = f"Tool result: {msg.content}"
                elif msg.tool_calls:
                    # Convert assistant tool call to text so the model sees what it "said"
                    tc = msg.tool_calls[0]
                    call_json = json.dumps({
                        "tool_call": {
                            "name": tc.function.name,
                            "arguments": json.loads(tc.function.arguments),
                        }
                    })
                    text = msg.content or ""
                    m["content"] = f"{text}\n```json\n{call_json}\n```".strip()
                    # Don't include native tool_calls
                out.append(m)
            else:
                # Native tool support — pass through
                if msg.tool_calls:
                    m["tool_calls"] = [
                        {
                            "function": {
                                "name": tc.function.name,
                                "arguments": json.loads(tc.function.arguments),
                            }
                        }
                        for tc in msg.tool_calls
                    ]
                if msg.tool_call_id is not None:
                    m["tool_call_id"] = msg.tool_call_id
                out.append(m)

        return out

    @staticmethod
    def _from_ollama_response(data: dict[str, Any]) -> Message:
        """Convert an Ollama chat response into a DomeKit Message."""
        msg_data = data.get("message", {})
        content = msg_data.get("content") or None
        tool_calls: list[ToolCall] | None = None

        raw_calls = msg_data.get("tool_calls")
        if raw_calls:
            tool_calls = []
            for i, tc in enumerate(raw_calls):
                fn = tc.get("function", {})
                args = fn.get("arguments", {})
                if isinstance(args, dict):
                    args_str = json.dumps(args)
                else:
                    args_str = str(args)
                # Use Ollama's id if present, otherwise generate one
                call_id = tc.get("id", f"call_{i}")
                tool_calls.append(
                    ToolCall(
                        id=call_id,
                        type="function",
                        function=ToolCallFunction(
                            name=fn.get("name", ""),
                            arguments=args_str,
                        ),
                    )
                )
        # Fallback: some models return tool calls as JSON text in content
        elif content and content.strip().startswith("{"):
            try:
                # Try to fix common JSON formatting issues from models
                cleaned = content.strip()
                # Fix escaped quotes in wrong places: "parameters\":{" -> "parameters":{
                cleaned = cleaned.replace('\\":{', '":{').replace('\\":', '":')
                # Fix missing quote and colon: "parameters{" -> "parameters":{
                cleaned = re.sub(r'"(parameters|arguments)(\{)', r'"\1":\2', cleaned)

                parsed = json.loads(cleaned)
                # Check if it looks like a tool call (has "name" and "arguments" or "parameters")
                if isinstance(parsed, dict) and "name" in parsed:
                    args = parsed.get("arguments") or parsed.get("parameters", {})
                    if args:
                        tool_calls = [
                            ToolCall(
                                id="call_0",
                                type="function",
                                function=ToolCallFunction(
                                    name=parsed["name"],
                                    arguments=json.dumps(args) if isinstance(args, dict) else str(args),
                                ),
                            )
                        ]
                        # Clear content since we extracted the tool call
                        content = None
            except (json.JSONDecodeError, KeyError):
                # Not a tool call, treat as regular content
                pass

        return Message(
            role=Role.ASSISTANT,
            content=content,
            tool_calls=tool_calls,
        )
