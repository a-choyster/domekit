"""Tool registry — register, look-up, and export DomeKit tools."""

from __future__ import annotations

from contracts.tool_sdk import BaseTool


class ToolRegistry:
    """In-memory registry of available tools."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool instance.  Overwrites if name already exists."""
        name = tool.definition().name
        self._tools[name] = tool

    def get(self, name: str) -> BaseTool:
        """Return a registered tool by name, or raise ``KeyError``."""
        return self._tools[name]

    def list_tools(self) -> list[str]:
        """Return sorted list of registered tool names."""
        return sorted(self._tools)

    def get_openai_definitions(self) -> list[dict]:
        """Export all tools in OpenAI function-calling format."""
        defs: list[dict] = []
        for name in sorted(self._tools):
            defn = self._tools[name].definition()
            defs.append(
                {
                    "type": "function",
                    "function": {
                        "name": defn.name,
                        "description": defn.description,
                        "parameters": defn.input_schema,
                    },
                }
            )
        return defs


def create_default_registry(
    embedding_adapter: object | None = None,
    vector_adapter: object | None = None,
) -> ToolRegistry:
    """Create a registry pre-loaded with all built-in tools."""
    from runtime.tools.sql_query import SqlQueryTool
    from runtime.tools.read_file import ReadFileTool
    from runtime.tools.write_file import WriteFileTool
    from runtime.tools.vector_search import VectorSearchTool
    from runtime.tools.vector_manage import VectorManageTool

    registry = ToolRegistry()
    registry.register(SqlQueryTool())
    registry.register(ReadFileTool())
    registry.register(WriteFileTool())
    registry.register(VectorSearchTool(
        embedding_adapter=embedding_adapter,
        vector_adapter=vector_adapter,
    ))
    registry.register(VectorManageTool(
        embedding_adapter=embedding_adapter,
        vector_adapter=vector_adapter,
    ))
    return registry
