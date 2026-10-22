import os
from pathlib import Path

import duckdb
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Find database path
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = REPO_ROOT / "data" / "warehouse.duckdb"
DB_PATH = os.getenv("DUCKDB_PATH", str(DEFAULT_DB_PATH))

# Color palette
PALETTE = {
    "primary": "#3B82F6",  # Blue
    "secondary": "#6366F1",  # Indigo
    "success": "#10B981",  # Emerald
    "warning": "#F59E0B",  # Amber
    "danger": "#EF4444",  # Rose
    "neutral": "#64748B",  # Slate
    "dark": "#0F172A",
    "light": "#F8FAFC",
    "accent1": "#8B5CF6",  # Purple
    "accent2": "#06B6D4",  # Cyan
    "purple": "#8B5CF6",
}

CHART_COLORS = [
    "#3B82F6",
    "#10B981",
    "#F59E0B",
    "#EF4444",
    "#8B5CF6",
    "#06B6D4",
    "#EC4899",
    "#64748B",
]


@st.cache_resource
def get_db_connection():
    """Returns a read-only DuckDB connection."""
    if not Path(DB_PATH).exists():
        raise FileNotFoundError(
            f"DuckDB database not found at {DB_PATH}. "
            "Please build the pipeline first via 'make dbt-build'."
        )
    return duckdb.connect(DB_PATH, read_only=True)


@st.cache_data(ttl=600, show_spinner=False)
def run_query(query: str, params: tuple | None = None) -> pd.DataFrame:
    """Executes a SQL query against the warehouse and returns a pandas DataFrame."""
    con = get_db_connection()
    if params:
        return con.execute(query, params).df()
    return con.execute(query).df()


def format_currency(val: float, prefix: str = "Rp ") -> str:
    """Formats numeric value into clean IDR currency string (Billions/Millions)."""
    if val is None or pd.isna(val):
        return f"{prefix}0"
    abs_val = abs(val)
    sign = "-" if val < 0 else ""
    if abs_val >= 1e12:
        return f"{sign}{prefix}{abs_val / 1e12:.2f} T"
    if abs_val >= 1e9:
        return f"{sign}{prefix}{abs_val / 1e9:.2f} B"
    if abs_val >= 1e6:
        return f"{sign}{prefix}{abs_val / 1e6:.2f} M"
    if abs_val >= 1e3:
        return f"{sign}{prefix}{abs_val / 1e3:.1f} K"
    return f"{sign}{prefix}{abs_val:,.0f}"


def format_number(val: float) -> str:
    """Formats integer or float with K/M abbreviations or commas."""
    if val is None or pd.isna(val):
        return "0"
    abs_val = abs(val)
    sign = "-" if val < 0 else ""
    if abs_val >= 1e6:
        return f"{sign}{abs_val / 1e6:.2f}M"
    if abs_val >= 1e3:
        return f"{sign}{abs_val / 1e3:.1f}K"
    return f"{sign}{abs_val:,.0f}"


def format_pct(val: float) -> str:
    """Formats float percentage."""
    if val is None or pd.isna(val):
        return "0.0%"
    return f"{val:.1f}%"


def apply_custom_css():
    """Injects high-end, responsive styling into the Streamlit dashboard."""
    st.markdown(
        """
        <style>
        /* General layout spacing */
        .block-container {
            padding-top: 1.8rem;
            padding-bottom: 2rem;
            max-width: 1300px;
        }

        /* KPI Card styling */
        .kpi-card {
            background-color: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 12px;
            padding: 18px 20px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            transition: transform 0.15s ease-in-out, box-shadow 0.15s ease-in-out;
            margin-bottom: 12px;
        }
        .kpi-card:hover {
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }
        .kpi-title {
            font-size: 0.85rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: #64748B;
            margin-bottom: 6px;
        }
        .kpi-value {
            font-size: 1.85rem;
            font-weight: 700;
            color: #0F172A;
            margin-bottom: 4px;
            letter-spacing: -0.02em;
        }
        .kpi-delta-pos {
            font-size: 0.85rem;
            font-weight: 600;
            color: #10B981;
        }
        .kpi-delta-neg {
            font-size: 0.85rem;
            font-weight: 600;
            color: #EF4444;
        }
        .kpi-delta-neutral {
            font-size: 0.85rem;
            font-weight: 500;
            color: #64748B;
        }

        /* Badge pills */
        .badge {
            display: inline-block;
            padding: 3px 10px;
            font-size: 0.75rem;
            font-weight: 600;
            border-radius: 9999px;
            margin-right: 6px;
        }
        .badge-blue { background-color: #DBEAFE; color: #1D4ED8; }
        .badge-green { background-color: #D1FAE5; color: #047857; }
        .badge-purple { background-color: #EDE9FE; color: #6D28D9; }
        .badge-amber { background-color: #FEF3C7; color: #B45309; }

        /* Section headers */
        .section-header {
            font-size: 1.25rem;
            font-weight: 700;
            color: #1E293B;
            margin-top: 1.2rem;
            margin-bottom: 0.6rem;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        /* Sidebar tweaks */
        section[data-testid="stSidebar"] {
            background-color: #F8FAFC;
            border-right: 1px solid #E2E8F0;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def style_plot(
    fig: go.Figure, title: str | None = None, height: int = 420
) -> go.Figure:
    """Applies a clean, unified aesthetic to Plotly figures."""
    fig.update_layout(
        template="plotly_white",
        title={
            "text": f"<b>{title}</b>" if title else "",
            "font": {"size": 15, "color": "#1E293B"},
            "x": 0.01,
            "y": 0.96,
        },
        margin={"l": 20, "r": 20, "t": 50, "b": 30},
        height=height,
        font={"family": "Inter, -apple-system, sans-serif", "color": "#334155"},
        hoverlabel={
            "bgcolor": "#1E293B",
            "font_size": 12,
            "font_family": "Inter, sans-serif",
            "font_color": "#FFFFFF",
        },
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1,
            "title": "",
        },
    )
    fig.update_xaxes(showgrid=True, gridcolor="#F1F5F9", linecolor="#CBD5E1")
    fig.update_yaxes(showgrid=True, gridcolor="#F1F5F9", linecolor="#CBD5E1")
    return fig


def render_kpi(
    col,
    title: str,
    value: str,
    delta: str | None = None,
    delta_positive: bool = True,
    help_text: str | None = None,
):
    """Renders a modern, visually appealing KPI card."""
    with col:
        delta_html = ""
        if delta is not None:
            css_class = "kpi-delta-pos" if delta_positive else "kpi-delta-neg"
            delta_html = f'<div class="{css_class}">{delta}</div>'

        st.markdown(
            f"""
            <div class="kpi-card" title="{help_text or ""}">
                <div class="kpi-title">{title}</div>
                <div class="kpi-value">{value}</div>
                {delta_html}
            </div>
            """,
            unsafe_allow_html=True,
        )
