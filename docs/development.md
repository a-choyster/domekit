# Development

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run unit tests only
pytest tests/unit/ -v

# Run integration tests only
pytest tests/integration/ -v

# Run specific test file
pytest tests/unit/test_policy.py -v

# Run with coverage
pytest tests/ --cov=runtime --cov-report=html
```

**Test count:** 129 tests (unit + integration)

## Adding a New Tool

### 1. Define the tool

Inherit from `BaseTool`:

```python
from contracts.tool_sdk import BaseTool, ToolContext, ToolDefinition, ToolOutput
from typing import Any

class MyCustomTool(BaseTool):
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="my_tool",
            description="Does something useful",
            input_schema={
                "type": "object",
                "properties": {
                    "param": {"type": "string"}
                },
                "required": ["param"]
            },
            permissions=["custom:permission"]
        )

    async def run(self, ctx: ToolContext, args: dict[str, Any]) -> ToolOutput:
        result = f"Processed: {args['param']}"
        return ToolOutput(
            call_id=ctx.request_id,
            tool_name="my_tool",
            result=result,
        )
```

### 2. Register the tool

```python
# In runtime/tools/registry.py
from runtime.tools.my_tool import MyCustomTool

def create_default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(SqlQueryTool())
    registry.register(ReadFileTool())
    registry.register(WriteFileTool())
    registry.register(MyCustomTool())  # Add your tool
    return registry
```

### 3. Update the manifest

```yaml
policy:
  tools:
    allow:
      - my_tool
```

### 4. Write tests

```python
def test_my_custom_tool():
    tool = MyCustomTool()
    ctx = ToolContext(request_id="test", app_name="test")
    output = await tool.run(ctx, {"param": "test"})
    assert output.success
    assert "Processed: test" in output.result
```

## Contributing

```bash
# Fork and clone
git clone https://github.com/a-choyster/domekit.git
cd domekit

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Make your changes, add tests, commit
git checkout -b feature/my-feature
pytest tests/ -v
git commit -m "feat: add my feature"

# Push and create PR
git push origin feature/my-feature
```
