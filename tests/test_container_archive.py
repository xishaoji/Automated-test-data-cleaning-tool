"""Unit tests for Docker archive file transfer helpers."""

from __future__ import annotations

import io
import tarfile
from pathlib import Path

from sandbox.container_manager import DockerSandbox


class FakeContainer:
    def __init__(self) -> None:
        self.archives: dict[str, bytes] = {}

    def put_archive(self, target_dir: str, data: bytes) -> None:
        self.archives[target_dir] = data

    def get_archive(self, container_path: str):
        file_name = Path(container_path).name
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w") as archive:
            payload = b"col\n1\n"
            info = tarfile.TarInfo(name=file_name)
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
        tar_buffer.seek(0)
        return [tar_buffer.getvalue()], {}


class TestDockerArchiveHelpers:
    def test_put_file_writes_tar_archive(self, tmp_path):
        source = tmp_path / "script.py"
        source.write_text("print('ok')", encoding="utf-8")
        container = FakeContainer()

        DockerSandbox._put_file(container, "/app", source, "script.py")

        with tarfile.open(fileobj=io.BytesIO(container.archives["/app"]), mode="r") as archive:
            member = archive.getmember("script.py")
            extracted = archive.extractfile(member)
            assert extracted is not None
            assert extracted.read().decode("utf-8") == "print('ok')"

    def test_copy_file_from_container_writes_destination(self, tmp_path):
        destination = tmp_path / "input.csv"

        DockerSandbox._copy_file_from_container(FakeContainer(), "/data/input.csv", destination)

        assert destination.read_text(encoding="utf-8") == "col\n1\n"
