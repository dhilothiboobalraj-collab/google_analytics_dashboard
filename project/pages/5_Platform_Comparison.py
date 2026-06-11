import pandas as pd
import plotly.express as px
import streamlit as st
try:
    import utils
except ImportError:
    from project import utils

utils.inject_dashboard_style()
utils.setup_refresh()

utils.render_page_header(
    "Platform Comparison",
    "Compare each platform's live reach, engagement, and follower momentum side by side.",
)
selection, custom_range = utils.build_date_filter()
start_date, end_date = utils.get_date_range(selection, custom_range)

summary_df = utils.load_daily_summary(start_date, end_date)
followers_df = utils.load_followers_history()
posts_df = utils.load_all_posts(start_date, end_date)

if summary_df.empty:
    st.warning("No comparison data available for this date range.")
    st.stop()

summary_df = summary_df.copy()
summary_df["Platform"] = summary_df["platform"].apply(utils.platform_label)
agg = summary_df.groupby("Platform").agg({"reach": "sum", "engagement": "sum"}).reset_index()
agg = agg.rename(columns={"reach": "Reach", "engagement": "Engagement"})
long_df = agg.melt(id_vars=["Platform"], value_vars=["Reach", "Engagement"], var_name="Metric", value_name="Value")
long_df["Value Belongs To"] = long_df["Platform"] + " - " + long_df["Metric"]

total_reach = int(agg["Reach"].sum())
total_engagement = int(agg["Engagement"].sum())

engagement_rate_df = (
    summary_df.groupby("Platform", dropna=False)
    .agg(Reach=("reach", "sum"), Engagement=("engagement", "sum"))
    .reset_index()
)
engagement_rate_df["Engagement Rate (%)"] = engagement_rate_df.apply(
    lambda row: 0 if row["Reach"] == 0 else (row["Engagement"] / row["Reach"]) * 100,
    axis=1,
)
engagement_rate_df = engagement_rate_df.sort_values("Engagement Rate (%)", ascending=False)

followers_growth_df = followers_df.copy() if not followers_df.empty else pd.DataFrame()
if not followers_growth_df.empty:
    followers_growth_df["Platform"] = followers_growth_df["platform"].apply(utils.platform_label)

latest = followers_growth_df.sort_values("date").groupby("Platform", dropna=False).tail(1) if not followers_growth_df.empty else pd.DataFrame()
fastest_growth = None
if not latest.empty:
    latest = latest.rename(columns={"followers": "Followers", "growth_rate": "Growth Rate"})
    fastest_growth = latest.sort_values("Growth Rate", ascending=False).iloc[0]

st.markdown(
    """
    <div class='dashboard-card-grid'>
      <div class='dashboard-card'>
        <div class='dashboard-card-title'>Performance summary</div>
        <p>Compare total reach, engagement, and growth across channels for the selected date range.</p>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)
metric_cards = st.columns(3)
metric_cards[0].metric("Total Reach", utils.format_count(total_reach))
metric_cards[1].metric("Total Engagement", utils.format_count(total_engagement))
metric_cards[2].metric(
    "Fastest Growth",
    f"{fastest_growth['Platform']} • {fastest_growth['Growth Rate']:.1f}%" if fastest_growth is not None else "No growth data",
)

st.markdown("---")
st.markdown("<div class='dashboard-card'><div class='dashboard-card-title'>Engagement Rate by Platform</div></div>", unsafe_allow_html=True)
st.caption("This visual highlights which platform turns reach into the strongest engagement efficiency.")

rate_col, insight_col = st.columns([2, 1])
with rate_col:
    rate_fig = px.bar(
        engagement_rate_df,
        x="Platform",
        y="Engagement Rate (%)",
        color="Platform",
        color_discrete_map=utils.PLATFORM_COLORS,
        text="Engagement Rate (%)",
        title="Engagement Rate by Platform",
        labels={"Platform": "Platform", "Engagement Rate (%)": "Engagement Rate (%)"},
        hover_data={"Platform": True, "Engagement Rate (%)": ":.2f", "Reach": ":,.0f", "Engagement": ":,.0f"},
    )
    rate_fig.update_traces(texttemplate="%{text:.2f}%", textposition="outside")
    st.plotly_chart(utils.chart_layout(rate_fig), use_container_width=True)

with insight_col:
    top_rate = engagement_rate_df.iloc[0] if not engagement_rate_df.empty else None
    if top_rate is not None:
        st.metric("Top Engagement Rate", f"{top_rate['Engagement Rate (%)']:.2f}%", delta=f"{top_rate['Platform']} leads the set")
        st.info(
            f"{top_rate['Platform']} generated the strongest engagement efficiency in this range, with {utils.format_count(int(top_rate['Engagement']))} engagements from {utils.format_count(int(top_rate['Reach']))} total reach."
        )
    else:
        st.info("Engagement rate data is not available for this date range.")

comparison_tabs = st.tabs(["Weekly Comparison", "Monthly Comparison"])

with comparison_tabs[0]:
    weekly_df = summary_df.copy()
    weekly_df["Week"] = weekly_df["date"].dt.to_period("W-MON").apply(lambda x: x.start_time.strftime("%b %d"))
    weekly_group = (
        weekly_df.groupby(["Week", "Platform"], dropna=False)
        .agg(Reach=("reach", "sum"), Engagement=("engagement", "sum"))
        .reset_index()
    )
    weekly_long = weekly_group.melt(
        id_vars=["Week", "Platform"],
        value_vars=["Reach", "Engagement"],
        var_name="Metric",
        value_name="Value",
    )
    weekly_fig = px.bar(
        weekly_long,
        x="Week",
        y="Value",
        color="Platform",
        facet_col="Metric",
        color_discrete_map=utils.PLATFORM_COLORS,
        barmode="group",
        title="Weekly Platform Comparison",
        labels={"Value": "Total Value", "Week": "Week", "Platform": "Platform"},
        text="Value",
        hover_data={"Platform": True, "Metric": True, "Value": ":,.0f"},
    )
    weekly_fig.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
    st.plotly_chart(utils.chart_layout(weekly_fig), use_container_width=True)

with comparison_tabs[1]:
    monthly_df = summary_df.copy()
    monthly_df["Month"] = monthly_df["date"].dt.to_period("M").astype(str)
    monthly_group = (
        monthly_df.groupby(["Month", "Platform"], dropna=False)
        .agg(Reach=("reach", "sum"), Engagement=("engagement", "sum"))
        .reset_index()
    )
    monthly_long = monthly_group.melt(
        id_vars=["Month", "Platform"],
        value_vars=["Reach", "Engagement"],
        var_name="Metric",
        value_name="Value",
    )
    monthly_fig = px.bar(
        monthly_long,
        x="Month",
        y="Value",
        color="Platform",
        facet_col="Metric",
        color_discrete_map=utils.PLATFORM_COLORS,
        barmode="group",
        title="Monthly Platform Comparison",
        labels={"Value": "Total Value", "Month": "Month", "Platform": "Platform"},
        text="Value",
        hover_data={"Platform": True, "Metric": True, "Value": ":,.0f"},
    )
    monthly_fig.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
    st.plotly_chart(utils.chart_layout(monthly_fig), use_container_width=True)

if not followers_df.empty:
    followers_df = followers_df.copy()
    followers_df["Platform"] = followers_df["platform"].apply(utils.platform_label)
    latest = followers_df.sort_values("date").groupby("Platform").tail(1)
    latest = latest.rename(columns={"followers": "Followers", "growth_rate": "Growth Rate"})
    if not latest.empty:
        follower_rows = latest[["Platform", "Followers"]].copy()
        follower_rows["Metric"] = "Followers"
        follower_rows["Value Belongs To"] = follower_rows["Platform"] + " - Followers"
        fig_followers = px.bar(
            follower_rows,
            x="Metric",
            y="Followers",
            color="Platform",
            color_discrete_map=utils.PLATFORM_COLORS,
            barmode="group",
            title="Followers Comparison",
            labels={"Platform": "Platform"},
            text="Followers",
            hover_data={"Platform": True, "Followers": ":,.0f"},
        )
        fig_followers.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
        st.plotly_chart(utils.chart_layout(fig_followers), use_container_width=True)

        follower_timeline = followers_df.sort_values(["Platform", "date"]).copy()
        fig_timeline = px.line(
            follower_timeline,
            x="date",
            y="followers",
            color="Platform",
            color_discrete_map=utils.PLATFORM_COLORS,
            markers=True,
            title="Follower Growth Over Time",
            labels={"followers": "Followers", "date": "Date", "Platform": "Platform"},
        )
        st.plotly_chart(utils.chart_layout(fig_timeline), use_container_width=True)
