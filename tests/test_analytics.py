"""
tests/test_analytics.py
========================
Unit tests for analytics modules.
"""

from __future__ import annotations

import io

import pandas as pd
import numpy as np
import pytest

from analytics.data_processor import load_dataset, suggest_joins
from analytics.statistical_analysis import (
    descriptive_stats,
    correlation_matrix,
    missing_value_report,
)


class TestDataProcessor:
    def test_load_csv(self):
        csv = "a,b,c\n1,2,3\n4,5,6\n"
        df, schema = load_dataset(csv.encode(), "test.csv")
        assert len(df) == 2
        assert schema["columns_count"] == 3

    def test_load_json(self):
        import json
        data = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]
        content = json.dumps(data).encode()
        df, schema = load_dataset(content, "test.json")
        assert len(df) == 2

    def test_suggest_joins(self):
        schemas = {
            "sales": {"columns": ["id", "region", "revenue"]},
            "customers": {"columns": ["id", "name", "region"]},
        }
        suggestions = suggest_joins(schemas)
        assert len(suggestions) >= 1
        common = suggestions[0]["common_columns"]
        assert "id" in common or "region" in common

    def test_unsupported_extension_raises(self):
        with pytest.raises(ValueError, match="Unsupported"):
            load_dataset(b"data", "file.parquet")


class TestStatisticalAnalysis:
    @pytest.fixture
    def df(self):
        rng = np.random.default_rng(0)
        return pd.DataFrame({
            "revenue": rng.uniform(100, 1000, 50),
            "units": rng.integers(1, 100, 50),
            "region": rng.choice(["A", "B", "C"], 50),
        })

    def test_descriptive_stats(self, df):
        stats = descriptive_stats(df)
        assert "revenue" in stats
        assert "variance" in stats

    def test_correlation_matrix(self, df):
        corr = correlation_matrix(df)
        assert "revenue" in corr
        assert corr["revenue"]["revenue"] == pytest.approx(1.0, abs=0.01)

    def test_missing_value_report(self, df):
        df.loc[0, "revenue"] = None
        report = missing_value_report(df)
        assert report["counts"]["revenue"] == 1
        assert report["total_rows"] == 50