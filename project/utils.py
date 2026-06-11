from zoneinfo import ZoneInfo

IST_TZ = ZoneInfo("Asia/Kolkata")
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional
import os
import sqlite3

import pandas as pd
import streamlit as st

ROOT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = ROOT_DIR / "social_media.db"

PLATFORM_COLORS = {
    "Facebook": "#0EA5E9",
    "facebook": "#0EA5E9",
    "Instagram": "#EC4899",
    "YouTube": "#F59E0B",
    "youtube": "#F59E0B",
    "instagram": "#EC4899",
    "All": "#8B5CF6",
}

CHART_COLORS = ["#22D3EE", "#EC4899", "#F59E0B", "#10B981", "#818CF8", "#A78BFA", "#FB7185", "#38BDF8"]

FB_COLOR = "#2563EB"
IG_COLOR = "#A855F7"
YT_COLOR = "#EF4444"
ACCENT = "#6366F1"


def platform_label(value: str) -> str:
    text = str(value or "").strip().lower()
    if text == "facebook":
        return "Facebook"
    if text == "instagram":
        return "Instagram"
    if text == "youtube":
        return "YouTube"
    return str(value or "Unknown").title()


def get_db_connection():
    return sqlite3.connect(str(DB_PATH))


def load_table(table_name: str) -> pd.DataFrame:
    try:
        with get_db_connection() as conn:
            return pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
    except Exception:
        return pd.DataFrame()


def get_latest_available_date() -> Optional[pd.Timestamp]:
    latest_dates = []
    for table_name in ("daily_summary", "facebook_posts", "instagram_posts", "youtube_videos"):
        try:
            df = load_table(table_name)
            if df.empty or "date" not in df.columns:
                continue
            parsed = pd.to_datetime(df["date"], errors="coerce")
            if parsed.notna().any():
                latest_dates.append(parsed.max())
        except Exception:
            continue
    if not latest_dates:
        return None
    return max(latest_dates)


def get_date_range(selection: str, custom_range):
    today = date.today()
    if selection == "Today":
        return today, today
    if selection == "Yesterday":
        yesterday = today - timedelta(days=1)
        return yesterday, yesterday
    if selection == "Last 7 Days":
        return today - timedelta(days=6), today
    if selection == "Last 30 Days":
        return today - timedelta(days=29), today
    if selection == "Custom Range" and isinstance(custom_range, (list, tuple)) and len(custom_range) == 2:
        return custom_range[0], custom_range[1]
    if selection == "Custom Range" and isinstance(custom_range, date):
        return custom_range, custom_range
    return today - timedelta(days=29), today


def build_date_filter():
    selection = st.sidebar.selectbox(
        "📅 Date filter",
        ["Today", "Yesterday", "Last 7 Days", "Last 30 Days", "Custom Range"],
        index=3,
    )
    custom_range = None
    if selection == "Custom Range":
        custom_range = st.sidebar.date_input(
            "Custom date range",
            [date.today() - timedelta(days=29), date.today()],
            key="custom_date_range",
        )
    return selection, custom_range


def format_count(value):
    try:
        n = int(value)
        if n >= 1_000_000:
            return f"{n / 1_000_000:.1f}M"
        if n >= 1_000:
            return f"{n / 1_000:.1f}K"
        return f"{n:,}"
    except Exception:
        return "0"


def build_platform_breakdown_rows(platform_totals):
    return pd.DataFrame(
        [
            {
                "Platform": "🔵 Facebook",
                "Posts": platform_totals["facebook"]["posts"],
                "Reach": platform_totals["facebook"]["reach"],
                "Views / Impressions": platform_totals["facebook"]["impressions"],
                "Engagement": platform_totals["facebook"]["engagement"],
                "Followers": platform_totals["facebook"]["followers"],
            },
            {
                "Platform": "🟣 Instagram",
                "Posts": platform_totals["instagram"]["posts"],
                "Reach": platform_totals["instagram"]["reach"],
                "Views / Impressions": platform_totals["instagram"]["impressions"],
                "Engagement": platform_totals["instagram"]["engagement"],
                "Followers": platform_totals["instagram"]["followers"],
            },
                        {
                "Platform": "🔴 YouTube",
                "Posts": platform_totals["youtube"]["posts"],
                "Reach": platform_totals["youtube"]["reach"],
                "Views / Impressions": platform_totals["youtube"]["impressions"],
                "Engagement": platform_totals["youtube"]["engagement"],
                "Followers": platform_totals["youtube"]["followers"],
            },
        ]
    )


def render_platform_breakdown(platform_totals, title: str = "Platform Breakdown"):
    breakdown = build_platform_breakdown_rows(platform_totals)
    st.markdown(f"#### {title}")
    st.dataframe(
        breakdown,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Posts": st.column_config.NumberColumn("Posts", format="%d"),
            "Reach": st.column_config.NumberColumn("Reach", format="%d"),
            "Views / Impressions": st.column_config.NumberColumn("Views / Impressions", format="%d"),
            "Engagement": st.column_config.NumberColumn("Engagement", format="%d"),
            "Followers": st.column_config.NumberColumn("Followers", format="%d"),
        },
    )
    return breakdown


def inject_dashboard_style():
    st.markdown(
        """
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

            /* ─── Global ─── */
            html, body, .stApp, [data-testid="stAppViewContainer"] {
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
            }
            .stApp {
                background:
                    radial-gradient(circle at top left, rgba(34, 211, 238, 0.18) 0%, transparent 18%),
                    radial-gradient(circle at top right, rgba(236, 72, 153, 0.18) 0%, transparent 20%),
                    radial-gradient(circle at bottom left, rgba(16, 185, 129, 0.14) 0%, transparent 18%),
                    radial-gradient(circle at bottom right, rgba(139, 92, 246, 0.16) 0%, transparent 20%),
                    linear-gradient(135deg, #F8FBFF 0%, #EEF6FF 45%, #F5F3FF 100%) !important;
            }
            [data-testid="stAppViewContainer"] main {
                background: transparent !important;
            }
            .block-container {
                padding-top: 1rem !important;
                padding-bottom: 2rem !important;
            }

            /* ─── Sidebar ─── */
            [data-testid="stSidebar"] {
                background: linear-gradient(180deg, #0f172a 0%, #111827 18%, #1e293b 55%, #4338ca 100%) !important;
                border-right: none !important;
                box-shadow: 4px 0 24px rgba(30, 27, 75, 0.18);
                border-top-right-radius: 32px !important;
                border-bottom-right-radius: 32px !important;
                padding-top: 1rem !important;
            }
            [data-testid="stSidebar"] * {
                color: #E0E7FF !important;
                -webkit-text-fill-color: #E0E7FF !important;
            }
            [data-testid="stSidebar"] .stButton > button {
                background: linear-gradient(135deg, #22D3EE 0%, #818CF8 45%, #EC4899 100%) !important;
                color: #FFFFFF !important;
                -webkit-text-fill-color: #FFFFFF !important;
                border: none !important;
                border-radius: 14px !important;
                font-weight: 600 !important;
                padding: 0.7rem 1rem !important;
                transition: all 0.3s ease !important;
                box-shadow: 0 6px 18px rgba(79, 70, 229, 0.2) !important;
            }
            [data-testid="stSidebar"] .stButton > button:hover {
                transform: translateY(-2px) !important;
                box-shadow: 0 10px 30px rgba(56, 189, 248, 0.35), 0 0 0 1px rgba(255,255,255,0.12) inset !important;
            }
            [data-testid="stSidebar"] .stButton > button * {
                color: #FFFFFF !important;
                -webkit-text-fill-color: #FFFFFF !important;
            }
            [data-testid="stSidebar"] .stMarkdown, [data-testid="stSidebar"] .stText, [data-testid="stSidebar"] .stSelectbox, [data-testid="stSidebar"] .stDateInput, [data-testid="stSidebar"] .stSlider {
                border-radius: 24px !important;
                background: rgba(255,255,255,0.08) !important;
                padding: 0.9rem 1rem 0.8rem !important;
                margin-bottom: 0.9rem !important;
                border: 1px solid rgba(255,255,255,0.12) !important;
                box-shadow: inset 0 1px 2px rgba(255,255,255,0.08), 0 10px 24px rgba(15,23,42,0.08) !important;
            }
            .sidebar-card {
                border-radius: 24px;
                background: rgba(255,255,255,0.09);
                border: 1px solid rgba(255,255,255,0.14);
                box-shadow: 0 18px 42px rgba(15, 23, 42, 0.12);
                padding: 18px;
                margin-bottom: 20px;
                color: #E0E7FF !important;
            }
            .sidebar-card h3 {
                margin: 0 0 0.5rem;
                font-size: 1rem;
                color: #EFF6FF !important;
            }
            .sidebar-card p {
                margin: 0;
                color: #CBD5E1 !important;
                font-size: 0.95rem;
                line-height: 1.6;
            }

            /* ─── Typography ─── */
            h1, h2, h3, h4 {
                font-family: 'Inter', sans-serif !important;
                font-weight: 700 !important;
                color: var(--text-color) !important;
                letter-spacing: -0.02em !important;
            }
            h1 { font-weight: 800 !important; }
            h2 { margin-top: 0.5rem !important; }
            p, label, .stMarkdown, .stText {
                font-family: 'Inter', sans-serif !important;
            }

            /* ─── Metric Cards ─── */
            [data-testid="stMetric"] {
                background: linear-gradient(135deg, rgba(8, 47, 73, 0.98), rgba(17, 24, 39, 0.98), rgba(139, 92, 246, 0.98)) !important;
                opacity: 0.98;
                backdrop-filter: blur(12px) !important;
                -webkit-backdrop-filter: blur(12px) !important;
                border: 1px solid rgba(128, 128, 128, 0.2) !important;
                border-radius: 16px !important;
                padding: 1.1rem 1.25rem !important;
                box-shadow: 0 4px 16px rgba(0, 0, 0, 0.05) !important;
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
                position: relative !important;
                overflow: hidden !important;
            }
            [data-testid="stMetric"]::before {
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                height: 4px;
                background: linear-gradient(90deg, #22D3EE 0%, #818CF8 35%, #EC4899 70%, #F59E0B 100%);
                border-radius: 16px 16px 0 0;
                box-shadow: 0 0 12px rgba(56, 189, 248, 0.25);
            }
            [data-testid="stMetric"]:hover {
                transform: translateY(-4px) scale(1.015) !important;
                box-shadow: 0 18px 42px rgba(56, 189, 248, 0.18), 0 10px 28px rgba(236, 72, 153, 0.14), 0 2px 10px rgba(15, 23, 42, 0.08) !important;
            }
            [data-testid="stMetricLabel"] {
                color: #E5EEF9 !important;
                opacity: 0.82;
                font-size: 0.8rem !important;
                font-weight: 600 !important;
                text-transform: uppercase !important;
                letter-spacing: 0.04em !important;
            }
            [data-testid="stMetricValue"] {
                color: #FFFFFF !important;
                font-weight: 800 !important;
                font-size: 1.65rem !important;
            }
            [data-testid="stMetricDelta"] {
                color: #BFDBFE !important;
                font-weight: 600 !important;
            }

            /* ─── Hero Banner ─── */
            .dashboard-hero {
                border-radius: 24px;
                padding: 1.5rem 2rem;
                margin: 0.25rem 0 1.5rem;
                background:
                    radial-gradient(circle at top right, rgba(255,255,255,0.18), transparent 18%),
                    linear-gradient(135deg, #0EA5E9 0%, #8B5CF6 45%, #EC4899 100%);
                color: #FFFFFF;
                border: none;
                box-shadow: 0 8px 32px rgba(79, 70, 229, 0.25), 0 2px 8px rgba(124, 58, 237, 0.15);
                position: relative;
                overflow: hidden;
            }
            .dashboard-hero::before {
                content: '';
                position: absolute;
                top: -50%;
                right: -20%;
                width: 300px;
                height: 300px;
                background: radial-gradient(circle, rgba(255,255,255,0.12) 0%, transparent 70%);
                border-radius: 50%;
            }
            .dashboard-hero::after {
                content: '';
                position: absolute;
                bottom: -30%;
                left: -10%;
                width: 200px;
                height: 200px;
                background: radial-gradient(circle, rgba(255,255,255,0.08) 0%, transparent 70%);
                border-radius: 50%;
            }
            .dashboard-hero h1, .dashboard-hero h2, .dashboard-hero p {
                color: #FFFFFF !important;
                -webkit-text-fill-color: #FFFFFF !important;
                margin: 0;
                position: relative;
                z-index: 1;
            }
            .dashboard-hero h1 {
                font-size: clamp(1.5rem, 3vw, 2rem);
                font-weight: 800 !important;
                line-height: 1.2;
                letter-spacing: -0.03em;
            }
            .dashboard-hero p {
                margin-top: 0.5rem;
                max-width: 56rem;
                color: rgba(255, 255, 255, 0.85) !important;
                -webkit-text-fill-color: rgba(255, 255, 255, 0.85) !important;
                font-size: 0.95rem;
                line-height: 1.5;
            }
            .status-pill {
                display: inline-flex;
                align-items: center;
                gap: 0.4rem;
                border-radius: 999px;
                padding: 0.35rem 0.85rem;
                background: rgba(255, 255, 255, 0.2);
                backdrop-filter: blur(8px);
                border: 1px solid rgba(255, 255, 255, 0.3);
                color: #FFFFFF !important;
                -webkit-text-fill-color: #FFFFFF !important;
                font-size: 0.82rem;
                margin-top: 0.75rem;
                font-weight: 600;
                position: relative;
                z-index: 1;
            }
            .status-pill::before {
                content: '';
                width: 8px;
                height: 8px;
                background: #34D399;
                border-radius: 50%;
                animation: pulse-dot 2s ease-in-out infinite;
                box-shadow: 0 0 8px rgba(52, 211, 153, 0.6);
            }
            @keyframes pulse-dot {
                0%, 100% { opacity: 1; transform: scale(1); }
                50% { opacity: 0.5; transform: scale(0.8); }
            }

            /* ─── Data Tables ─── */
            div[data-testid="stDataFrame"] {
                border-radius: 16px !important;
                overflow: hidden !important;
                border: 1px solid rgba(226, 232, 240, 0.8) !important;
                box-shadow: 0 2px 8px rgba(15, 23, 42, 0.04) !important;
                background: var(--background-color) !important;
            }

            /* ─── Buttons ─── */
            .stButton > button, .stDownloadButton > button {
                border-radius: 12px !important;
                border: 1px solid rgba(148, 163, 184, 0.25) !important;
                background: linear-gradient(135deg, rgba(255,255,255,0.98), rgba(224, 242, 254, 0.98)) !important;
                color: var(--text-color) !important;
                -webkit-text-fill-color: var(--text-color) !important;
                font-weight: 600 !important;
                box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05) !important;
                transition: all 0.2s ease !important;
            }
            .stButton > button:hover, .stDownloadButton > button:hover {
                border-color: #A78BFA !important;
                color: #6D28D9 !important;
                -webkit-text-fill-color: #6D28D9 !important;
                box-shadow: 0 10px 22px rgba(139, 92, 246, 0.20), 0 0 0 1px rgba(255,255,255,0.22) inset !important;
                transform: translateY(-2px) !important;
            }

            /* ─── Inputs ─── */
            input, textarea, select,
            [data-baseweb="select"] *,
            [data-baseweb="input"] * {
                color: var(--text-color) !important;
                -webkit-text-fill-color: var(--text-color) !important;
                font-family: 'Inter', sans-serif !important;
            }
            [data-baseweb="select"] > div {
                border-radius: 10px !important;
                border-color: rgba(128, 128, 128, 0.2) !important;
                background: var(--background-color) !important;
            }

            /* ─── Radio buttons ─── */
            [data-testid="stRadio"] * {
                color: var(--text-color) !important;
            }

            /* ─── Alerts ─── */
            [data-testid="stAlert"] {
                border-radius: 14px !important;
                border: 1px solid rgba(148, 163, 184, 0.25) !important;
                box-shadow: 0 10px 24px rgba(15, 23, 42, 0.06) !important;
                background: linear-gradient(135deg, rgba(255,255,255,0.96), rgba(248,250,252,0.94)) !important;
            }
            [data-testid="stAlert"] p {
                color: #334155 !important;
                -webkit-text-fill-color: #334155 !important;
            }

            /* ─── Expanders ─── */
            [data-testid="stExpander"] {
                border-radius: 18px !important;
                border: 1px solid rgba(148, 163, 184, 0.25) !important;
                background: linear-gradient(135deg, rgba(255,255,255,0.96), rgba(240,249,255,0.96)) !important;
                overflow: hidden !important;
                box-shadow: 0 10px 24px rgba(15, 23, 42, 0.06), 0 0 0 1px rgba(255,255,255,0.5) inset !important;
            }

            /* ─── Plotly charts ─── */
            .js-plotly-plot .plotly .modebar {
                background: transparent !important;
            }
            .js-plotly-plot, .plotly, .plot-container {
                border-radius: 16px !important;
                overflow: hidden !important;
            }

            /* ─── Dividers ─── */
            hr {
                border: none !important;
                height: 1px !important;
                background: linear-gradient(90deg, transparent, #CBD5E1, transparent) !important;
                margin: 1.5rem 0 !important;
            }

            /* ─── Smooth transitions for auto-refresh (no blink) ─── */
            .stApp, [data-testid="stAppViewContainer"],
            [data-testid="stAppViewContainer"] > section {
                transition: none !important;
                animation: none !important;
            }
            .element-container, .stMarkdown, [data-testid="stMetric"],
            [data-testid="column"], [data-testid="stVerticalBlock"] {
                animation: none !important;
            }

            /* ─── Scrollbar ─── */
            ::-webkit-scrollbar { width: 6px; height: 6px; }
            ::-webkit-scrollbar-track { background: transparent; }
            ::-webkit-scrollbar-thumb { background: #CBD5E1; border-radius: 3px; }
            ::-webkit-scrollbar-thumb:hover { background: #94A3B8; }

            /* ─── Tab styling ─── */
            .stTabs [data-baseweb="tab-list"] {
                gap: 6px;
                background: rgba(255, 255, 255, 0.55);
                border: 1px solid rgba(148, 163, 184, 0.18);
                border-radius: 14px;
                padding: 4px;
                box-shadow: 0 8px 18px rgba(15, 23, 42, 0.05);
            }
            .stTabs [data-baseweb="tab"] {
                border-radius: 10px;
                font-weight: 700;
                padding: 0.55rem 0.9rem;
                color: #475569 !important;
                -webkit-text-fill-color: #475569 !important;
            }
            .stTabs [data-baseweb="tab"]:hover {
                background: rgba(79, 70, 229, 0.08) !important;
            }
            .stTabs [data-baseweb="tab"][aria-selected='true'] {
                background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 100%) !important;
                color: #FFFFFF !important;
                -webkit-text-fill-color: #FFFFFF !important;
                box-shadow: 0 8px 16px rgba(79, 70, 229, 0.20) !important;
            }

            /* ─── Visual cards ─── */
            .visual-card {
                border-radius: 18px;
                border: 1px solid rgba(148, 163, 184, 0.18);
                background: linear-gradient(135deg, rgba(255,255,255,0.98), rgba(248,250,252,0.95));
                box-shadow: 0 10px 24px rgba(15, 23, 42, 0.06);
                padding: 1rem;
                margin: 0.2rem 0 1rem;
            }
            .visual-badge {
                display: inline-flex;
                align-items: center;
                gap: 0.35rem;
                border-radius: 999px;
                padding: 0.35rem 0.65rem;
                background: linear-gradient(135deg, rgba(56, 189, 248, 0.22), rgba(236, 72, 153, 0.22));
                box-shadow: 0 8px 18px rgba(56, 189, 248, 0.15);
                color: #4338CA !important;
                -webkit-text-fill-color: #4338CA !important;
                font-size: 0.78rem;
                font-weight: 700;
                letter-spacing: 0.03em;
                text-transform: uppercase;
            }
            .dashboard-hero {
                border-radius: 28px;
                padding: 32px 26px;
                background: linear-gradient(135deg, #0f172a 0%, #2563eb 46%, #0ea5e9 100%);
                color: #ffffff;
                box-shadow: 0 30px 80px rgba(15, 23, 42, 0.14);
                margin-bottom: 28px;
            }
            .dashboard-hero h1 {
                margin: 0 0 0.75rem;
                font-size: 2.45rem;
                line-height: 1.05;
            }
            .dashboard-hero p {
                margin: 0;
                max-width: 760px;
                opacity: 0.92;
                font-size: 1rem;
                line-height: 1.75;
            }
            .dashboard-hero .hero-details {
                margin-top: 24px;
                display: flex;
                flex-wrap: wrap;
                gap: 12px;
            }
            .status-pill {
                display: inline-flex;
                align-items: center;
                gap: 0.35rem;
                border-radius: 999px;
                padding: 0.55rem 0.9rem;
                background: rgba(255,255,255,0.16);
                border: 1px solid rgba(255,255,255,0.22);
                color: #ffffff !important;
                font-weight: 700;
                letter-spacing: 0.03em;
                text-transform: uppercase;
                font-size: 0.78rem;
            }
            .dashboard-card-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
                gap: 18px;
                margin-top: 20px;
            }
            .dashboard-card {
                border-radius: 24px;
                background: #ffffff;
                padding: 24px;
                box-shadow: 0 18px 50px rgba(15, 23, 42, 0.08);
                border: 1px solid rgba(148, 163, 184, 0.12);
            }
            .dashboard-card.small {
                padding: 18px;
            }
            .dashboard-card-title {
                margin-bottom: 14px;
                font-size: 1rem;
                font-weight: 700;
                color: #0f172a;
            }
            .dashboard-note {
                padding: 18px;
                border-radius: 18px;
                background: #eff6ff;
                color: #1e3a8a;
                border: 1px solid rgba(59, 130, 246, 0.2);
                margin-bottom: 22px;
            }
            @media(max-width:900px){
                .dashboard-card-grid { grid-template-columns: 1fr; }
                .dashboard-hero { padding: 24px 18px; }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

    try:
        st.sidebar.markdown(
            """
            <div class="sidebar-card">
                <h3>Dashboard controls</h3>
                <p>Use the filters and settings below to update the active dashboard view with the same HTML-style card look.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    except Exception:
        pass


def render_page_header(title: str, subtitle: str = ""):
    updated = get_last_updated_text()
    st.markdown(
        f"""
        <div class="dashboard-hero">
            <h1>{title}</h1>
            <p>{subtitle}</p>
            <div class="hero-details">
                <span class="visual-badge">Interactive visual analytics</span>
                <span class="status-pill">Live &bull; Last updated {updated}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def chart_layout(fig, title: str = None):
    if title:
        fig.update_layout(title=title)
    fig.update_layout(
        template="plotly_white",
        hovermode="x unified",
        colorway=CHART_COLORS,
        paper_bgcolor="rgba(248, 250, 252, 0.95)",
        plot_bgcolor="rgba(248, 250, 252, 0.95)",
        font=dict(family="Inter, sans-serif", color="#334155", size=13),
        title=dict(font=dict(size=18, color="#1E293B", family="Inter, sans-serif"), x=0, xanchor="left"),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            bgcolor="rgba(255,255,255,0)",
            font=dict(size=12, family="Inter, sans-serif"),
            borderwidth=0,
        ),
        margin=dict(l=36, r=36, t=72, b=56),
        hoverlabel=dict(
            bgcolor="rgba(255,255,255,0.98)",
            font_size=13,
            font_family="Inter, sans-serif",
            bordercolor="#E2E8F0",
        ),
    )
    fig.update_xaxes(
        showgrid=False,
        linecolor="#CBD5E1",
        title_font=dict(size=12, color="#64748B"),
        tickfont=dict(size=11, color="#64748B"),
    )
    fig.update_yaxes(
        gridcolor="rgba(148, 163, 184, 0.25)",
        zerolinecolor="#CBD5E1",
        title_font=dict(size=12, color="#64748B"),
        tickfont=dict(size=11, color="#64748B"),
    )
    return fig


def load_int_env(key: str, default: int) -> int:
    value = os.getenv(key)
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def get_last_updated_text():
    if DB_PATH.exists():
        # Get the file modification time and convert to IST
        updated = datetime.fromtimestamp(DB_PATH.stat().st_mtime, tz=IST_TZ)
        return updated.strftime("%Y-%m-%d %H:%M %Z")
    return "No database found"


def load_metric_sum(metric_name: str, source: str, start_date=None, end_date=None) -> int:
    query = "SELECT SUM(value) as total FROM metrics WHERE source = ? AND metric = ?"
    params = [source, metric_name]
    if start_date is not None and end_date is not None:
        query += " AND date >= ? AND date <= ?"
        params.extend([str(start_date), str(end_date)])
    try:
        with get_db_connection() as conn:
            df = pd.read_sql_query(query, conn, params=params)
            if not df.empty and pd.notna(df.at[0, "total"]):
                return int(df.at[0, "total"] or 0)
    except Exception:
        pass
    return 0


def load_views_impressions(start_date=None, end_date=None):
    df = load_daily_summary(start_date, end_date)
    fb = int(df[df["platform"].str.lower() == "facebook"]["impressions"].sum() or 0)
    ig = int(df[df["platform"].str.lower() == "instagram"]["impressions"].sum() or 0)
    yt = int(df[df["platform"].str.lower() == "youtube"]["impressions"].sum() or 0)

    if fb == 0:
        fb = load_metric_sum("page_impressions", "facebook", start_date, end_date)
        if fb == 0:
            fb = load_metric_sum("page_posts_impressions", "facebook", start_date, end_date)

    if ig == 0:
        ig = load_metric_sum("profile_views_total", "instagram", start_date, end_date)

    total = fb + ig + yt
    return ig, fb, yt, total
    return ig, fb, total


def load_platform_totals(start_date=None, end_date=None):
    summary_df = load_daily_summary(start_date, end_date)
    fb_summary = summary_df[summary_df["platform"].str.lower() == "facebook"] if not summary_df.empty else summary_df
    ig_summary = summary_df[summary_df["platform"].str.lower() == "instagram"] if not summary_df.empty else summary_df

    yt_summary = summary_df[summary_df["platform"].str.lower() == "youtube"] if not summary_df.empty else summary_df

    fb_posts = load_all_posts(start_date, end_date, platform="facebook")
    ig_posts = load_all_posts(start_date, end_date, platform="instagram")
    yt_posts = load_all_posts(start_date, end_date, platform="youtube")
    followers_df = load_followers_history()

    yt_followers = 0
    if not followers_df.empty:
        fb_followers_df = followers_df[followers_df["platform"].str.lower() == "facebook"]
        ig_followers_df = followers_df[followers_df["platform"].str.lower() == "instagram"]
        yt_followers_df = followers_df[followers_df["platform"].str.lower() == "youtube"]
        if not fb_followers_df.empty:
            fb_followers = int(fb_followers_df.sort_values(by="date").tail(1)["followers"].squeeze())
        if not ig_followers_df.empty:
            ig_followers = int(ig_followers_df.sort_values(by="date").tail(1)["followers"].squeeze())
        if not yt_followers_df.empty:
            yt_followers = int(yt_followers_df.sort_values(by="date").tail(1)["followers"].squeeze())

    fb_reach = int(fb_summary["reach"].sum() or 0)
    if fb_reach == 0:
        fb_reach = load_metric_sum("page_impressions", "facebook", start_date, end_date)
        if fb_reach == 0:
            fb_reach = load_metric_sum("page_posts_impressions", "facebook", start_date, end_date)

    fb_impressions = int(fb_summary["impressions"].sum() or 0)
    if fb_impressions == 0:
        fb_impressions = load_metric_sum("page_impressions", "facebook", start_date, end_date)
        if fb_impressions == 0:
            fb_impressions = load_metric_sum("page_posts_impressions", "facebook", start_date, end_date)

    ig_reach = int(ig_summary["reach"].sum() or 0)
    if ig_reach == 0:
        ig_reach = load_metric_sum("reach", "instagram", start_date, end_date)

    ig_impressions = int(ig_summary["impressions"].sum() or 0)
    if ig_impressions == 0:
        ig_impressions = load_metric_sum("profile_views_total", "instagram", start_date, end_date)

    yt_reach = int(yt_summary["reach"].sum() or 0)
    yt_impressions = int(yt_summary["impressions"].sum() or 0)

    return {
        "facebook": {
            "posts": len(fb_posts),
            "reach": fb_reach,
            "impressions": fb_impressions,
            "engagement": int(fb_summary["engagement"].sum() or 0),
            "followers": fb_followers,
        },
                "instagram": {
            "posts": len(ig_posts),
            "reach": ig_reach,
            "impressions": ig_impressions,
            "engagement": int(ig_summary["engagement"].sum() or 0),
            "followers": ig_followers,
        },
        "youtube": {
            "posts": len(yt_posts),
            "reach": yt_reach,
            "impressions": yt_impressions,
            "engagement": int(yt_summary["engagement"].sum() or 0),
            "followers": yt_followers,
        },
    }


def load_all_posts(start_date=None, end_date=None, platform: str = "all") -> pd.DataFrame:
    fb = load_table("facebook_posts")
    ig = load_table("instagram_posts")

    frames = []
    if not fb.empty and platform in ("all", "facebook"):
        fb = fb.copy()
        fb["source"] = "Facebook"
        fb["caption"] = fb["message"].fillna("")
        fb["time"] = fb["time"].fillna("")
        fb.loc[fb["time"] == "", "time"] = fb["created_time"].fillna("").str[11:19]
        fb["post_id"] = fb["post_id"].fillna("")
        fb["likes"] = fb["reactions"].fillna(0)
        fb["comments"] = fb["comments"].fillna(0)
        fb["shares"] = fb["shares"].fillna(0)
        fb["reach"] = fb["post_reach"].fillna(0)
        fb["impressions"] = fb["post_impressions"].fillna(0)
        fb.loc[fb["impressions"] == 0, "impressions"] = fb.loc[fb["impressions"] == 0, "reach"]
        fb["engagement"] = fb["total_engagement"].fillna(0)
        fb["engagement_rate"] = fb["engagement_rate"].fillna(0)
        frames.append(fb[["source", "post_id", "date", "time", "caption", "reach", "impressions", "likes", "comments", "shares", "engagement", "engagement_rate"]])

    if not ig.empty and platform in ("all", "instagram"):
        ig = ig.copy()
        ig["source"] = "Instagram"
        ig["caption"] = ig["caption"].fillna("")
        ig["time"] = ig["time"].fillna("")
        ig.loc[ig["time"] == "", "time"] = ig["timestamp"].fillna("").str[11:19]
        ig["media_id"] = ig["media_id"].fillna("")
        ig["likes"] = ig["like_count"].fillna(0)
        ig["comments"] = ig["comments_count"].fillna(0)
        ig["shares"] = ig["shares"].fillna(0)
        ig["reach"] = ig["reach"].fillna(0)
        ig["impressions"] = ig["impressions"].fillna(0)
        ig.loc[ig["impressions"] == 0, "impressions"] = ig.loc[ig["impressions"] == 0, "reach"]
        ig["engagement"] = ig["total_interactions"].fillna(0)
        ig["engagement_rate"] = ig["engagement_rate"].fillna(0)
        frames.append(ig[["source", "media_id", "date", "time", "caption", "reach", "impressions", "likes", "comments", "shares", "engagement", "engagement_rate"]])


    yt = load_table("youtube_videos")
    
    if not yt.empty and platform in ("all", "youtube"):
        yt = yt.copy()
        yt["source"] = "YouTube"
        yt["caption"] = yt["title"].fillna("") + " " + yt["description"].fillna("")
        yt["time"] = yt["time"].fillna("")
        yt.loc[yt["time"] == "", "time"] = yt["timestamp"].fillna("").str[11:19]
        yt["video_id"] = yt["video_id"].fillna("")
        yt["likes"] = yt["like_count"].fillna(0)
        yt["comments"] = yt["comment_count"].fillna(0)
        yt["shares"] = 0
        yt["reach"] = yt["view_count"].fillna(0)
        yt["impressions"] = yt["view_count"].fillna(0)
        yt["engagement"] = yt["likes"] + yt["comments"]
        yt["engagement_rate"] = yt["engagement_rate"].fillna(0)
        frames.append(yt[["source", "video_id", "date", "time", "caption", "reach", "impressions", "likes", "comments", "shares", "engagement", "engagement_rate"]].rename(columns={"video_id": "content_id"}))

    if not frames:
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True, sort=False)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["content_id"] = df.get("post_id", pd.Series("", index=df.index)).fillna("")
    if "media_id" in df.columns:
        df.loc[df["content_id"] == "", "content_id"] = df.loc[df["content_id"] == "", "media_id"].fillna("")
    if "video_id" in df.columns:
        df.loc[df["content_id"] == "", "content_id"] = df.loc[df["content_id"] == "", "media_id"].fillna("")
    if start_date is not None and end_date is not None:
        df = df[(df["date"] >= pd.to_datetime(start_date)) & (df["date"] <= pd.to_datetime(end_date))]
    return df.sort_values(by=["engagement"], ascending=False)


def load_daily_summary(start_date=None, end_date=None, platform: str = "all") -> pd.DataFrame:
    df = load_table("daily_summary")
    if df.empty:
        return df
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    if start_date is not None and end_date is not None:
        df = df[(df["date"] >= pd.to_datetime(start_date)) & (df["date"] <= pd.to_datetime(end_date))]
    if platform != "all":
        df = df[df["platform"].str.lower() == platform.lower()]
    return df


def load_followers_history() -> pd.DataFrame:
    df = load_table("followers_history")
    if df.empty:
        return df
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df


def load_best_posting_time() -> pd.DataFrame:
    df = load_table("best_posting_time")
    if df.empty:
        return df
    df = df.copy()
    df["hour_label"] = df["hour"].apply(lambda x: f"{int(x):02d}:00")
    return df


def load_top_posts(start_date=None, end_date=None) -> pd.DataFrame:
    df = load_all_posts(start_date, end_date)
    if not df.empty:
        df = df.copy()
        df["platform"] = df["source"].apply(platform_label)
        df["caption"] = df["caption"].fillna("").astype(str)
        df["likes"] = pd.to_numeric(df["likes"], errors="coerce").fillna(0).astype(int)
        df["comments"] = pd.to_numeric(df["comments"], errors="coerce").fillna(0).astype(int)
        df["shares"] = pd.to_numeric(df["shares"], errors="coerce").fillna(0).astype(int)
        df["engagement"] = pd.to_numeric(df["engagement"], errors="coerce").fillna(0).astype(int)
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
        return df.sort_values(["engagement", "likes"], ascending=False).head(10)

    df = load_table("top_posts")
    if df.empty:
        return df
    df = df.copy()
    df["caption"] = df["caption"].fillna("")
    return df


def load_alerts() -> pd.DataFrame:
    df = load_table("alerts_log")
    if df.empty:
        return df
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    return df.sort_values(by="timestamp", ascending=False)


REFRESH_INTERVAL_MS = load_int_env("REFRESH_INTERVAL_MS", 30000)


def setup_refresh(interval_ms: int = REFRESH_INTERVAL_MS):
    """Use streamlit-autorefresh if available, otherwise use a meta-refresh
    approach that avoids full page blinks by only clearing the data cache."""
    try:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=interval_ms, key="dashboard_refresh")
    except ImportError:
        # Smooth refresh: clear cached data periodically so next interaction
        # picks up new DB data, but do NOT force a hard page reload that
        # causes visible blinking.
        if "last_cache_clear" not in st.session_state:
            st.session_state["last_cache_clear"] = datetime.now()

        elapsed = (datetime.now() - st.session_state["last_cache_clear"]).total_seconds() * 1000
        if elapsed >= interval_ms:
            st.cache_data.clear()
            st.session_state["last_cache_clear"] = datetime.now()
