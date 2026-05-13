"""Tests for agent-level logic (circuit breaker, prompt building)."""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from core.agent import consecutive_tool_errors, is_tool_error
from core.prompts import build_system_prompt


class TestIsToolError:
    def test_detects_sandbox_error(self):
        assert is_tool_error("[sandbox-error] something went wrong")

    def test_detects_exception(self):
        assert is_tool_error("KeyError: 'voltage'")
        assert is_tool_error("Exception in thread")

    def test_success_not_flagged(self):
        assert not is_tool_error("[stdout]\nwrote 100 rows\n[exit_code] 0")


class TestConsecutiveToolErrors:
    def test_no_messages(self):
        assert consecutive_tool_errors([]) == 0

    def test_single_error(self):
        msgs = [
            HumanMessage(content="clean data"),
            AIMessage(content="", tool_calls=[{"id": "1", "name": "x", "args": {}}]),
            ToolMessage(content="[sandbox-error] boom", tool_call_id="1"),
        ]
        assert consecutive_tool_errors(msgs) == 1

    def test_three_errors_trips_breaker(self):
        msgs = [HumanMessage(content="go")]
        for i in range(3):
            msgs.append(AIMessage(content="", tool_calls=[{"id": str(i), "name": "x", "args": {}}]))
            msgs.append(ToolMessage(content="Exception: fail", tool_call_id=str(i)))
        assert consecutive_tool_errors(msgs) >= 3

    def test_success_resets_counter(self):
        msgs = [
            HumanMessage(content="go"),
            AIMessage(content="", tool_calls=[{"id": "1", "name": "x", "args": {}}]),
            ToolMessage(content="Exception: fail", tool_call_id="1"),
            AIMessage(content="", tool_calls=[{"id": "2", "name": "x", "args": {}}]),
            ToolMessage(content="[stdout]\nok\n[exit_code] 0", tool_call_id="2"),
            AIMessage(content="", tool_calls=[{"id": "3", "name": "x", "args": {}}]),
            ToolMessage(content="Exception: fail again", tool_call_id="3"),
        ]
        assert consecutive_tool_errors(msgs) == 1


class TestBuildSystemPrompt:
    def test_contains_schema(self):
        prompt = build_system_prompt(schema="col1: int64", file_path="/data/x.csv")
        assert "col1: int64" in prompt
        assert "/data/x.csv" in prompt

    def test_contains_safety_clauses(self):
        prompt = build_system_prompt(schema="", file_path="")
        assert "execute_python_code" in prompt
        assert "parse_communication_protocol" in prompt
