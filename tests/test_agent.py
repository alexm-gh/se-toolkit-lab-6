"""Regression tests for agent.py CLI."""

import json
import subprocess
import sys
from pathlib import Path


def test_agent_returns_valid_json() -> None:
    """Test that agent.py outputs valid JSON with required fields."""
    project_root = Path(__file__).parent.parent

    result = subprocess.run(
        [
            sys.executable,
            "agent.py",
            "Answer only number, do not provide any else answer. 0b1111 in C++ is?",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=project_root,
    )

    assert result.returncode == 0, f"Agent failed with: {result.stderr}"
    assert result.stdout.strip(), "Agent produced no output"

    output = json.loads(result.stdout)

    # Assert required fields exist
    assert "answer" in output, "Missing 'answer' field"
    assert "tool_calls" in output, "Missing 'tool_calls' field"
    assert "source" in output, "Missing 'source' field"
    assert "log" in output, "Missing 'log' field"

    # Assert field types
    assert isinstance(output["answer"], str), "'answer' should be a string"
    assert isinstance(output["tool_calls"], list), "'tool_calls' should be an array"
    assert isinstance(output["source"], str), "'source' should be a string"
    assert isinstance(output["log"], dict), "'log' should be a dict"

    # Assert answer is not empty
    assert output["answer"].strip(), "'answer' should not be empty"


def test_agent_uses_list_files_tool() -> None:
    """Test that agent.py uses list_files tool when asked about directory contents."""
    project_root = Path(__file__).parent.parent

    result = subprocess.run(
        [
            sys.executable,
            "agent.py",
            "What files are in the wiki directory?",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=project_root,
    )

    assert result.returncode == 0, f"Agent failed with: {result.stderr}"

    output = json.loads(result.stdout)

    # Assert tool_calls is not empty (agent should use list_files)
    assert len(output["tool_calls"]) > 0, "Expected agent to use at least one tool"

    # Assert list_files was used
    tools_used = [call["tool"] for call in output["tool_calls"]]
    assert "list_files" in tools_used, "Expected agent to use list_files tool"

    # Assert log is a dict
    assert isinstance(output["log"], dict), "'log' should be a dict"


def test_agent_uses_read_file_for_merge_conflict() -> None:
    """Test that agent.py uses read_file tool when asked about merge conflicts."""
    project_root = Path(__file__).parent.parent

    result = subprocess.run(
        [
            sys.executable,
            "agent.py",
            "How do you resolve a merge conflict?",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=project_root,
    )

    assert result.returncode == 0, f"Agent failed with: {result.stderr}"

    output = json.loads(result.stdout)

    # Assert tool_calls is not empty (agent should read files)
    assert len(output["tool_calls"]) > 0, "Expected agent to use at least one tool"

    # Assert read_file was used
    tools_used = [call["tool"] for call in output["tool_calls"]]
    assert "read_file" in tools_used, "Expected agent to use read_file tool"

    # Assert source field exists and points to a wiki file
    assert "source" in output, "Missing 'source' field"
    assert "wiki/" in output["source"], f"Source should reference a wiki file, got: {output['source']}"

    # Assert log is a dict (empty on success)
    assert isinstance(output["log"], dict), "'log' should be a dict"


def test_log_structure_on_success() -> None:
    """Test that log is empty dict on success."""
    project_root = Path(__file__).parent.parent

    result = subprocess.run(
        [
            sys.executable,
            "agent.py",
            "Answer only number: 2+2=?",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=project_root,
    )

    assert result.returncode == 0, f"Agent failed with: {result.stderr}"

    output = json.loads(result.stdout)

    # Assert log is a dict (empty on success)
    assert isinstance(output["log"], dict), "'log' should be a dict"
    assert output["log"] == {}, "Log should be empty dict on success"


def test_agent_uses_query_api_for_data_question() -> None:
    """Test that agent.py uses query_api tool when asked about database items."""
    project_root = Path(__file__).parent.parent

    result = subprocess.run(
        [
            sys.executable,
            "agent.py",
            "How many items are currently stored in the database? Query the running API to find out.",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=project_root,
    )

    assert result.returncode == 0, f"Agent failed with: {result.stderr}"

    output = json.loads(result.stdout)

    # Assert tool_calls is not empty (agent should query API)
    assert len(output["tool_calls"]) > 0, "Expected agent to use at least one tool"

    # Assert query_api was used
    tools_used = [call["tool"] for call in output["tool_calls"]]
    assert "query_api" in tools_used, f"Expected agent to use query_api tool, got: {tools_used}"

    # Assert log is a dict (empty on success)
    assert isinstance(output["log"], dict), "'log' should be a dict"


def test_agent_uses_read_file_for_source_code_question() -> None:
    """Test that agent.py uses read_file tool when asked about the backend framework."""
    project_root = Path(__file__).parent.parent

    result = subprocess.run(
        [
            sys.executable,
            "agent.py",
            "What Python web framework does this project's backend use? Read the source code to find out.",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=project_root,
    )

    assert result.returncode == 0, f"Agent failed with: {result.stderr}"

    output = json.loads(result.stdout)

    # Assert tool_calls is not empty (agent should read source code)
    assert len(output["tool_calls"]) > 0, "Expected agent to use at least one tool"

    # Assert read_file was used (not query_api for source code question)
    tools_used = [call["tool"] for call in output["tool_calls"]]
    assert "read_file" in tools_used, f"Expected agent to use read_file tool, got: {tools_used}"

    # Assert answer contains FastAPI
    assert "fastapi" in output["answer"].lower(), (
        f"Expected answer to contain 'FastAPI', got: {output['answer']}"
    )

    # Assert log is a dict (empty on success)
    assert isinstance(output["log"], dict), "'log' should be a dict"
