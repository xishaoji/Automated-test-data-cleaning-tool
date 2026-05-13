"""Helpers for keeping Streamlit dataset state deterministic."""

from __future__ import annotations

import hashlib

import pandas as pd


def file_digest(raw_bytes: bytes) -> str:
    """Return a stable digest for uploaded file contents."""

    return hashlib.sha256(raw_bytes).hexdigest()


def build_dataset_schema(df: pd.DataFrame) -> str:
    """Render the compact schema snippet passed into the agent."""

    return (
        f"字段类型:\n{df.dtypes.to_string()}\n\n"
        f"前三行数据预览:\n{df.head(3).to_markdown(index=False)}"
    )
