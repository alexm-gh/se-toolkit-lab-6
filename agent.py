#!/usr/bin/env python3
"""Agent CLI that calls an LLM and returns a structured JSON answer.

Usage:
    uv run agent.py "Your question here"

Output (stdout):
    {"answer": "...", "tool_calls": [], "log": [...]}

All debug output goes to stderr.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx


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


def call_lllm(question: str) -> dict[str, Any]:
    """Call the LLM API and return the response."""
    # Get configuration from environment
    api_base = os.environ.get("LLM_API_BASE", "")
    api_key = os.environ.get("LLM_API_KEY", "")
    model = os.environ.get("LLM_MODEL", "")
    
    log_entries = []
    
    # Validate configuration
    if not api_base:
        log_entries.append({"message": "LLM_API_BASE not set", "code": "CONFIG_ERROR"})
        return {"answer": "", "tool_calls": [], "log": log_entries}
    
    if not api_key:
        log_entries.append({"message": "LLM_API_KEY not set", "code": "CONFIG_ERROR"})
        return {"answer": "", "tool_calls": [], "log": log_entries}
    
    if not model:
        log_entries.append({"message": "LLM_MODEL not set", "code": "CONFIG_ERROR"})
        return {"answer": "", "tool_calls": [], "log": log_entries}
    
    # Build the request
    url = f"{api_base}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": question}
        ],
        "max_tokens": 500,
    }
    
    print(f"Calling LLM at {url} with model {model}...", file=sys.stderr)
    
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, headers=headers, json=payload)
    except httpx.TimeoutException:
        log_entries.append({"message": "Request timed out after 60 seconds", "code": "TIMEOUT"})
        return {"answer": "", "tool_calls": [], "log": log_entries}
    except httpx.RequestError as e:
        log_entries.append({"message": f"Request failed: {str(e)}", "code": "NETWORK_ERROR"})
        return {"answer": "", "tool_calls": [], "log": log_entries}
    
    # Check for HTTP errors
    if response.status_code != 200:
        try:
            error_data = response.json()
            error_msg = error_data.get("error", {}).get("message", str(error_data))
            log_entries.append({"message": f"API error: {error_msg}", "code": str(response.status_code)})
        except json.JSONDecodeError:
            log_entries.append({"message": f"API error: {response.text}", "code": str(response.status_code)})
        return {"answer": "", "tool_calls": [], "log": log_entries}
    
    # Parse the response
    try:
        response_data = response.json()
    except json.JSONDecodeError as e:
        log_entries.append({"message": f"Failed to parse JSON response: {str(e)}", "code": "PARSE_ERROR"})
        return {"answer": "", "tool_calls": [], "log": log_entries}
    
    # Extract the answer
    try:
        answer = response_data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        log_entries.append({"message": f"Unexpected response structure: {str(e)}", "code": "STRUCTURE_ERROR"})
        return {"answer": "", "tool_calls": [], "log": log_entries}
    
    return {"answer": answer, "tool_calls": [], "log": log_entries}


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
    
    # Call the LLM
    result = call_lllm(question)
    
    # Output JSON to stdout
    print(json.dumps(result))


if __name__ == "__main__":
    main()
