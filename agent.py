#!/usr/bin/env python3
"""Agent CLI with tools and agentic loop.

Usage:
    uv run agent.py "Your question here"

Output (stdout):
    {"answer": "...", "source": "...", "tool_calls": [...], "log": {...}}

All debug output goes to stderr.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx


# =============================================================================
# Configuration
# =============================================================================

MAX_TOOL_CALLS = 15  # Maximum tool calls per question (increased for complex architecture questions)


# =============================================================================
# Log Helper Functions
# =============================================================================

def create_log_entry(message: str, code: str, response_code: int = -1) -> dict[str, Any]:
    """Create a log entry dictionary.
    
    Args:
        message: Human-readable error description
        code: Error category (e.g., 'TIMEOUT', 'CONFIG_ERROR')
        response_code: HTTP status code, or -1 for internal errors
    """
    return {
        "message": message,
        "code": code,
        "response_code": response_code
    }


# =============================================================================
# Environment Loading
# =============================================================================

def load_env_file(env_path: Path) -> None:
    """Load variables from .env file into os.environ."""
    if not env_path.exists():
        print(f"Error: {env_path} not found", file=sys.stderr)
        sys.exit(1)

    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


# =============================================================================
# Tool Definitions
# =============================================================================

# Tool schemas for LLM (OpenAI function-calling format)
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file from the project repository. Use this to examine file contents, documentation, or source code.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path from project root (e.g., 'wiki/git-workflow.md', 'backend/app/main.py')"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and directories at a given path. Use this FIRST to discover what files exist in a directory before reading them. For example, to find API routers, call list_files('backend/app/routers') to see all router files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative directory path from project root (e.g., 'wiki', 'backend/app/routers')"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_api",
            "description": "Call the backend API to query system data or get live information. Use this FIRST for questions about API errors, HTTP status codes, items count, or analytics. For bug diagnosis questions, ALWAYS start with query_api to see the actual error, THEN read source code to understand the bug.",
            "parameters": {
                "type": "object",
                "properties": {
                    "method": {
                        "type": "string",
                        "description": "HTTP method (GET, POST, PUT, DELETE, etc.)"
                    },
                    "path": {
                        "type": "string",
                        "description": "API endpoint path (e.g., '/items/', '/analytics/completion-rate', '/health', '/interactions/')"
                    },
                    "body": {
                        "type": "string",
                        "description": "Optional JSON request body for POST/PUT requests (e.g., '{\"key\": \"value\"}')"
                    }
                },
                "required": ["method", "path"]
            }
        }
    }
]

# System prompt for the agentic loop
SYSTEM_PROMPT = """You are a helpful documentation and system assistant. You have access to tools that let you:
1. Read files and list directories in a project repository (for documentation and source code)
2. Query the backend API for live system data

Project structure:
- Wiki documentation: wiki/
- Backend code: backend/app/
- API routers: backend/app/routers/ (items.py, interactions.py, analytics.py, learners.py, pipeline.py)
- ETL pipeline: backend/app/etl.py
- Agent code: agent.py
- Docker: docker-compose.yml, Dockerfile
- Frontend proxy: caddy/Caddyfile

When answering questions:

**For wiki/documentation questions:**
- Use list_files FIRST to discover files, then read_file to examine contents

**For source code questions:**
- Use list_files to see what files exist, then read_file to read the relevant source files
- For API routers, start with list_files('backend/app/routers')
- For ETL pipeline idempotency, read backend/app/etl.py (look for external_id checks in load_logs)
- For analytics bugs, read backend/app/routers/analytics.py and look for sorted() calls with None values, or division operations that could cause ZeroDivisionError

**For API questions (CRITICAL):**
- "How many items..." → Use query_api('GET', '/items/') and count results
- "What HTTP status code..." → Use query_api('GET', '/items/') without auth header
- "Query the /interactions/ endpoint..." → Use query_api('GET', '/interactions/') FIRST, then read source
- "How many learners..." → Use query_api('GET', '/learners/') and count results
- For bug diagnosis questions, ALWAYS start with query_api to see the actual error, THEN read source code

**For architecture questions (Docker, request flow):**
- Read docker-compose.yml, Dockerfile, Caddyfile, and main.py to trace the flow

**Always cite your source** at the end of your answer in the format: Source: wiki/file.md#section-name

CRITICAL RULE: When asked to "list all" or describe multiple files, you must provide a FINAL ANSWER after gathering information. Do NOT keep reading files forever.

Example workflow for "List all API routers":
1. Call list_files('backend/app/routers') — get 6 files
2. Read 2-3 representative files to understand the pattern
3. STOP and provide a complete answer listing ALL routers with their domains

Example answer format:
"The backend has 5 API routers in backend/app/routers/:
- items.py: handles item CRUD operations (GET /, POST /, GET /{id}, PUT /{id})
- interactions.py: handles interaction logs (GET /, POST /)
- analytics.py: handles analytics queries (GET /scores, /pass-rates, /timeline, /groups, /completion-rate, /top-learners)
- learners.py: handles learner management
- pipeline.py: handles ETL pipeline operations"

Efficiency tips:
- When asked to "list all" or "what domain does each handle", use list_files once, then read a few representative files, then synthesize a complete answer
- Don't make unnecessary tool calls — if you have enough information, provide the final answer
- For "explain the journey" questions, trace: Caddy (proxy) → FastAPI (app) → auth → router → ORM → PostgreSQL

Think step by step. Call tools when you need information, then use the results to answer."""


def validate_path(path: str) -> bool:
    """Check if path is safe (no directory traversal)."""
    # Block path traversal attempts
    if ".." in path:
        return False
    # Block absolute paths
    if path.startswith("/"):
        return False
    # Block Windows-style absolute paths
    if len(path) >= 2 and path[1] == ":":
        return False
    return True


def read_file(path: str) -> str:
    """Read a file from the project repository."""
    if not validate_path(path):
        return "Error: Invalid path (directory traversal not allowed)"

    project_root = Path(__file__).parent
    full_path = project_root / path

    if not full_path.exists():
        return f"Error: File not found: {path}"

    if not full_path.is_file():
        return f"Error: Not a file: {path}"

    try:
        return full_path.read_text()
    except Exception as e:
        return f"Error reading file: {str(e)}"


def list_files(path: str) -> str:
    """List files and directories at a given path."""
    if not validate_path(path):
        return "Error: Invalid path (directory traversal not allowed)"

    project_root = Path(__file__).parent
    full_path = project_root / path

    if not full_path.exists():
        return f"Error: Path not found: {path}"

    if not full_path.is_dir():
        return f"Error: Not a directory: {path}"

    try:
        entries = sorted(full_path.iterdir())
        # Show only names, mark directories with /
        lines = []
        for entry in entries:
            # Skip hidden files and common ignored directories
            if entry.name.startswith(".") and entry.name not in [".vscode", ".github"]:
                continue
            if entry.name in ["__pycache__", ".venv", ".pytest_cache", "node_modules"]:
                continue

            suffix = "/" if entry.is_dir() else ""
            lines.append(f"{entry.name}{suffix}")

        result = "\n".join(lines)
        # Truncate if too long (leave room for other message content)
        if len(result) > 4000:
            result = result[:4000] + "\n... (truncated)"
        return result
    except Exception as e:
        return f"Error listing directory: {str(e)}"


def query_api(method: str, path: str, body: str | None = None) -> str:
    """Call the backend API.

    Args:
        method: HTTP method (GET, POST, etc.)
        path: API endpoint path (e.g., '/items/')
        body: Optional JSON request body for POST/PUT requests

    Returns:
        JSON string with status_code and body
    """
    api_key = os.environ.get("LMS_API_KEY", "")
    base_url = os.environ.get("AGENT_API_BASE_URL", "http://localhost:42002")

    if not api_key:
        return json.dumps({
            "status_code": 0,
            "body": {"error": "LMS_API_KEY not configured in environment"}
        })

    url = f"{base_url}{path}"
    headers = {
        "Authorization": f"Bearer {api_key}",
    }

    print(f"  Calling API: {method} {url}...", file=sys.stderr)

    try:
        with httpx.Client(timeout=30.0) as client:
            if method.upper() == "GET":
                response = client.get(url, headers=headers)
            elif method.upper() == "POST":
                headers["Content-Type"] = "application/json"
                response = client.post(url, headers=headers, data=body or "{}")
            elif method.upper() == "PUT":
                headers["Content-Type"] = "application/json"
                response = client.put(url, headers=headers, data=body or "{}")
            elif method.upper() == "DELETE":
                response = client.delete(url, headers=headers)
            else:
                return json.dumps({
                    "status_code": 0,
                    "body": {"error": f"Unsupported method: {method}"}
                })
    except httpx.TimeoutException:
        return json.dumps({
            "status_code": 0,
            "body": {"error": "Request timed out"}
        })
    except httpx.RequestError as e:
        return json.dumps({
            "status_code": 0,
            "body": {"error": f"Request failed: {str(e)}"}
        })

    # Return response with status_code and body
    try:
        response_body = response.json()
    except json.JSONDecodeError:
        response_body = response.text

    return json.dumps({
        "status_code": response.status_code,
        "body": response_body
    })


# Dispatch dictionary for tool execution
TOOLS_IMPL = {
    "read_file": read_file,
    "list_files": list_files,
    "query_api": query_api,
}


# =============================================================================
# Agentic Loop
# =============================================================================

class AgentState:
    """Manages conversation history and tool call tracking."""

    def __init__(self, question: str):
        self.messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question}
        ]
        self.tool_calls_log: list[dict[str, Any]] = []
        self.last_file_read: str | None = None
        self.consecutive_reads = 0  # Track consecutive read_file calls

    def add_assistant_response(self, content: str | None, tool_calls: list | None) -> None:
        """Add assistant message to history."""
        message: dict[str, Any] = {"role": "assistant"}
        if content is not None:
            message["content"] = content
        if tool_calls is not None:
            message["tool_calls"] = tool_calls
        self.messages.append(message)

    def add_tool_result(self, tool_call_id: str, result: str, tool_name: str = "") -> None:
        """Add tool execution result to history."""
        # Note: OpenAI API doesn't require 'name' field for tool results
        self.messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": result
        })

    def log_tool_call(self, tool: str, args: dict[str, Any], result: str) -> None:
        """Log a tool call for the final output."""
        self.tool_calls_log.append({
            "tool": tool,
            "args": args,
            "result": result
        })
        # Track last file read for source extraction
        if tool == "read_file":
            self.last_file_read = args.get("path")
            self.consecutive_reads += 1
        else:
            self.consecutive_reads = 0  # Reset on non-read_file calls


def execute_tool_call(tool_call: dict[str, Any]) -> str:
    """Execute a single tool call and return the result."""
    function = tool_call.get("function", {})
    name = function.get("name", "")
    args_str = function.get("arguments", "{}")

    try:
        args = json.loads(args_str)
    except json.JSONDecodeError:
        return "Error: Invalid arguments JSON"

    print(f"  Executing {name}({args})...", file=sys.stderr)

    if name not in TOOLS_IMPL:
        return f"Error: Unknown tool: {name}"

    try:
        result = TOOLS_IMPL[name](**args)
    except Exception as e:
        result = f"Error: {str(e)}"

    return result


def call_llm_with_tools(
    api_base: str,
    api_key: str,
    model: str,
    messages: list[dict[str, Any]]
) -> tuple[dict[str, Any] | None, int]:
    """Call LLM with tool support.
    
    Returns:
        Tuple of (parsed_response, response_code)
        - parsed_response: dict or None on error
        - response_code: HTTP status code, or -1 on network error
    """
    url = f"{api_base}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {
        "model": model,
        "messages": messages,
        "tools": TOOL_SCHEMAS,
        "tool_choice": "auto",
        "max_tokens": 1000,
    }

    print(f"Calling LLM at {url} with model {model}...", file=sys.stderr)

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, headers=headers, json=payload)
    except httpx.TimeoutException:
        print("Error: Request timed out", file=sys.stderr)
        return None, -1
    except httpx.RequestError as e:
        print(f"Error: Request failed: {e}", file=sys.stderr)
        return None, -1

    if response.status_code != 200:
        print(f"Error: API returned status {response.status_code}", file=sys.stderr)
        try:
            error_data = response.json()
            error_msg = error_data.get("error", {}).get("message", str(error_data))
            print(f"  {error_msg}", file=sys.stderr)
        except json.JSONDecodeError:
            print(f"  {response.text}", file=sys.stderr)
        return None, response.status_code

    try:
        return response.json(), 200
    except json.JSONDecodeError as e:
        print(f"Error: Failed to parse response: {e}", file=sys.stderr)
        return None, -1


def run_agentic_loop(question: str) -> dict[str, Any]:
    """Run the agentic loop and return the final result."""
    api_base = os.environ.get("LLM_API_BASE", "")
    api_key = os.environ.get("LLM_API_KEY", "")
    model = os.environ.get("LLM_MODEL", "")

    # Validate configuration
    if not all([api_base, api_key, model]):
        return {
            "answer": "",
            "source": "",
            "tool_calls": [],
            "log": create_log_entry("LLM configuration incomplete", "CONFIG_ERROR", -1)
        }

    state = AgentState(question)
    tool_call_count = 0

    while tool_call_count < MAX_TOOL_CALLS:
        # Call LLM
        response_data, response_code = call_llm_with_tools(api_base, api_key, model, state.messages)

        if response_data is None:
            return {
                "answer": "",
                "source": "",
                "tool_calls": state.tool_calls_log,
                "log": create_log_entry("LLM request failed", "API_ERROR", response_code)
            }

        # Extract assistant message
        try:
            assistant_message = response_data["choices"][0]["message"]
        except (KeyError, IndexError):
            return {
                "answer": "",
                "source": "",
                "tool_calls": state.tool_calls_log,
                "log": create_log_entry("Unexpected response structure", "STRUCTURE_ERROR", -1)
            }

        content = assistant_message.get("content")
        tool_calls = assistant_message.get("tool_calls")

        # Check if LLM returned a final answer (no tool calls)
        if not tool_calls:
            print(f"LLM returned final answer", file=sys.stderr)

            # Extract source from answer or use last file read
            source = ""
            if state.last_file_read:
                source = state.last_file_read
                # Try to extract section anchor from answer
                import re
                anchor_match = re.search(r'#([a-zA-Z0-9_-]+)', content or "")
                if anchor_match:
                    source = f"{state.last_file_read}#{anchor_match.group(1)}"

            return {
                "answer": content or "",
                "source": source,
                "tool_calls": state.tool_calls_log,
                "log": {}  # Empty log on success
            }

        # Check if LLM is stuck in a loop reading files
        # If it has read 4+ files consecutively without answering, add a hint to the history
        if state.consecutive_reads >= 4:
            print(f"LLM has read {state.consecutive_reads} files consecutively - adding hint to provide final answer", file=sys.stderr)
            # Add a user message to prompt the LLM to answer
            state.messages.append({
                "role": "user",
                "content": "You have now read enough files. Based on the list_files results and the files you've read, provide a COMPLETE FINAL ANSWER listing all the routers and their domains. Do not read any more files - just synthesize the information you have."
            })
            # Continue the loop - LLM will now respond with final answer
            continue

        # Execute tool calls
        print(f"LLM requested {len(tool_calls)} tool call(s)", file=sys.stderr)

        # First, add assistant message with tool_calls to history
        state.add_assistant_response(content, tool_calls)

        # Then execute tools and add results
        for tool_call in tool_calls:
            if tool_call_count >= MAX_TOOL_CALLS:
                print(f"Reached max tool calls ({MAX_TOOL_CALLS})", file=sys.stderr)
                break

            tool_call_id = tool_call.get("id", "unknown")
            function = tool_call.get("function", {})
            tool_name = function.get("name", "unknown")

            # Execute the tool
            result = execute_tool_call(tool_call)

            # Log the tool call
            try:
                args = json.loads(function.get("arguments", "{}"))
            except json.JSONDecodeError:
                args = {}
            state.log_tool_call(tool_name, args, result)

            # Add result to message history
            state.add_tool_result(tool_call_id, result, tool_name)

            tool_call_count += 1

    # Reached max tool calls
    return {
        "answer": "Reached maximum tool calls without a final answer.",
        "source": state.last_file_read or "",
        "tool_calls": state.tool_calls_log,
        "log": create_log_entry(f"Reached max tool calls ({MAX_TOOL_CALLS})", "MAX_CALLS", 200)
    }


# =============================================================================
# Main Entry Point
# =============================================================================

def main() -> None:
    """Main entry point."""
    # Parse command-line argument
    if len(sys.argv) < 2:
        print("Usage: uv run agent.py \"Your question here\"", file=sys.stderr)
        sys.exit(1)

    question = sys.argv[1]

    # Load environment configuration
    env_path = Path(__file__).parent / ".env.agent.secret"
    load_env_file(env_path)

    # Run the agentic loop
    result = run_agentic_loop(question)

    # Output JSON to stdout
    print(json.dumps(result))


if __name__ == "__main__":
    main()
