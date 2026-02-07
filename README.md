# MCP Media Factory
Turn your LLM into a local video editor.

This Model Context Protocol (MCP) server enables AI agents to access and extract video content


## Configuration

| Variable | Default | Options |
|---|---|---|
| `WHISPER_MODEL_SIZE` | `base` | `tiny`, `base`, `small`, `medium`, `large-v3` |

The Whisper model loads lazily on the first transcription call. Larger models are more accurate but slower and use more memory.

```bash
export WHISPER_MODEL_SIZE=small
```

## Run server
```bash
fastmcp run src/server.py:mcp --transport http --port 8000