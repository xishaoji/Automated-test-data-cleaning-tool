"""Hardened Docker sandbox for executing LLM-generated Pandas code.

Threat model
------------
We assume the generated code is *not* adversarial but *may* be buggy, touch
unrelated files, or loop forever. Concretely we enforce:

* No network (``network_disabled=True``).
* Read-only root filesystem plus a small writable ``tmpfs`` for ``/tmp``.
* Dropped Linux capabilities and ``no-new-privileges``.
* Hard CPU quota, memory limit, PID limit.
* Wall-clock timeout (``Settings.sandbox_timeout_seconds``); on timeout we
  forcibly kill the container.
* Per-call isolated host mount: only the target CSV is mounted read-write,
  nothing else under ``data/``.

The wrapper script injected into the container also uses ``textwrap.indent``
so the LLM code always parses regardless of its original indentation —
previous versions silently produced broken Python when the model emitted
already-indented blocks.
"""

from __future__ import annotations

import contextlib
import shutil
import tempfile
import textwrap
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

import docker
from docker.errors import APIError, ContainerError, DockerException, ImageNotFound, NotFound

from core.config import Settings, get_settings
from core.exceptions import (
    SandboxExecutionError,
    SandboxTimeoutError,
    SandboxUnavailableError,
)
from utils.logger import get_logger

logger = get_logger("sandbox")


@dataclass(frozen=True)
class SandboxResult:
    """Structured result of a sandbox run.

    Splitting stdout/stderr lets the agent reason about partial output even
    when the script ultimately fails.
    """

    stdout: str
    stderr: str
    exit_code: int

    @property
    def ok(self) -> bool:
        return self.exit_code == 0

    def format_for_llm(self) -> str:
        """Render a concise string suitable for feeding back into the LLM."""

        parts: list[str] = []
        if self.stdout:
            parts.append(f"[stdout]\n{self.stdout.strip()}")
        if self.stderr:
            parts.append(f"[stderr]\n{self.stderr.strip()}")
        parts.append(f"[exit_code] {self.exit_code}")
        return "\n".join(parts)


_WRAPPER_TEMPLATE = """\
import sys
import traceback
import pandas as pd  # noqa: F401  (kept in namespace for the user snippet)

INPUT_PATH = "/data/input.csv"
OUTPUT_PATH = "/data/input.csv"  # overwrite in place to stay compatible with the UI


def _run() -> None:
    df = pd.read_csv(INPUT_PATH)
    # --- BEGIN USER CODE ---
{user_code}
    # --- END USER CODE ---
    if "df" in locals() and isinstance(df, pd.DataFrame):
        df.to_csv(OUTPUT_PATH, index=False)
        print("[sandbox] wrote", len(df), "rows ->", OUTPUT_PATH)


if __name__ == "__main__":
    try:
        _run()
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        sys.exit(1)
"""


class DockerSandbox:
    """Thin wrapper around the Docker SDK tuned for one-shot code execution."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        try:
            self._client = docker.from_env()
            # Fail fast if the daemon isn't actually reachable.
            self._client.ping()
        except DockerException as exc:  # pragma: no cover - depends on host
            logger.error("Docker daemon unreachable: %s", exc)
            self._client = None

    # --- public API -------------------------------------------------------

    @property
    def is_ready(self) -> bool:
        return self._client is not None

    def run(self, python_code: str, dataframe_csv_path: str) -> SandboxResult:
        """Execute ``python_code`` against the CSV at ``dataframe_csv_path``.

        Raises
        ------
        SandboxUnavailableError
            Docker daemon is not running or the image is missing.
        SandboxTimeoutError
            Wall-clock timeout exceeded.
        SandboxExecutionError
            The user code ran but returned a non-zero exit code.
        """

        if not self._client:
            raise SandboxUnavailableError("Docker daemon is not available on the host")

        source = Path(dataframe_csv_path).resolve()
        if not source.is_file():
            raise SandboxUnavailableError(f"Input CSV not found: {source}")

        wrapper = _WRAPPER_TEMPLATE.format(user_code=textwrap.indent(python_code, "    "))
        logger.debug("sandbox wrapper script:\n%s", wrapper)

        # Per-call scratch dir keeps concurrent runs isolated.
        workdir = Path(tempfile.mkdtemp(prefix="copilot-sbx-"))
        script_path = workdir / "script.py"
        data_dir = workdir / "data"
        data_dir.mkdir()
        input_path = data_dir / "input.csv"

        script_path.write_text(wrapper, encoding="utf-8")
        shutil.copyfile(source, input_path)

        container_name = f"copilot-sbx-{uuid.uuid4().hex[:10]}"
        try:
            result = self._run_container(container_name, workdir)
        finally:
            # Clean up scratch dir but first sync the (possibly modified) CSV back.
            if input_path.is_file():
                shutil.copyfile(input_path, source)
            shutil.rmtree(workdir, ignore_errors=True)

        if not result.ok:
            raise SandboxExecutionError(
                f"Sandbox exited with code {result.exit_code}",
                stdout=result.stdout,
                stderr=result.stderr,
            )
        return result

    # --- internals --------------------------------------------------------

    def _run_container(self, name: str, workdir: Path) -> SandboxResult:
        assert self._client is not None
        settings = self._settings
        host_config = {
            "image": settings.sandbox_image,
            "name": name,
            "command": ["python", "/app/script.py"],
            "volumes": {
                str(workdir / "data"): {"bind": "/data", "mode": "rw"},
                str(workdir / "script.py"): {"bind": "/app/script.py", "mode": "ro"},
            },
            "working_dir": "/app",
            "network_disabled": True,
            "mem_limit": settings.sandbox_memory,
            "memswap_limit": settings.sandbox_memory,  # disallow swap growth
            "cpu_period": settings.sandbox_cpu_period,
            "cpu_quota": settings.sandbox_cpu_quota,
            "pids_limit": settings.sandbox_pids_limit,
            "read_only": True,
            "tmpfs": {"/tmp": "size=32m,mode=1777"},
            "security_opt": ["no-new-privileges:true"],
            "cap_drop": ["ALL"],
            "detach": True,
            "stdout": True,
            "stderr": True,
        }

        try:
            container = self._client.containers.run(**host_config)
        except ImageNotFound as exc:
            raise SandboxUnavailableError(
                f"Sandbox image '{settings.sandbox_image}' not found. "
                "Build it with `docker build -t pandas-sandbox:latest -f sandbox/Dockerfile .`"
            ) from exc
        except (APIError, ContainerError) as exc:
            raise SandboxUnavailableError(f"Docker API error while starting sandbox: {exc}") from exc

        start = time.monotonic()
        timeout = self._settings.sandbox_timeout_seconds

        # ``wait`` with timeout cleanly returns {'StatusCode': int}; if it
        # times out we kill the container so the image + volume handles are
        # released.
        watchdog = threading.Event()

        def _kill_on_timeout() -> None:
            if watchdog.wait(timeout):
                return
            try:
                container.kill()
                logger.warning("sandbox %s killed after %ss", name, timeout)
            except (NotFound, APIError):  # pragma: no cover - race with normal exit
                pass

        killer = threading.Thread(target=_kill_on_timeout, daemon=True)
        killer.start()

        try:
            status = container.wait(timeout=timeout + 5)
            watchdog.set()
        except Exception as exc:  # noqa: BLE001 - docker-py surfaces many error types here
            watchdog.set()
            with contextlib.suppress(NotFound, APIError):
                container.kill()
            raise SandboxTimeoutError(
                f"Sandbox execution exceeded {timeout}s"
            ) from exc

        elapsed = time.monotonic() - start
        exit_code = int(status.get("StatusCode", -1))

        stdout = container.logs(stdout=True, stderr=False).decode("utf-8", errors="replace")
        stderr = container.logs(stdout=False, stderr=True).decode("utf-8", errors="replace")

        logger.info(
            "sandbox run finished",
            extra={"container": name, "exit_code": exit_code, "elapsed_s": round(elapsed, 3)},
        )

        with contextlib.suppress(NotFound, APIError):
            container.remove(force=True)

        return SandboxResult(stdout=stdout, stderr=stderr, exit_code=exit_code)


# Backwards-compatible shim so callers that previously imported the old class
# keep working while we migrate.
__all__ = ["DockerSandbox", "SandboxResult"]
