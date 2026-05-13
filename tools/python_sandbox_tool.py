"""LangGraph tool that runs Pandas code in a hardened Docker sandbox."""

from __future__ import annotations

from typing import Annotated

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from core.exceptions import (
    SandboxExecutionError,
    SandboxTimeoutError,
    SandboxUnavailableError,
)
from sandbox.container_manager import DockerSandbox
from utils.logger import get_logger

logger = get_logger("tool.sandbox")

# Single sandbox manager per process; the Docker client is cheap to reuse.
_sandbox = DockerSandbox()


@tool("execute_python_code")
def execute_python_code(
    code: str,
    state: Annotated[dict, InjectedState],
) -> str:
    """Run Pandas code against the current session's CSV in an isolated Docker sandbox.

    Contract for the calling LLM:
      * A ``df`` (pandas.DataFrame) is preloaded from the user-uploaded CSV.
      * Do not call ``pd.read_csv`` / ``df.to_csv``; persistence is automatic.
      * Use ``print(...)`` to surface diagnostics back to the reasoning loop.
      * Any exception raised by your code is captured and returned as stderr.
    """

    csv_path = state.get("csv_file_path")
    if not csv_path:
        return "[system] No csv_file_path in state; please upload a CSV first."

    logger.info("invoking sandbox", extra={"csv_path": csv_path, "code_len": len(code)})
    try:
        result = _sandbox.run(code, csv_path)
    except SandboxUnavailableError as exc:
        logger.error("sandbox unavailable: %s", exc)
        return f"[sandbox-unavailable] {exc}"
    except SandboxTimeoutError as exc:
        logger.warning("sandbox timeout")
        return f"[sandbox-timeout] {exc}"
    except SandboxExecutionError as exc:
        logger.info("sandbox user-code error")
        # Re-use the structured formatter so the LLM sees stdout + stderr distinctly.
        stdout = (exc.stdout or "").strip()
        stderr = (exc.stderr or "").strip()
        return (
            f"[sandbox-error] {exc}\n"
            + (f"[stdout]\n{stdout}\n" if stdout else "")
            + (f"[stderr]\n{stderr}" if stderr else "")
        )

    return result.format_for_llm()
