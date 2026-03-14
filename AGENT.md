# Agent Documentation

## Overview

This agent provides a CLI interface to query Large Language Models (LLMs) and receive structured JSON responses. It handles the complete flow: parse user input, call the LLM API, and return formatted answers with error logging.

## Usage

### Basic Command

```bash
uv run agent.py "<your-question>"
```

### Examples

```bash
# Safe usage (recommended)
uv run agent.py "What is 2+2?"
uv run agent.py "What does REST stand for?"

# Alternative (use with caution - some questions may cause issues)
python agent.py "Explain HTTP status codes"
```

### Output

The agent outputs a single JSON line to stdout:

```json
{
    "answer": "LLM's response to your query",
    "tool_calls": [],
    "log": []
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
| `LLM_API_KEY` | Your API key from the LLM provider | `sk-...` |
| `LLM_API_BASE` | Base URL of the LLM API | `https://openrouter.ai/api/v1` |
| `LLM_MODEL` | Model identifier | `qwen/qwen3-coder-plus` |

### Recommended Configuration (OpenRouter)

```bash
LLM_API_KEY=<your-openrouter-api-key>
LLM_API_BASE=https://openrouter.ai/api/v1
LLM_MODEL=qwen/qwen3-coder-plus
```

**Get API Key:** Sign up at [openrouter.ai](https://openrouter.ai) and create an API key.

**Available Models:** Browse models at [openrouter.ai/models](https://openrouter.ai/models). Free tier options include:
- `qwen/qwen3-coder:free` — coding specialist
- `meta-llama/llama-3.3-70b-instruct:free` — general purpose
- `google/gemma-3n-e4b-it:free` — lightweight model

## Output Format

### Success Response

```json
{
    "answer": "The LLM's answer to your question",
    "tool_calls": [],
    "log": []
}
```

### Error Response

```json
{
    "answer": "",
    "tool_calls": [],
    "log": [
        {
            "message": "Error description",
            "code": "ERROR_CODE"
        }
    ]
}
```

### Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `answer` | string | The LLM's response. Empty if an error occurred. |
| `tool_calls` | array | Reserved for future implementation (Task 2). Currently always empty. |
| `log` | array | Error information. Empty on success. |

### Log Entry Structure

| Field | Type | Description |
|-------|------|-------------|
| `message` | string | Human-readable error description |
| `code` | string | Error code (e.g., `TIMEOUT`, `NETWORK_ERROR`, `404`, `429`) |

### Error Codes

| Code | Meaning |
|------|---------|
| `CONFIG_ERROR` | Missing or invalid environment configuration |
| `TIMEOUT` | Request exceeded 60-second limit |
| `NETWORK_ERROR` | Network/connection failure |
| `404`, `429`, etc. | HTTP error from API |
| `PARSE_ERROR` | Invalid JSON response from API |
| `STRUCTURE_ERROR` | Unexpected response structure |

## Architecture

### Flow

```
User Input → Parse CLI → Load Config → Validate → Call API → Parse Response → Output JSON
```

### Components

1. **CLI Parser** — Extracts question from `sys.argv[1]`
2. **Environment Loader** — Parses `.env.agent.secret` into `os.environ`
3. **Config Validator** — Checks required variables before making requests
4. **API Client** — Sends HTTP POST to LLM endpoint with timeout handling
5. **Response Parser** — Extracts answer from LLM response structure
6. **Error Handler** — Catches exceptions and logs with appropriate codes

### Implementation Details

- **HTTP Client:** `httpx` with 60-second timeout
- **Endpoint:** `POST {LLM_API_BASE}/chat/completions`
- **Request Format:** OpenAI-compatible chat completions API
- **Response Format:** Standard OpenAI-style response structure

## Extending the Agent

### Adding Tools (Task 2)

The `tool_calls` array is reserved for future implementation. When adding tools:
- Populate `tool_calls` with tool invocation details
- Implement tool execution logic
- Update the agentic loop to process tool results

### Custom Error Handling

To add new error types:
1. Catch the exception in `call_lllm()`
2. Append to `log_entries` with descriptive `message` and `code`
3. Return early with empty `answer`

## Testing

### Manual Testing

```bash
# Test basic functionality
uv run agent.py "What is 2+2?"

# Test error handling (invalid config)
mv .env.agent.secret .env.agent.secret.bak
uv run agent.py "test"

# Test with stderr suppressed
uv run agent.py "test" 2>/dev/null | python -m json.tool
```

### Regression Tests

Run the test suite to verify JSON output structure and error handling.

## Troubleshooting

### Common Issues

**"LLM_API_KEY not set"**
- Ensure `.env.agent.secret` exists and contains valid credentials

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
