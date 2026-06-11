import streamlit as st
import plotly.express as px
try:
    import utils
except ImportError:
    from project import utils

utils.inject_dashboard_style()
utils.setup_refresh()

utils.render_page_header(
    "Reach Analysis",
    "Explore daily, weekly, and monthly reach as live Meta snapshots flow into the local database.",
)
selection, custom_range = utils.build_date_filter()
start_date, end_date = utils.get_date_range(selection, custom_range)

summary_df = utils.load_daily_summary(start_date, end_date)

if summary_df.empty:
    st.warning("No reach data available for this date range.")
    st.stop()

summary_df = summary_df.sort_values("date")
if "platform" not in summary_df.columns:
    summary_df["platform"] = "All"
summary_df["Platform"] = summary_df["platform"].apply(utils.platform_label)
summary_df["Series"] = summary_df["Platform"] + " Reach"

platform_options = sorted(summary_df["Platform"].dropna().unique().tolist())
selected_platforms = st.multiselect(
    "Platform focus",
    platform_options,
    default=platform_options,
    key="reach_platform_focus",
    help="Highlight one or more channels in the visuals.",
)
if selected_platforms:
    summary_df = summary_df[summary_df["Platform"].isin(selected_platforms)]

total_reach = int(summary_df["reach"].sum())
avg_daily_reach = float(summary_df["reach"].mean())
peak_day = summary_df.sort_values("reach", ascending=False).iloc[0] if not summary_df.empty else None

st.markdown(
    """
    <div class='dashboard-card-grid'>
      <div class='dashboard-card'>
        <div class='dashboard-card-title'>Daily range summary</div>
        <p>Total reach, average daily reach, and peak campaign day.</p>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)
metrics = st.columns(3)
metrics[0].metric("Total Reach", utils.format_count(total_reach))
metrics[1].metric("Average Daily Reach", utils.format_count(int(avg_daily_reach)))
metrics[2].metric("Peak Day", peak_day["date"].strftime("%b %d") if peak_day is not None else "—")

st.markdown("<div class='dashboard-card'><div class='dashboard-card-title'>Daily Reach</div></div>", unsafe_allow_html=True)
fig_daily = px.line(
    summary_df,
    x="date",
    y="reach",
    color="Platform",
    color_discrete_map=utils.PLATFORM_COLORS,
    markers=True,
    title="Daily Reach by Platform",
    labels={"reach": "Reach Value", "date": "Date"},
    hover_data={"Platform": True, "reach": ":,.0f"},
)
st.plotly_chart(utils.chart_layout(fig_daily), use_container_width=True)

weekly = summary_df.copy()
weekly["week_start"] = weekly["date"].dt.to_period("W").apply(lambda r: r.start_time)
weekly = weekly.groupby(["week_start", "Platform", "Series"], dropna=False)["reach"].sum().reset_index()
weekly = weekly.sort_values("week_start")

st.markdown("<div class='dashboard-card'><div class='dashboard-card-title'>Weekly Reach</div></div>", unsafe_allow_html=True)
fig_weekly = px.line(
    weekly,
    x="week_start",
    y="reach",
    color="Platform",
    color_discrete_map=utils.PLATFORM_COLORS,
    markers=True,
    title="Weekly Reach by Platform",
    labels={"reach": "Reach Value", "week_start": "Week"},
    hover_data={"Platform": True, "reach": ":,.0f"},
)
st.plotly_chart(utils.chart_layout(fig_weekly), use_container_width=True)

monthly = summary_df.copy()
monthly["month"] = monthly["date"].dt.to_period("M").astype(str)
monthly = monthly.groupby(["month", "Platform", "Series"], dropna=False)["reach"].sum().reset_index()

st.markdown("<div class='dashboard-card'><div class='dashboard-card-title'>Monthly Reach</div></div>", unsafe_allow_html=True)
fig_monthly = px.bar(
    monthly,
    x="month",
    y="reach",
    color="Platform",
    color_discrete_map=utils.PLATFORM_COLORS,
    barmode="group",
    title="Monthly Reach by Platform",
    labels={"reach": "Reach Value", "month": "Month"},
    text="reach",
    hover_data={"Platform": True, "reach": ":,.0f"},
)
fig_monthly.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
st.plotly_chart(utils.chart_layout(fig_monthly), use_container_width=True)

monthly_share = monthly.groupby("Platform", as_index=False)["reach"].sum()
monthly_pie = px.pie(
    monthly_share,
    values="reach",
    names="Platform",
    hole=0.45,
    title="Monthly Reach Share by Platform",
    color_discrete_map=utils.PLATFORM_COLORS,
)
monthly_pie.update_traces(textinfo="percent+label", pull=[0.03, 0.03, 0.03], marker=dict(line=dict(color="white", width=2)))
st.plotly_chart(utils.chart_layout(monthly_pie), use_container_width=True)

reach_bubble = summary_df.copy()
reach_bubble["Engagement Size"] = reach_bubble["engagement"].fillna(0).astype(float)
fig_bubble = px.scatter(
    reach_bubble,
    x="date",
    y="reach",
    size="Engagement Size",
    color="Platform",
    color_discrete_map=utils.PLATFORM_COLORS,
    hover_data={"Platform": True, "reach": ":,.0f", "engagement": ":,.0f"},
    title="Reach Momentum vs Engagement",
    labels={"date": "Date", "reach": "Reach", "engagement": "Engagement"},
    size_max=60,
)
fig_bubble.update_traces(marker=dict(line=dict(width=1, color="rgba(15,23,42,0.12)")))
st.plotly_chart(utils.chart_layout(fig_bubble), use_container_width=True)
