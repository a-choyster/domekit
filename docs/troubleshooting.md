# Troubleshooting

## Model Not Calling Tools

**Symptoms:** Model returns text explanations instead of using tools.

**Solutions:**
1. DomeKit automatically falls back to prompt-based tool calling for models that don't support native tools (gemma3, gemma2). No configuration needed.
2. For best results, use models with native tool support: Qwen 2.5, Llama 3.1+, Mistral
3. Check the system prompt guides the model to use tools
4. Verify tools are in the manifest `allow` list
5. Check audit log for `policy.block` events:
   ```bash
   python cli/domekit.py logs audit.jsonl -e policy.block
   ```

## Tool Execution Fails

**Symptoms:** Tool called but returns errors.

**Solutions:**
1. Check the tool has access to required resources:
   ```yaml
   policy:
     data:
       sqlite:
         allow: ["path/to/database.db"]  # Exact path
   ```
2. Verify file/database exists and is readable
3. Check audit log for error details:
   ```bash
   python cli/domekit.py logs audit.jsonl -r <request_id>
   ```

## Ollama Connection Issues

**Symptoms:** `Connection refused` or `Cannot connect to Ollama`.

**Solutions:**
1. Verify Ollama is running:
   ```bash
   curl http://localhost:11434/api/tags
   ```
2. Start Ollama if needed:
   ```bash
   ollama serve
   ```
3. Check model is pulled:
   ```bash
   ollama list
   ollama pull llama3.1:8b
   ```

## Audit Log Not Created

**Symptoms:** No `audit.jsonl` file.

**Solutions:**
1. Check manifest `audit.path` is correct
2. Verify parent directory exists and is writable
3. Check runtime logs for permission errors

## Tests Failing

**Solutions:**
1. Reinstall dependencies:
   ```bash
   pip install -e ".[dev]"
   ```
2. Check Python version (requires 3.11+):
   ```bash
   python --version
   ```
3. Run specific failing test with verbose output:
   ```bash
   pytest tests/path/to/test.py::test_name -vv
   ```
