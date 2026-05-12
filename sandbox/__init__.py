"""Sandbox package: Docker-backed execution environment for LLM-authored code."""

from sandbox.container_manager import DockerSandbox, SandboxResult

__all__ = ["DockerSandbox", "SandboxResult"]
