# Task 2 Plan: The Documentation Agent

## Overview

Transform the Task 1 chatbot into a true **agent** with tools and an agentic loop. The agent can explore the project wiki, read files, and answer questions with citations.

---

## Part 1: Revise Log Structure (Foundation)

Before implementing tools, we need to fix the log structure from Task 1.

### Current Log Structure (Task 1)
```json
"log": [
    {"message": "Error description", "code": "ERROR_CODE"}
]
```

### New Log Structure (Task 2)
```json
"log": {
    "message": "Error description",
    "code": "ERROR_CODE",
    "response_code": 429
}
```

### Log Field Definitions

| Field | Type | Description |
|-------|------|-------------|
| `message` | string | Human-readable error description |
| `code` | string | Error category (e.g., `TIMEOUT`, `CONFIG_ERROR`) |
| `response_code` | int | HTTP status code from API, or `-1` for internal errors |

### Response Code Rules

| Scenario | `response_code` |
|----------|-----------------|
| Internal error (missing config, file not found) | `-1` |
| API returns HTTP error (401, 403, 429, 500) | Actual code from API |
| Success | `200` (or omitted if no error) |
| Network error (no response) | `-1` |

### Why This Change?

1. **Dictionary makes more sense** — There's only one error context per response, not multiple
2. **`response_code` helps debugging** — Distinguish between client errors (4xx) and server errors (5xx)
3. **Consistent with HTTP semantics** — Aligns with API response codes

---

## Part 2: Tool Definitions

### Tool Schemas (OpenAI Function-Calling Format)

```json
{
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Read a file from the project repository",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path from project root"
                }
            },
            "required": ["path"]
        }
    }
}
```

### Tool Implementations

| Tool | Parameters | Returns | Security |
|------|------------|---------|----------|
| `read_file` | `path: str` | File contents (string) | Block `..`, absolute paths |
| `list_files` | `path: str` | Newline-separated listing | Block `..`, absolute paths |

### Path Security

```python
def validate_path(path: str) -> bool:
    if ".." in path:
        return False
    if path.startswith("/"):
        return False
    return True
```

---

## Part 3: Agentic Loop

### Loop Structure

```
1. Send question + tool definitions to LLM
2. Parse response:
   - If tool_calls present → execute tools → add results to messages → goto 1
   - If no tool_calls → extract answer → output JSON → exit
3. Maximum 10 tool calls per question
```

### Message History Format

```python
messages = [
    {"role": "system", "content": SYSTEM_PROMPT},
    {"role": "user", "content": question},
    {"role": "assistant", "tool_calls": [...]},
    {"role": "tool", "tool_call_id": "...", "content": "..."},
    # ... repeat until final answer
]
```

### State Management

Use a class to track:
- Message history (`messages: list[dict]`)
- Tool call log (`tool_calls_log: list[dict]`)
- Last file read (for `source` field)

---

## Part 4: Output Format

### Success Response
```json
{
    "answer": "The answer from LLM",
    "source": "wiki/git-workflow.md#resolving-merge-conflicts",
    "tool_calls": [
        {
            "tool": "list_files",
            "args": {"path": "wiki"},
            "result": "file1.md\nfile2.md"
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

---

## Part 5: System Prompt Strategy

The system prompt should instruct the LLM to:
1. Use `list_files` to discover wiki files
2. Use `read_file` to examine file contents
3. Cite sources in the answer (format: `wiki/file.md#section`)
4. Think step by step

---

## Implementation Steps

1. **Revise log structure** — Change from array to dict, add `response_code`
2. **Define tool schemas** — Add `TOOL_SCHEMAS` constant
3. **Implement tools** — `read_file`, `list_files` with path validation
4. **Create AgentState class** — Manage message history and tool tracking
5. **Implement agentic loop** — `run_agentic_loop()` function
6. **Update output format** — Add `source` field, update `tool_calls` structure
7. **Update tests** — Match new log and output format

---

## Acceptance Criteria

- [ ] Log is a dictionary with `message`, `code`, `response_code`
- [ ] `read_file` and `list_files` tools are implemented
- [ ] Path security prevents directory traversal
- [ ] Agentic loop executes tool calls and feeds results back
- [ ] Maximum 10 tool calls per question
- [ ] Output includes `answer`, `source`, `tool_calls`, `log`
- [ ] 3 regression tests pass
