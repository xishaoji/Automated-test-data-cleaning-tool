"""Tests for Streamlit dataset-state helpers."""

from __future__ import annotations

import pandas as pd

from utils.data_session import build_dataset_schema, file_digest


class TestDataSessionHelpers:
    def test_file_digest_is_content_based(self):
        assert file_digest(b"abc") == file_digest(b"abc")
        assert file_digest(b"abc") != file_digest(b"abcd")

    def test_build_dataset_schema_contains_types_and_preview(self):
        df = pd.DataFrame({"device_id": ["A1", "A2"], "voltage": [3.2, 3.4]})
        schema = build_dataset_schema(df)
        assert "字段类型" in schema
        assert "device_id" in schema
        assert "voltage" in schema
        assert "A1" in schema
