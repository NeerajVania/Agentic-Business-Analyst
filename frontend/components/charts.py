"""
frontend/components/charts.py
==============================
Reusable Streamlit chart components for visualizing analysis results.
"""

from typing import Any, Dict, List, Optional
import streamlit as st
import pandas as pd
import plotly.graph_objects as go


def render_kpi_card(label: str, value: Any, delta: Optional[str] = None, delta_color: str = "off"):
    """Render a KPI card."""
    col = st.columns(1)[0]
    with col:
        st.metric(label, value, delta=delta, delta_color=delta_color)


def render_metric_row(metrics: Dict[str, Any], cols: int = 4):
    """Render multiple KPI metrics in a row."""
    columns = st.columns(cols)
    for idx, (label, value) in enumerate(list(metrics.items())[:cols]):
        with columns[idx % cols]:
            st.metric(label, value)


def render_plotly_chart(fig: go.Figure, key: Optional[str] = None):
    """Render a Plotly figure in Streamlit."""
    st.plotly_chart(fig, width="stretch", key=key)


def render_chart_from_dict(chart_dict: Dict[str, Any]):
    """Render a chart from Plotly dictionary specification."""
    if not chart_dict:
        st.warning("No chart data available.")
        return
    
    try:
        fig = go.Figure(chart_dict)
        render_plotly_chart(fig)
    except Exception as e:
        st.error(f"Failed to render chart: {e}")


def render_insights_list(insights: List[str], title: str = "📊 Insights"):
    """Render a list of text insights."""
    if not insights:
        return
    
    st.subheader(title)
    for i, insight in enumerate(insights, 1):
        st.markdown(f"**{i}. {insight}**")


def render_recommendations(recommendations: List[str], title: str = "💡 Recommendations"):
    """Render action recommendations."""
    if not recommendations:
        return
    
    st.subheader(title)
    for i, rec in enumerate(recommendations, 1):
        st.info(f"**{i}. {rec}**")


def render_anomalies(anomalies: List[str], title: str = "⚠️ Anomalies Detected"):
    """Render detected anomalies with warnings."""
    if not anomalies:
        return
    
    st.subheader(title)
    for anomaly in anomalies:
        st.warning(f"• {anomaly}")


def render_data_table(df: pd.DataFrame, title: Optional[str] = None, height: int = 300):
    """Render a data table with optional title."""
    if title:
        st.subheader(title)
    
    if df.empty:
        st.info("No data to display.")
        return
    
    st.dataframe(df, width="stretch", height=height)


def render_tabs(*tabs: tuple):
    """
    Render multiple tabs.
    
    Usage:
        render_tabs(
            ("Tab1", content1_func),
            ("Tab2", content2_func),
        )
    """
    tab_names = [t[0] for t in tabs]
    tab_contents = [t[1] for t in tabs]
    
    tab_objects = st.tabs(tab_names)
    
    for tab, content_func in zip(tab_objects, tab_contents):
        with tab:
            content_func()


def render_comparison(df1: pd.DataFrame, df2: pd.DataFrame, title: str = "Comparison"):
    """Render side-by-side dataframe comparison."""
    st.subheader(title)
    col1, col2 = st.columns(2)
    
    with col1:
        st.caption("Dataset 1")
        st.dataframe(df1, width="stretch")
    
    with col2:
        st.caption("Dataset 2")
        st.dataframe(df2, width="stretch")
