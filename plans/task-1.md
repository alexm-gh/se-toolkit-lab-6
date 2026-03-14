# Task 1 Plan: Call an LLM from Code

## LLM Provider & Model

**Primary Model:** `qwen/qwen3-coder-plus` via OpenRouter

- Provider: OpenRouter (https://openrouter.ai)
- API Base: `https://openrouter.ai/api/v1`
- Model: `qwen/qwen3-coder-plus` (no `:free` suffix — works without rate limiting currently)

**Fallback Models** (if primary is unavailable):

- `qwen/qwen3-coder:free` — 480B parameter coder model (free tier)
- `meta-llama/llama-3.3-70b-instruct:free` — general purpose (free tier)
- `nousresearch/hermes-3-llama-3.1-405b:free` — largest free model

## Environment Setup

**Configuration File:** `.env.agent.secret` (in project root)

Required variables:

```
LLM_API_KEY=<openrouter-api-key>
LLM_API_BASE=https://openrouter.ai/api/v1
LLM_MODEL=qwen/qwen3-coder-plus
```

The agent loads these variables at startup using a simple key=value parser (same pattern as `run_eval.py`).

## CLI Interface

**Usage:**

```bash
uv run agent.py "<question>"
```

**Argument Parsing:**

- Single argument: the user's question (string)
- If no argument provided: print usage hint to stderr
- If multiple arguments: use only the first one

**Output:**

- stdout: single-line JSON with `answer`, `tool_calls`, `log`
- stderr: all debug/progress messages

## API Communication

**Endpoint:** `POST {LLM_API_BASE}/chat/completions`

**Headers:**

```python
{
    "Content-Type": "application/json",
    "Authorization": f"Bearer {LLM_API_KEY}"
}
```

**Request Body:**

```python
{
    "model": LLM_MODEL,
    "messages": [{"role": "user", "content": "<question>"}],
    "max_tokens": 500
}
```

## Response Handling

**Success Case:**

- Extract: `response["choices"][0]["message"]["content"]`
- Output: `{"answer": "<content>", "tool_calls": [], "log": []}`

**Error Cases:**

| Error Type | Detection | Response |
|------------|-----------|----------|
| Missing config | Empty env var | `log: [{message: "... not set", code: "CONFIG_ERROR"}]` |
| Timeout | `httpx.TimeoutException` | `log: [{message: "Request timed out...", code: "TIMEOUT"}]` |
| Network error | `httpx.RequestError` | `log: [{message: "Request failed: ...", code: "NETWORK_ERROR"}]` |
| HTTP error | `status_code != 200` | `log: [{message: "API error: ...", code: "<status>"}]` |
| Parse error | `json.JSONDecodeError` | `log: [{message: "Failed to parse...", code: "PARSE_ERROR"}]` |
| Structure error | Missing `choices[0].message.content` | `log: [{message: "Unexpected response...", code: "STRUCTURE_ERROR"}]` |

**Output JSON Structure:**

```json
{
    "answer": "String",
    "tool_calls": [],
    "log": [
        {"message": "String", "code": "String"}
    ]
}
```

## Implementation Steps

1. **Parse CLI arguments** — use `sys.argv[1]` for the question
2. **Load environment** — parse `.env.agent.secret` into `os.environ`
3. **Validate configuration** — check `LLM_API_BASE`, `LLM_API_KEY`, `LLM_MODEL`
4. **Build HTTP request** — construct URL, headers, and payload
5. **Send request with timeout** — use `httpx.Client` with 60s timeout
6. **Handle errors** — catch exceptions, log with appropriate codes
7. **Parse response** — extract answer from `choices[0].message.content`
8. **Output JSON** — print to stdout, debug to stderr

## Testing Strategy

**Manual Testing:**

```bash
uv run agent.py "What is 2+2?"
uv run agent.py "What does REST stand for?"
```

**Regression Test:**

- Run `agent.py` as subprocess
- Parse stdout as JSON
- Assert `answer` field exists and is non-empty
- Assert `tool_calls` field exists and is an array
- Assert `log` field exists

## Acceptance Criteria Checklist

- [x] Uses LLM provider (OpenRouter + Qwen)
- [x] Reads credentials from `.env.agent.secret`
- [x] CLI accepts question as argument
- [x] Outputs valid JSON with required fields
- [x] Handles errors gracefully with logging
- [ ] Plan document created (`plans/task-1.md`)
- [ ] Agent implemented (`agent.py`)
- [ ] Documentation written (`AGENT.md`)
- [ ] Regression test exists
