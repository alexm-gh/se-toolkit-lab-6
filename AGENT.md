# Agent Documentation

## Overview

This agent provides a CLI interface to query Large Language Models (LLMs) with tool support. It can explore the project wiki using `read_file` and `list_files` tools, then answer questions with citations.

## Usage

### Basic Command

```bash
uv run agent.py "<your-question>"
```

### Examples

```bash
# Ask about wiki contents
uv run agent.py "What files are in the wiki directory?"

# Ask about documentation
uv run agent.py "How do you resolve a merge conflict?"

# Simple question (no tools needed)
uv run agent.py "What is 2+2?"

# Alternative (use with caution)
uv run agent.py "What is 0 divided by 0?"
```

### Output

The agent outputs a single JSON line to stdout:

```json
{
    "answer": "LLM's response to your query",
    "source": "wiki/file.md#section",
    "tool_calls": [...],
    "log": {}
}
```

**Note:** All debug/progress output goes to stderr.

## Configuration

### Environment File

Create `.env.agent.secret` in the project root:

```bash
cp .env.agent.example .env.agent.secret
```

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `LLM_API_KEY` | Your API key from the LLM provider | `sk-or-v1-...` |
| `LLM_API_BASE` | Base URL of the LLM API | `https://openrouter.ai/api/v1` |
| `LLM_MODEL` | Model identifier | `qwen/qwen3-coder-plus` |

### Recommended Configuration (OpenRouter)

```bash
LLM_API_KEY=<your-openrouter-api-key>
LLM_API_BASE=https://openrouter.ai/api/v1
LLM_MODEL=qwen/qwen3-coder-plus
```

**Get API Key:** Sign up at [openrouter.ai](https://openrouter.ai) and create an API key.

**Available Models:** Browse models at [openrouter.ai/models](https://openrouter.ai/models). Some models are:
- qwen/qwen3-coder:free
- qwen/qwen3-coder-plus
- meta-llama/llama-3.2-3b-instruct:free
- nvidia/nemotron-3-super-120b-a12b:free

## Output Format

### Success Response

```json
{
    "answer": "To resolve a merge conflict, edit the conflicting file...",
    "source": "wiki/git-vscode.md#resolve-a-merge-conflict",
    "tool_calls": [
        {
            "tool": "list_files",
            "args": {"path": "wiki"},
            "result": "git-workflow.md\ngit.md\n..."
        },
        {
            "tool": "read_file",
            "args": {"path": "wiki/git-vscode.md"},
            "result": "# Git in VS Code\n\n..."
        }
    ],
    "log": {}
}
```

### Error Response

```json
{
    "answer": "",
    "source": "",
    "tool_calls": [],
    "log": {
        "message": "Request timed out after 60 seconds",
        "code": "TIMEOUT",
        "response_code": -1
    }
}
```

## Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `answer` | string | The LLM's response. Empty if an error occurred. |
| `source` | string | The wiki file/section that was used for the answer. |
| `tool_calls` | array | List of all tool calls made during the agentic loop. |
| `log` | object | Error information. Empty `{}` on success. |

### Tool Call Structure

Each entry in `tool_calls` contains:

| Field | Type | Description |
|-------|------|-------------|
| `tool` | string | Name of the tool used (`read_file` or `list_files`) |
| `args` | object | Arguments passed to the tool |
| `result` | string | The tool's return value |

### Log Structure

The `log` field is an **object** (not array) with these fields:

| Field | Type | Description |
|-------|------|-------------|
| `message` | string | Human-readable error description |
| `code` | string | Error category (e.g., `TIMEOUT`, `CONFIG_ERROR`) |
| `response_code` | int | HTTP status code from API, or `-1` for internal errors |

### Response Code Values

| Scenario | `response_code` |
|----------|-----------------|
| Internal error (missing config, file not found) | `-1` |
| Network error (timeout, connection failed) | `-1` |
| API returns HTTP error (401, 403, 429, 500) | Actual code from API |
| Success | `200` (log is empty on success) |

### Error Codes

| Code | Meaning | `response_code` |
|------|---------|-----------------|
| `CONFIG_ERROR` | Missing LLM configuration | `-1` |
| `TIMEOUT` | Request exceeded 60-second limit | `-1` |
| `NETWORK_ERROR` | Network/connection failure | `-1` |
| `API_ERROR` | API returned non-200 status | HTTP code (401, 429, etc.) |
| `STRUCTURE_ERROR` | Unexpected response structure | `-1` |
| `MAX_CALLS` | Reached maximum tool calls (10) | `200` |

## Architecture

### Agentic Loop Flow

```
User Question
      │
      ▼
┌─────────────────┐
│  Send to LLM    │
│  + tool schemas │
└────────┬────────┘
         │
         ▼
    ┌────────────┐
    │ tool_calls?│
    └────┬───────┘
         │
    ┌────┴────┐
    │         │
   Yes       No
    │         │
    ▼         ▼
Execute    Return
Tools      Answer
    │
    ▼
Feed back
to LLM
    │
    └──────► (loop)
```

### Components

1. **CLI Parser** — Extracts question from `sys.argv[1]`
2. **Environment Loader** — Parses `.env.agent.secret` into `os.environ`
3. **Tool Schemas** — OpenAI function-calling format for `read_file` and `list_files`
4. **AgentState Class** — Manages message history and tool call tracking
5. **Agentic Loop** — Executes tool calls and feeds results back to LLM
6. **Path Security** — Prevents directory traversal attacks

### Implementation Details

- **HTTP Client:** `httpx` with 60-second timeout
- **Endpoint:** `POST {LLM_API_BASE}/chat/completions`
- **Request Format:** OpenAI-compatible with `tools` parameter
- **Max Tool Calls:** 10 per question
- **Message History:** Tracks `system`, `user`, `assistant`, and `tool` roles

## Tools

### `read_file`

Read a file from the project repository.

**Parameters:**
- `path` (string, required) — Relative path from project root (e.g., `wiki/git-workflow.md`)

**Returns:** File contents as string, or error message

**Security:** Blocks `..` and absolute paths

### `list_files`

List files and directories at a given path.

**Parameters:**
- `path` (string, required) — Relative directory path from project root (e.g., `wiki`)

**Returns:** Newline-separated listing, or error message

**Security:** Blocks `..` and absolute paths

## System Prompt

The agent uses this system prompt to guide the LLM:

```
You are a helpful documentation assistant. You have access to tools that let you 
read files and list directories in a project repository.

When answering questions:
1. Use list_files to discover what files exist
2. Use read_file to examine file contents
3. Always cite your source at the end of your answer in the format: 
   Source: wiki/file.md#section-name
4. If a section doesn't have an anchor, just use the file path

Think step by step. Call tools when you need information, then use the results to answer.
```

## Testing

### Manual Testing

```bash
# Test with tool usage
uv run agent.py "What files are in the wiki?"

# Test with file reading
uv run agent.py "How do you resolve a merge conflict?"

# Test error handling (invalid config)
mv .env.agent.secret .env.agent.secret.bak
uv run agent.py "test"

# Test with stderr suppressed
uv run agent.py "test" 2>/dev/null | python -m json.tool
```

### Regression Tests

Run the test suite:

```bash
uv run pytest tests/test_agent.py -v
```

Tests verify:
- JSON output structure (`answer`, `source`, `tool_calls`, `log`)
- Tool usage (`list_files` for directory questions)
- Tool usage (`read_file` for documentation questions)
- Source field contains wiki path

## Troubleshooting

### Common Issues

**"LLM configuration incomplete"**
- Ensure `.env.agent.secret` exists with `LLM_API_KEY`, `LLM_API_BASE`, `LLM_MODEL`

**"Request timed out"**
- Check network connectivity
- Verify `LLM_API_BASE` is accessible
- The LLM may be overloaded (try a different model)

**"429 Too Many Requests"**
- You've hit rate limits (common with free-tier models)
- The LLM may be overloaded (try a different model)
- Wait and retry, or switch to a different model

**"Failed to parse JSON"**
- The API returned malformed response
- Check if the API endpoint is correct

**Agent doesn't use tools**
- Some questions don't require tools (simple math, general knowledge)
- Ask about project-specific documentation to trigger tool usage
