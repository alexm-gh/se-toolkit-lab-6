"""Regression tests for agent.py CLI."""

import json
import subprocess
import sys
from pathlib import Path


def test_agent_returns_valid_json() -> None:
    """Test that agent.py outputs valid JSON with required fields."""
    # Get the project root directory
    project_root = Path(__file__).parent.parent.parent.parent
    
    # Run agent.py as a subprocess
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
    
    # Assert process exited successfully
    assert result.returncode == 0, f"Agent failed with: {result.stderr}"
    
    # Assert stdout is not empty
    assert result.stdout.strip(), "Agent produced no output"
    
    # Parse JSON output
    output = json.loads(result.stdout)
    
    # Assert required fields exist
    assert "answer" in output, "Missing 'answer' field"
    assert "tool_calls" in output, "Missing 'tool_calls' field"
    
    # Assert field types
    assert isinstance(output["answer"], str), "'answer' should be a string"
    assert isinstance(output["tool_calls"], list), "'tool_calls' should be an array"
    
    # Assert answer is not empty
    assert output["answer"].strip(), "'answer' should not be empty"
