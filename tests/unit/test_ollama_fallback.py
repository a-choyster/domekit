"""Unit tests for OllamaAdapter fallback parsing of tool calls in text content."""

from __future__ import annotations

from contracts.api import Role
from runtime.model_adapters.ollama import OllamaAdapter


class TestOllamaFallbackParser:
    """Test that the adapter can parse tool calls returned as JSON text."""

    def test_fallback_parses_well_formed_json_tool_call(self) -> None:
        """Model returns tool call as clean JSON in content field."""
        data = {
            "message": {
                "role": "assistant",
                "content": '{"name": "sql_query", "arguments": {"db_path": "test.db", "query": "SELECT 1"}}',
            }
        }
        msg = OllamaAdapter._from_ollama_response(data)

        assert msg.role == Role.ASSISTANT
        assert msg.content is None  # Content cleared since tool call extracted
        assert msg.tool_calls is not None
        assert len(msg.tool_calls) == 1
        assert msg.tool_calls[0].function.name == "sql_query"
        assert '"db_path": "test.db"' in msg.tool_calls[0].function.arguments
        assert '"query": "SELECT 1"' in msg.tool_calls[0].function.arguments

    def test_fallback_parses_malformed_json_with_escaped_quotes(self) -> None:
        """Model returns malformed JSON with escaped quotes in wrong places."""
        data = {
            "message": {
                "role": "assistant",
                "content": '{"name":"sql_query","parameters\\":{\"db_path\":\"apps/health-poc/data/health.db\",\"query\":\"SELECT COUNT(*) FROM activities\"}}',
            }
        }
        msg = OllamaAdapter._from_ollama_response(data)

        assert msg.role == Role.ASSISTANT
        assert msg.content is None
        assert msg.tool_calls is not None
        assert len(msg.tool_calls) == 1
        assert msg.tool_calls[0].function.name == "sql_query"
        # Should parse parameters field (some models use "parameters" instead of "arguments")
        assert "db_path" in msg.tool_calls[0].function.arguments

    def test_fallback_handles_parameters_field_instead_of_arguments(self) -> None:
        """Some models use 'parameters' instead of 'arguments'."""
        data = {
            "message": {
                "role": "assistant",
                "content": '{"name": "read_file", "parameters": {"path": "/tmp/test.txt"}}',
            }
        }
        msg = OllamaAdapter._from_ollama_response(data)

        assert msg.tool_calls is not None
        assert msg.tool_calls[0].function.name == "read_file"
        assert '"path": "/tmp/test.txt"' in msg.tool_calls[0].function.arguments

    def test_fallback_ignores_non_tool_json(self) -> None:
        """JSON content that isn't a tool call is left as regular content."""
        data = {
            "message": {
                "role": "assistant",
                "content": '{"result": "some data", "status": "ok"}',
            }
        }
        msg = OllamaAdapter._from_ollama_response(data)

        assert msg.content == '{"result": "some data", "status": "ok"}'
        assert msg.tool_calls is None

    def test_fallback_ignores_invalid_json(self) -> None:
        """Completely broken JSON is left as regular content."""
        data = {
            "message": {
                "role": "assistant",
                "content": '{"broken": invalid json here}',
            }
        }
        msg = OllamaAdapter._from_ollama_response(data)

        assert msg.content == '{"broken": invalid json here}'
        assert msg.tool_calls is None

    def test_native_tool_calls_take_precedence(self) -> None:
        """When tool_calls array exists, don't try to parse content."""
        data = {
            "message": {
                "role": "assistant",
                "content": '{"name": "fake_tool", "arguments": {}}',
                "tool_calls": [
                    {
                        "id": "call_123",
                        "function": {
                            "name": "real_tool",
                            "arguments": {"key": "value"},
                        },
                    }
                ],
            }
        }
        msg = OllamaAdapter._from_ollama_response(data)

        assert msg.tool_calls is not None
        assert len(msg.tool_calls) == 1
        assert msg.tool_calls[0].function.name == "real_tool"
        assert msg.tool_calls[0].id == "call_123"

    def test_fallback_with_multiline_json(self) -> None:
        """Handle tool calls with newlines and formatting."""
        data = {
            "message": {
                "role": "assistant",
                "content": """{
  "name": "sql_query",
  "arguments": {
    "db_path": "apps/health-poc/data/health.db",
    "query": "SELECT COUNT(*) FROM activities WHERE date BETWEEN 'last_month_start' AND 'last_month_end';"
  }
}""",
            }
        }
        msg = OllamaAdapter._from_ollama_response(data)

        assert msg.tool_calls is not None
        assert msg.tool_calls[0].function.name == "sql_query"
        assert "db_path" in msg.tool_calls[0].function.arguments

    def test_fallback_fixes_missing_colon_after_parameters(self) -> None:
        """Model forgets colon: 'parameters{' instead of 'parameters':{ """
        data = {
            "message": {
                "role": "assistant",
                "content": '{"name":"sql_query","parameters{"db_path": "test.db", "query":"SELECT 1"}}',
            }
        }
        msg = OllamaAdapter._from_ollama_response(data)

        assert msg.tool_calls is not None
        assert msg.tool_calls[0].function.name == "sql_query"
        assert "db_path" in msg.tool_calls[0].function.arguments
