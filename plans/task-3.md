# Plan for Task 3: The System Agent

## Overview

This task extends the Task 2 agent with a new `query_api` tool that allows the agent to query the deployed backend API. The agent will be able to answer both static system questions (framework, ports, status codes) and data-dependent queries (item count, scores).

## Implementation Steps

### 1. Add Environment Variables ✅

Need to read additional environment variables:
- `LMS_API_KEY` — from `.env.docker.secret` for backend API authentication
- `AGENT_API_BASE_URL` — base URL for the backend (default: `http://localhost:42002`)

These must be read from environment, not hardcoded, because the autochecker injects different values.

### 2. Define `query_api` Tool Schema ✅

Added a new tool schema to `TOOL_SCHEMAS` list with clear description:
- `method` — HTTP method (GET, POST, etc.)
- `path` — API endpoint path
- `body` — Optional JSON request body

### 3. Implement `query_api` Function ✅

The function:
- Reads `LMS_API_KEY` from environment
- Reads `AGENT_API_BASE_URL` from environment (default to `http://localhost:42002`)
- Makes HTTP request with Bearer token authentication
- Returns JSON string with `status_code` and `body`

### 4. Update System Prompt ✅

Updated the system prompt to guide the LLM on when to use which tool:
- `read_file` / `list_files` — for wiki documentation questions
- `query_api` — for system facts and data queries from the backend
- Added project structure to help LLM know where to look

### 5. Update AGENT.md Documentation ✅

Documented:
- The new `query_api` tool and its authentication
- How the LLM decides between wiki tools vs `query_api`
- Tool selection strategy table
- Lessons learned from implementation
- 400+ words total

### 6. Write Regression Tests ✅

Added 2 tests to `tests/test_agent.py`:
1. `test_agent_uses_query_api_for_data_question` — tests that data questions use `query_api`
2. `test_agent_uses_read_file_for_source_code_question` — tests that source code questions use `read_file`

### 7. Run Benchmark and Iterate 🔄

```bash
uv run run_eval.py
```

## Benchmark Progress

| Question | Topic | Status |
|----------|-------|--------|
| 0 | Wiki: protect branch | ✅ Passed |
| 1 | Wiki: SSH connection | ✅ Passed |
| 2 | Source: framework | ✅ Passed |
| 3 | Source: API routers | ❌ Failed — agent didn't use `list_files` on `backend/app/routers/` |
| 4 | Data: items count | ⏳ Pending |
| 5 | API: status code | ⏳ Pending |
| 6 | Bug: ZeroDivisionError | ⏳ Pending |
| 7 | Bug: TypeError | ⏳ Pending |
| 8 | Reasoning: request lifecycle | ⏳ Pending |
| 9 | Reasoning: ETL idempotency | ⏳ Pending |

## Iteration Strategy

### Issue: Question 3 Failure

**Problem:** Agent didn't use `list_files` on the routers directory.

**Fix Applied:**
- Updated `SYSTEM_PROMPT` to include project structure
- Added explicit mention of `backend/app/routers/` directory
- Added hint: "For API routers, check backend/app/routers/"

**Next Steps:**
1. Re-run `run_eval.py` to verify fix
2. If still failing, improve tool description for `list_files`
3. Consider adding more specific guidance about exploring directories

### Future Issues to Watch

1. **Question 4-5 (Data queries):** Ensure `query_api` is working with proper auth
2. **Question 6-7 (Bug diagnosis):** Agent needs to chain `query_api` + `read_file`
3. **Question 8-9 (Reasoning):** LLM judge evaluates quality of explanation

## Success Criteria

- [x] `query_api` tool defined and registered
- [x] Tool authenticates with `LMS_API_KEY`
- [x] Agent reads all config from environment variables
- [x] 2 new regression tests added
- [x] `AGENT.md` updated (400+ words)
- [ ] `run_eval.py` passes all 10 questions
- [ ] Autochecker bot benchmark passes
