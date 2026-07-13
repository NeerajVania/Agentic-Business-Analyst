import json
from pathlib import Path

import pandas as pd
import pytest

from agents.state import AgentState
from agents.data_analysis_agent import data_analysis_agent
from agents.anomaly_detection_agent import anomaly_detection_agent
from agents.visualization_agent import visualization_agent
from agents.report_agent import report_agent, _render_html, _render_markdown


@pytest.fixture
def sample_df() -> pd.DataFrame:
    import numpy as np
    rng = np.random.default_rng(42)
    return pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=50, freq="D"),
        "region": rng.choice(["North", "South", "East", "West"], 50),
        "revenue": rng.uniform(10_000, 100_000, 50),
        "units": rng.integers(10, 500, 50),
    })


@pytest.fixture
def base_state(sample_df) -> AgentState:
    return AgentState(
        user_query="Why did revenue drop last month?",
        session_id="test-session-001",
        dataset_ids=["ds1"],
        dataframes={"sales": sample_df},
        dataset_schemas={
            "sales": {
                "columns": sample_df.columns.tolist(),
                "dtypes": sample_df.dtypes.astype(str).to_dict(),
            }
        },
        errors=[],
        metadata={},
    )


class TestDataAnalysisAgent:
    def test_returns_analysis_results(self, base_state):
        result = data_analysis_agent(base_state)
        assert "analysis_results" in result
        assert "sales" in result["analysis_results"]

    def test_kpi_extraction(self, base_state):
        result = data_analysis_agent(base_state)
        assert "kpi_summary" in result
        assert isinstance(result["kpi_summary"], dict)

    def test_no_dataframes(self):
        state = AgentState(user_query="test", session_id="s", errors=[])
        result = data_analysis_agent(state)
        assert result["errors"]


class TestAnomalyDetectionAgent:
    def test_detects_anomalies(self, base_state):
        base_state["dataframes"]["sales"].loc[0, "revenue"] = 9_999_999
        result = anomaly_detection_agent(base_state)
        assert "anomalies" in result
        assert isinstance(result["anomalies"], list)

    def test_explanations_generated(self, base_state):
        result = anomaly_detection_agent(base_state)
        assert "anomaly_explanations" in result


class TestVisualizationAgent:
    def test_charts_generated(self, base_state):
        update = data_analysis_agent(base_state)
        merged = {**base_state, **update}
        result = visualization_agent(merged)
        assert "chart_specs" in result
        assert len(result["chart_specs"]) > 0

    def test_chart_types_logged(self, base_state):
        update = data_analysis_agent(base_state)
        merged = {**base_state, **update}
        result = visualization_agent(merged)
        assert "chart_types_chosen" in result
        assert len(result["chart_types_chosen"]) == len(result["chart_specs"])

    def test_visualization_agent_returns_json_serialized_charts(self, sample_df):
        state = AgentState(
            user_query="Test chart generation",
            session_id="test-session-visualization",
            dataframes={"sales": sample_df},
            dataset_ids=["sales"],
            dataset_schemas={"sales": {
                "columns": sample_df.columns.tolist(),
                "dtypes": sample_df.dtypes.astype(str).to_dict(),
            }},
            errors=[],
            metadata={},
        )

        result = visualization_agent(state)
        chart_specs = result.get("chart_specs", [])
        assert chart_specs, "Expected at least one serialized chart"
        assert isinstance(chart_specs[0], dict)

        import plotly.io as pio
        json_chart = json.dumps(chart_specs[0])
        fig = pio.from_json(json_chart)
        assert fig.data, "Deserialized Plotly figure should contain traces"


class TestReportAgent:
    """Tests for report_agent and its rendering helpers."""

    def _full_state(self, base_state, sample_df) -> AgentState:
        """Build a state that has gone through data_analysis_agent."""
        update = data_analysis_agent(base_state)
        return {**base_state, **update}

    def test_report_agent_returns_html(self, base_state, sample_df, tmp_path, monkeypatch):
        """report_agent must populate report_html with a non-empty HTML string."""
        # Patch reports_dir to a temp directory so no real files are written
        from config import settings as _settings_module
        from unittest.mock import patch
        from config.settings import Settings

        state = self._full_state(base_state, sample_df)
        with patch("agents.report_agent.settings") as mock_settings:
            mock_settings.reports_dir = tmp_path
            result = report_agent(state)

        html = result.get("report_html", "")
        assert html, "report_html should be non-empty"
        assert "<html" in html.lower(), "report_html should contain an HTML document"

    def test_report_agent_returns_markdown(self, base_state, sample_df, tmp_path):
        """report_agent must populate report_markdown with a non-empty Markdown string."""
        state = self._full_state(base_state, sample_df)
        from unittest.mock import patch

        with patch("agents.report_agent.settings") as mock_settings:
            mock_settings.reports_dir = tmp_path
            result = report_agent(state)

        md = result.get("report_markdown", "")
        assert md, "report_markdown should be non-empty"
        assert "# " in md, "report_markdown should contain at least one heading"

    def test_report_agent_returns_final_response(self, base_state, sample_df, tmp_path):
        """report_agent must populate final_response."""
        state = self._full_state(base_state, sample_df)
        from unittest.mock import patch

        with patch("agents.report_agent.settings") as mock_settings:
            mock_settings.reports_dir = tmp_path
            result = report_agent(state)

        assert "final_response" in result
        assert isinstance(result["final_response"], str)

    def test_report_agent_saves_files(self, base_state, sample_df, tmp_path):
        """report_agent must write .html and .md files to reports_dir."""
        state = self._full_state(base_state, sample_df)
        from unittest.mock import patch

        with patch("agents.report_agent.settings") as mock_settings:
            mock_settings.reports_dir = tmp_path
            report_agent(state)

        html_files = list(tmp_path.glob("*.html"))
        md_files = list(tmp_path.glob("*.md"))
        assert html_files, "Expected at least one .html file in reports_dir"
        assert md_files, "Expected at least one .md file in reports_dir"

    def test_report_agent_empty_state(self, tmp_path):
        """report_agent should not crash on a minimal/empty state."""
        state = AgentState(
            user_query="empty test",
            session_id="test-empty",
            errors=[],
            metadata={},
        )
        from unittest.mock import patch

        with patch("agents.report_agent.settings") as mock_settings:
            mock_settings.reports_dir = tmp_path
            result = report_agent(state)   # must not raise

        assert "report_html" in result
        assert "report_markdown" in result

    def test_render_html_includes_title(self):
        """_render_html should embed the title in the returned HTML."""
        ctx = {
            "title": "Test Report",
            "generated_at": "2024-01-01 00:00:00",
            "session_id": "abc",
            "dataset_count": 1,
            "executive_summary": "All good.",
            "schemas": {},
            "kpi_summary": {},
            "insights": ["Revenue is up."],
            "trends": [],
            "anomaly_explanations": [],
            "recommendations": ["Invest more."],
            "generated_sql": "",
            "execution_plan": [],
        }
        html = _render_html(ctx)
        assert "Test Report" in html
        assert "Revenue is up." in html

    def test_render_markdown_includes_insights(self):
        """_render_markdown should list every insight as a bullet."""
        ctx = {
            "title": "Markdown Report",
            "generated_at": "2024-01-01 00:00:00",
            "session_id": "abc",
            "executive_summary": "Summary here.",
            "insights": ["Insight A", "Insight B"],
            "trends": [],
            "anomaly_explanations": [],
            "recommendations": [],
            "generated_sql": "",
        }
        md = _render_markdown(ctx)
        assert "Insight A" in md
        assert "Insight B" in md
        assert "## Business Insights" in md
