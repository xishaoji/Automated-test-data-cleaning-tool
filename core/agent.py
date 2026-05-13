"""LangGraph agent orchestration for the test-log copilot."""

from __future__ import annotations

from collections.abc import Iterable

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from core.config import Settings, get_settings
from core.prompts import build_system_prompt
from core.state import DataCopilotState
from tools.protocol_parser import parse_communication_protocol
from tools.python_sandbox_tool import execute_python_code
from utils.logger import get_logger

logger = get_logger("agent")

_ERROR_TOKENS = ("sandbox-error", "sandbox-timeout", "Exception", "Error", "异常")


def is_tool_error(content: str) -> bool:
    """Return True when a tool result looks like a failure worth counting."""

    return any(token in content for token in _ERROR_TOKENS)


def consecutive_tool_errors(messages: Iterable[BaseMessage]) -> int:
    """Count consecutive failed tool results at the tail of ``messages``.

    The counter resets whenever we hit a successful tool message or a new
    human turn. Exposed as a free function so tests can drive it with fake
    messages without spinning up a full graph.
    """

    count = 0
    for msg in reversed(list(messages)):
        msg_type = getattr(msg, "type", "")
        if msg_type == "tool":
            if is_tool_error(str(getattr(msg, "content", ""))):
                count += 1
            else:
                break
        elif msg_type == "human":
            break
    return count


class LangGraphDataAgent:
    """Builds and exposes the LangGraph workflow.

    The class is deliberately cheap to construct (it just wires nodes), so
    callers can cache a compiled graph in ``st.session_state`` rather than
    rebuilding it per prompt.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._llm = ChatOpenAI(
            model=self._settings.llm_model_name,
            temperature=self._settings.llm_temperature,
            api_key=self._settings.openai_api_key or None,
            base_url=self._settings.openai_base_url or None,
        )
        self._tools = [execute_python_code, parse_communication_protocol]
        self._llm_with_tools = self._llm.bind_tools(self._tools)

    # --- nodes ------------------------------------------------------------

    async def reasoner_node(self, state: DataCopilotState) -> dict:
        """Core LLM reasoning step with a circuit breaker on repeated failures."""

        messages: list[BaseMessage] = list(state["messages"])

        if consecutive_tool_errors(messages) >= self._settings.max_error_retries:
            logger.warning(
                "circuit breaker tripped after %s errors", self._settings.max_error_retries
            )
            sos = AIMessage(
                content=(
                    "⚠️ **执行熔断**：沙盒代码连续失败，已停止自动重试。"
                    "请确认字段名或提供更明确的清洗规则，我再继续。"
                )
            )
            return {"messages": [sos]}

        system_prompt = build_system_prompt(
            schema=state["dataset_schema"],
            file_path=state["csv_file_path"],
        )
        full_messages: list[BaseMessage] = [SystemMessage(content=system_prompt), *messages]

        logger.info("reasoning", extra={"messages": len(full_messages)})
        response = await self._llm_with_tools.ainvoke(full_messages)
        if getattr(response, "tool_calls", None):
            logger.debug("tool calls: %s", response.tool_calls)
        return {"messages": [response]}

    # --- graph ------------------------------------------------------------

    def build_graph(self) -> CompiledStateGraph:
        workflow = StateGraph(DataCopilotState)
        workflow.add_node("reasoner", self.reasoner_node)
        workflow.add_node("tools", ToolNode(self._tools))

        workflow.add_edge(START, "reasoner")
        workflow.add_conditional_edges(
            "reasoner",
            tools_condition,
            {"tools": "tools", END: END},
        )
        workflow.add_edge("tools", "reasoner")
        return workflow.compile()
