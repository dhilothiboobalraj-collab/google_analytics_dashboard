import pandas as pd
import plotly.express as px
import streamlit as st

try:
    import utils
except ImportError:
    from project import utils

try:
    import google_analytics as ga
except ImportError:
    from project import google_analytics as ga

utils.inject_dashboard_style()
utils.setup_refresh()

page_css = """
<style>
.ga-topbar {display:flex;flex-wrap:wrap;align-items:flex-start;justify-content:space-between;gap:18px;padding:24px 0;}
.ga-topbar-left {max-width:72%;}
.ga-topbar h1 {margin:0;font-size:2.15rem;line-height:1.05;color:#0f172a;font-weight:800;}
.ga-topbar p {margin:12px 0 0;font-size:1rem;color:#475569;max-width:760px;}
.ga-tabs {display:flex;flex-wrap:wrap;gap:10px;margin-top:22px;}
.ga-tab {padding:12px 18px;border-radius:999px;background:#f8fafc;color:#475569;font-weight:600;cursor:pointer;border:1px solid rgba(148,163,184,0.25);transition:all .2s ease;}
.ga-tab.active {background:#eff6ff;color:#1d4ed8;border-color:#93c5fd;box-shadow:0 10px 30px rgba(59,130,246,0.12);}
.ga-tab:hover {transform:translateY(-1px);}
.ga-hero {background:linear-gradient(135deg, #0b67d3, #13b8c3);border-radius:28px;padding:32px;box-shadow:0 30px 80px rgba(15,23,42,0.12);color:#ffffff;}
.ga-hero h2 {margin:0;font-size:2.25rem;line-height:1.05;}
.ga-hero p {margin:14px 0 0;max-width:720px;opacity:.94;font-size:1rem;}
.ga-chip-row {display:flex;flex-wrap:wrap;gap:12px;margin-top:24px;}
.ga-chip {display:inline-flex;align-items:center;gap:8px;padding:10px 16px;border-radius:999px;background:rgba(255,255,255,0.16);border:1px solid rgba(255,255,255,0.24);font-weight:600;font-size:0.92rem;}
.ga-card-grid {display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:18px;margin-top:24px;}
.ga-card {border-radius:24px;background:#ffffff;padding:24px;box-shadow:0 18px 52px rgba(15,23,42,0.06);border:1px solid rgba(148,163,184,0.12);}
.ga-card.small {padding:18px;}
.ga-card-title {font-size:1rem;font-weight:700;color:#0f172a;margin-bottom:14px;}
.ga-metric-title {font-size:0.85rem;color:#64748b;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:10px;}
.ga-metric-value {font-size:2rem;font-weight:800;color:#0f172a;margin-bottom:6px;}
.ga-metric-delta {font-size:0.95rem;font-weight:700;color:#10b981;}
.ga-divider {height:1px;background:linear-gradient(90deg,transparent,#cbd5e1,transparent);border:none;margin:30px 0;}
.ga-note {padding:18px;border-radius:20px;background:#eff6ff;color:#1e40af;border:1px solid rgba(59,130,246,0.18);margin-bottom:22px;}
.ga-small-grid {display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:18px;margin-top:12px;}
.ga-small-card {background:#f8fafc;border-radius:20px;padding:18px;}
.ga-small-card span {display:block;}
.ga-small-card .sub {margin-top:6px;color:#475569;font-size:0.9rem;}
@media(max-width:900px){.ga-flex-grid{grid-template-columns:1fr}.ga-topbar-left{max-width:100%;}}
</style>
"""

st.markdown(page_css, unsafe_allow_html=True)

property_id = ga.normalize_property_id(ga.load_env_value("GA4_PROPERTY_ID", ""))
auth_details = ga.get_google_auth_status()

auth_method = "OAuth" if auth_details["oauth_path"] else "Service account" if auth_details["service_path"] else "Unconfigured"
credential_status = "Configured" if auth_details["oauth_path"] or auth_details["service_path"] else "Missing"

summary = ga.fetch_ga4_summary(property_id=property_id or None, days=30)
channels = ga.fetch_ga4_channels(property_id=property_id or None, days=30)
connection_status = "Connected" if not summary.get("error") else "Disconnected"

trend_df = pd.DataFrame(summary.get("rows", []))
if not trend_df.empty:
    trend_df["date"] = pd.to_datetime(trend_df["date"], errors="coerce")
    trend_df = trend_df.sort_values("date").dropna(subset=["date"])
    last_7 = trend_df.tail(7)
    prior_7 = trend_df.iloc[-14:-7] if len(trend_df) >= 14 else pd.DataFrame()
    last_7_sessions = int(last_7["sessions"].sum()) if not last_7.empty else 0
    prior_7_sessions = int(prior_7["sessions"].sum()) if not prior_7.empty else 0
    last_7_users = int(last_7["activeUsers"].sum()) if not last_7.empty else 0
    prior_7_users = int(prior_7["activeUsers"].sum()) if not prior_7.empty else 0
    last_7_views = int(last_7["screenPageViews"].sum()) if not last_7.empty else 0
    prior_7_views = int(prior_7["screenPageViews"].sum()) if not prior_7.empty else 0
else:
    last_7 = pd.DataFrame()
    prior_7 = pd.DataFrame()
    last_7_sessions = prior_7_sessions = last_7_users = prior_7_users = last_7_views = prior_7_views = 0


def format_delta(current, previous):
    if previous <= 0:
        return "—"
    diff = current - previous
    percent = diff / previous * 100
    sign = "+" if diff >= 0 else ""
    return f"{sign}{diff:,} ({sign}{percent:.1f}%)"

weekly_session_change = format_delta(last_7_sessions, prior_7_sessions)
weekly_user_change = format_delta(last_7_users, prior_7_users)
weekly_view_change = format_delta(last_7_views, prior_7_views)

hero_html = f"""
<div class='ga-topbar'>
  <div class='ga-topbar-left'>
    <h1>Google Analytics — Live Website Performance</h1>
    <p>Visualize Google Analytics real-time metrics, traffic channels, and weekly trends in a polished dashboard layout.</p>
    <div class='ga-tabs'>
      <div class='ga-tab active'>Overview</div>
      <div class='ga-tab'>Google Analytics</div>
      <div class='ga-tab'>LinkedIn</div>
      <div class='ga-tab'>Facebook</div>
      <div class='ga-tab'>Instagram</div>
    </div>
  </div>
  <div class='ga-chip-row'>
    <div class='ga-chip'>Property: {property_id or 'Not set'}</div>
    <div class='ga-chip'>Auth: {auth_method}</div>
    <div class='ga-chip'>Connection: {connection_status}</div>
    <div class='ga-chip'>Creds: {credential_status}</div>
  </div>
</div>
"""

st.markdown(hero_html, unsafe_allow_html=True)

if auth_details["oauth_path"] and not auth_details["oauth_token_path"]:
    st.warning("OAuth credentials are configured, but the OAuth token file has not been created yet. Sign in once to complete the connection.")

if auth_method == "Unconfigured":
    st.info("No GA4 auth credentials are configured. Add OAuth or service account paths to .env and restart.")

if summary.get("error"):
    st.error(summary["error"])
    st.info("Set GA4_PROPERTY_ID and GOOGLE_APPLICATION_CREDENTIALS in .env, then restart the dashboard.")
    st.stop()

metric_html = f"""
<div class='ga-card-grid'>
  <div class='ga-card'>
    <div class='ga-metric-title'>Active Users</div>
    <div class='ga-metric-value'>{utils.format_count(summary.get('total_active_users', 0))}</div>
    <div class='ga-metric-delta'>{weekly_user_change if weekly_user_change != '—' else 'Weekly trend unavailable'}</div>
  </div>
  <div class='ga-card'>
    <div class='ga-metric-title'>Sessions</div>
    <div class='ga-metric-value'>{utils.format_count(summary.get('total_sessions', 0))}</div>
    <div class='ga-metric-delta'>{weekly_session_change if weekly_session_change != '—' else 'Weekly trend unavailable'}</div>
  </div>
  <div class='ga-card'>
    <div class='ga-metric-title'>Page Views</div>
    <div class='ga-metric-value'>{utils.format_count(summary.get('total_page_views', 0))}</div>
    <div class='ga-metric-delta'>{weekly_view_change if weekly_view_change != '—' else 'Weekly trend unavailable'}</div>
  </div>
  <div class='ga-card'>
    <div class='ga-metric-title'>New Users</div>
    <div class='ga-metric-value'>{utils.format_count(summary.get('total_new_users', 0))}</div>
    <div class='ga-metric-delta'>30-day total</div>
  </div>
  <div class='ga-card'>
    <div class='ga-metric-title'>Avg daily sessions</div>
    <div class='ga-metric-value'>{utils.format_count(round(summary.get('total_sessions', 0) / 30) if summary.get('total_sessions') else 0)}</div>
    <div class='ga-metric-delta'>Last 30 days</div>
  </div>
</div>
"""

st.markdown(metric_html, unsafe_allow_html=True)

st.markdown("<hr class='ga-divider'/>", unsafe_allow_html=True)

if not trend_df.empty:
    fig = px.line(
        trend_df,
        x="date",
        y=["activeUsers", "sessions", "screenPageViews"],
        markers=True,
        labels={"value": "Count", "date": "Date", "variable": "Metric"},
        color_discrete_sequence=["#0066CC", "#00CCCC", "#F59E0B"],
    )
    fig.update_layout(title="GA4 engagement trend", hovermode="x unified", template="plotly_white")
    fig.update_yaxes(title_text="Count")
    fig.update_xaxes(title_text="Date")

    left_col, right_col = st.columns([2, 1])
    with left_col:
        st.markdown("<div class='ga-card'><div class='ga-card-title'>Engagement trend</div></div>", unsafe_allow_html=True)
        st.plotly_chart(utils.chart_layout(fig), use_container_width=True)
    with right_col:
        st.markdown("<div class='ga-card small'><div class='ga-card-title'>Weekly summary</div></div>", unsafe_allow_html=True)
        st.metric("Sessions (7d)", utils.format_count(last_7_sessions), weekly_session_change)
        st.metric("Users (7d)", utils.format_count(last_7_users), weekly_user_change)
        st.metric("Page views (7d)", utils.format_count(last_7_views), weekly_view_change)
else:
    st.info("No GA4 trend data is available yet to build the charts.")

st.markdown("<hr class='ga-divider'/>", unsafe_allow_html=True)

channel_df = channels.get("channels", pd.DataFrame()) if isinstance(channels, dict) else pd.DataFrame()
if not channel_df.empty:
    channel_df = channel_df.rename(columns={"sessions": "Sessions", "activeUsers": "Active Users", "screenPageViews": "Page Views"})
    channel_df["Traffic Share"] = channel_df["Sessions"] / channel_df["Sessions"].sum() * 100

    left, right = st.columns([1.3, 1])
    with left:
        st.markdown("<div class='ga-card'><div class='ga-card-title'>Top traffic channels</div></div>", unsafe_allow_html=True)
        channel_fig = px.bar(
            channel_df.head(8),
            x="Sessions",
            y="channel",
            orientation="h",
            color="Sessions",
            color_continuous_scale="Viridis",
            labels={"channel": "Channel", "Sessions": "Sessions"},
        )
        channel_fig.update_layout(yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(utils.chart_layout(channel_fig), use_container_width=True)

    with right:
        st.markdown("<div class='ga-card small'><div class='ga-card-title'>Channel mix</div></div>", unsafe_allow_html=True)
        donut = px.pie(
            channel_df.head(6),
            names="channel",
            values="Sessions",
            hole=0.48,
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        donut.update_traces(textinfo="percent+label", marker=dict(line=dict(color="white", width=2)))
        st.plotly_chart(utils.chart_layout(donut), use_container_width=True)

    st.markdown("<div class='ga-card'><div class='ga-card-title'>Channel breakdown</div></div>", unsafe_allow_html=True)
    st.dataframe(channel_df.sort_values("Sessions", ascending=False).head(10), use_container_width=True, hide_index=True)
else:
    st.warning("GA4 traffic channel data is not available right now. Check the service-account permissions and property ID.")

st.markdown("<hr class='ga-divider'/>", unsafe_allow_html=True)

st.caption(
    "Google Analytics access now supports OAuth via client_secret.json and a service-account fallback via service_account.json. Use the configuration method that fits your GA4 property setup."
)
