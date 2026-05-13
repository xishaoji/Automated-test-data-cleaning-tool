"""Tests for utils.data_profiler."""

from __future__ import annotations

import pandas as pd

from utils.data_profiler import generate_profiling_report


class TestProfilingReport:
    def test_empty_df(self):
        df = pd.DataFrame({"a": pd.Series([], dtype="float64")})
        report = generate_profiling_report(df)
        assert "空文件" in report

    def test_no_missing(self):
        df = pd.DataFrame({"x": [1, 2, 3], "y": ["a", "b", "c"]})
        report = generate_profiling_report(df)
        assert "✅" in report
        assert "3 行" in report

    def test_missing_reported(self):
        df = pd.DataFrame({"x": [1, None, 3], "y": [None, None, "c"]})
        report = generate_profiling_report(df)
        assert "`y`" in report
        assert "66.7%" in report

    def test_duplicates_reported(self):
        df = pd.DataFrame({"x": [1, 1, 2]})
        report = generate_profiling_report(df)
        assert "重复行" in report
