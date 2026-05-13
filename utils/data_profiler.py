"""Profiling helpers used by the sidebar data-health panel."""

from __future__ import annotations

import pandas as pd


def generate_profiling_report(df: pd.DataFrame) -> str:
    """Return a Markdown snippet summarising the uploaded dataset."""

    total_rows = len(df)
    missing = df.isna().sum()
    missing_cols = missing[missing > 0].sort_values(ascending=False)

    lines = [
        "### 📊 测试日志数据体检",
        f"- **总记录数**: {total_rows} 行",
        f"- **字段数**: {len(df.columns)} 列",
        f"- **内存占用**: {df.memory_usage(deep=True).sum() / 1024:.1f} KB",
    ]

    if total_rows == 0:
        lines.append("- **⚠️ 空文件**：未读取到任何行，请检查上传内容。")
        return "\n".join(lines)

    if not missing_cols.empty:
        lines.append("- **⚠️ 字段缺失情况**:")
        for col, count in missing_cols.items():
            lines.append(f"  - `{col}`: 缺失 {int(count)} 条 ({count / total_rows:.1%})")
    else:
        lines.append("- **✅ 字段完整度**: 未发现缺失。")

    dup_count = int(df.duplicated().sum())
    if dup_count:
        lines.append(f"- **♻️ 重复行**: {dup_count} 条 ({dup_count / total_rows:.1%})")

    return "\n".join(lines)
