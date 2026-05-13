"""Domain-specific exception hierarchy.

Keeping a small, explicit hierarchy lets callers (Streamlit UI, agent nodes,
tests) catch the right level of failure instead of stringifying every
``Exception``.
"""

from __future__ import annotations


class CopilotError(Exception):
    """Base class for all application-level errors."""


class SandboxError(CopilotError):
    """Raised when the Docker sandbox fails to prepare or execute code."""


class SandboxUnavailableError(SandboxError):
    """Docker daemon is unreachable or the sandbox image is missing."""


class SandboxExecutionError(SandboxError):
    """User (LLM) code executed inside the sandbox returned a non-zero status."""

    def __init__(self, message: str, *, stdout: str = "", stderr: str = "") -> None:
        super().__init__(message)
        self.stdout = stdout
        self.stderr = stderr


class SandboxTimeoutError(SandboxError):
    """Sandbox execution exceeded the configured wall-clock limit."""


class ProtocolParseError(CopilotError):
    """Raised for malformed or unsupported protocol payloads."""
