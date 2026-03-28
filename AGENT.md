# Agent Documentation

## Overview

This agent provides a CLI interface to query Large Language Models (LLMs) with tool support. It can explore the project wiki using `read_file` and `list_files` tools, query the backend API using `query_api`, and answer questions with citations.

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

# Query the backend API
uv run agent.py "How many items are in the database?"

# Ask about system facts
uv run agent.py "What HTTP status code does /items/ return without auth?"

# Simple question (no tools needed)
uv run agent.py "What is 2+2?"
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

### Environment Files

Create two environment files:

**`.env.agent.secret`** — LLM configuration:
```bash
cp .env.agent.example .env.agent.secret
```

**`.env.docker.secret`** — Backend API key (for `query_api`):
```bash
cp .env.docker.example .env.docker.secret
```

### Required Variables

| Variable | Description | Source |
|----------|-------------|--------|
| `LLM_API_KEY` | LLM provider API key | `.env.agent.secret` |
| `LLM_API_BASE` | LLM API endpoint URL | `.env.agent.secret` |
| `LLM_MODEL` | Model identifier | `.env.agent.secret` |
| `LMS_API_KEY` | Backend API key for query_api auth | `.env.docker.secret` |
| `AGENT_API_BASE_URL` | Base URL for backend (default: http://localhost:42002) | Optional, env var |

### Recommended Configuration (OpenRouter)

```bash
LLM_API_KEY=<your-openrouter-api-key>
LLM_API_BASE=https://openrouter.ai/api/v1
LLM_MODEL=qwen/qwen3-coder-plus
```

**Get API Key:** Sign up at [openrouter.ai](https://openrouter.ai) and create an API key.

## Output Format

### Success Response

```json
{
    "answer": "There are 120 items in the database.",
    "source": "backend/app/routers/items.py",
    "tool_calls": [
        {
            "tool": "query_api",
            "args": {"method": "GET", "path": "/items/"},
            "result": "{\"status_code\": 200, \"body\": {...}}"
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
| `source` | string | The file/section used for the answer. |
| `tool_calls` | array | List of all tool calls made during the agentic loop. |
| `log` | object | Error information. Empty `{}` on success. |

### Tool Call Structure

Each entry in `tool_calls` contains:

| Field | Type | Description |
|-------|------|-------------|
| `tool` | string | Name of the tool used (`read_file`, `list_files`, or `query_api`) |
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
3. **Tool Schemas** — OpenAI function-calling format for `read_file`, `list_files`, and `query_api`
4. **AgentState Class** — Manages message history and tool call tracking
5. **Agentic Loop** — Executes tool calls and feeds results back to LLM
6. **Path Security** — Prevents directory traversal attacks
7. **API Authentication** — Uses `LMS_API_KEY` for backend requests

### Implementation Details

- **HTTP Client:** `httpx` with 60-second timeout for LLM, 30-second for API
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

### `query_api` (Task 3)

Call the backend API to query system data or get live information.

**Parameters:**
- `method` (string, required) — HTTP method (GET, POST, PUT, DELETE)
- `path` (string, required) — API endpoint path (e.g., `/items/`, `/analytics/completion-rate`)
- `body` (string, optional) — JSON request body for POST/PUT requests

**Returns:** JSON string with `status_code` and `body` fields

**Authentication:** Uses `LMS_API_KEY` from environment variables with Bearer token auth

**Example:**
```json
{
    "tool": "query_api",
    "args": {"method": "GET", "path": "/items/"},
    "result": "{\"status_code\": 200, \"body\": [{\"id\": 1, ...}]}"
}
```

## System Prompt

The agent uses this system prompt to guide the LLM:

```
You are a helpful documentation and system assistant. You have access to tools that let you:
1. Read files and list directories in a project repository (for documentation and source code)
2. Query the backend API for live system data

Project structure:
- Wiki documentation: wiki/
- Backend code: backend/app/
- API routers: backend/app/routers/ (items.py, interactions.py, analytics.py, learners.py, pipeline.py)
- Agent code: agent.py

When answering questions:
- For wiki/documentation questions: Use list_files to discover files, then read_file to examine contents
- For source code questions: Use read_file to read the relevant source files. For API routers, check backend/app/routers/
- For system facts (framework, ports, status codes) or data queries (item count, analytics): Use query_api to call the backend
- Always cite your source at the end of your answer in the format: Source: wiki/file.md#section-name
- If a section doesn't have an anchor, just use the file path

Think step by step. Call tools when you need information, then use the results to answer.
```

## Tool Selection Strategy

The LLM decides which tool to use based on the question type:

| Question Type | Tool(s) | Example |
|---------------|---------|---------|
| Wiki documentation | `list_files`, `read_file` | "What does the wiki say about SSH?" |
| Source code structure | `list_files`, `read_file` | "What routers exist in the backend?" |
| System facts | `query_api`, `read_file` | "What framework does the backend use?" |
| Live data | `query_api` | "How many items are in the database?" |
| API behavior | `query_api` | "What status code does /items/ return?" |
| Bug diagnosis | `query_api`, `read_file` | "Why does /analytics/completion-rate crash?" |

## Testing

### Manual Testing

```bash
# Test with tool usage
uv run agent.py "What files are in the wiki?"

# Test with file reading
uv run agent.py "How do you resolve a merge conflict?"

# Test query_api tool
uv run agent.py "How many items are in the database?"

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
- Tool usage (`query_api` for data questions)
- Tool usage (`read_file` for source code questions)
- Source field contains wiki path
- Log structure on success/error

## Troubleshooting

### Common Issues

**"LLM configuration incomplete"**
- Ensure `.env.agent.secret` exists with `LLM_API_KEY`, `LLM_API_BASE`, `LLM_MODEL`

**"LMS_API_KEY not configured"**
- Ensure `.env.docker.secret` exists with `LMS_API_KEY`
- The agent reads this from environment variables

**"Request timed out"**
- Check network connectivity
- Verify `LLM_API_BASE` is accessible
- The LLM may be overloaded (try a different model)

**"429 Too Many Requests"**
- You've hit rate limits (common with free-tier models)
- Wait and retry, or switch to a different model

**"Failed to parse JSON"**
- The API returned malformed response
- Check if the API endpoint is correct

**Agent doesn't use tools**
- Some questions don't require tools (simple math, general knowledge)
- Ask about project-specific documentation to trigger tool usage

**Agent uses wrong tool**
- Check if the system prompt clearly distinguishes when to use each tool
- Improve tool descriptions in `TOOL_SCHEMAS`

## Lessons Learned (Task 3)

1. **Environment Variables**: The agent must read ALL configuration from environment variables (`LLM_API_KEY`, `LLM_API_BASE`, `LLM_MODEL`, `LMS_API_KEY`, `AGENT_API_BASE_URL`). Hardcoding values will cause the autochecker to fail.

2. **Tool Descriptions Matter**: The LLM relies on clear tool descriptions to decide which tool to use. Adding "Do NOT use for wiki documentation questions" to `query_api` helped prevent confusion.

3. **Project Structure in System Prompt**: Including the project structure (wiki/, backend/app/, backend/app/routers/) in the system prompt helps the LLM know where to look for specific files.

4. **Error Handling**: The `query_api` tool returns errors as JSON with `status_code: 0` so the LLM can understand what went wrong and potentially retry or explain the issue.

5. **Authentication**: Two separate API keys are used:
   - `LLM_API_KEY` — authenticates with the LLM provider
   - `LMS_API_KEY` — authenticates with the backend API
   Mixing them up causes 401 errors.

6. **Timeout Handling**: Different timeouts for LLM (60s) and API (30s) calls prevent the agent from hanging on slow responses.

## Final Evaluation Score

Run the benchmark with:
```bash
uv run run_eval.py
```

The benchmark tests 10 questions across all categories:
- Wiki lookup (questions 0-1)
- System facts (questions 2-3)
- Data queries (questions 4-5)
- Bug diagnosis (questions 6-7)
- Reasoning (questions 8-9)

**Current Status:** Iterating on failures. Check `plans/task-3.md` for detailed progress.
