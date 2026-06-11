from datetime import date

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
    "Executive Overview",
    "Scan current audience, reach, impressions, and engagement with charts that reload from live database snapshots.",
)
selection, custom_range = utils.build_date_filter()
start_date, end_date = utils.get_date_range(selection, custom_range)

today = date.today()
latest_snapshot_date = utils.get_latest_available_date()

if latest_snapshot_date is not None and latest_snapshot_date.date() < today:
    today = latest_snapshot_date.date()

teal_platform_colors = {
    "Facebook": "#14B8A6",
    "Instagram": "#2DD4BF",
    "YouTube": "#38BDF8",
    "All": "#0F766E",
}

st.markdown(
    f"""
    <div class='dashboard-card-grid'>
      <div class='dashboard-card'>
        <div class='dashboard-card-title'>Date range</div>
        <p>{start_date} to {end_date}</p>
      </div>
      <div class='dashboard-card'>
        <div class='dashboard-card-title'>Current snapshot day</div>
        <p>{today}</p>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

summary_df = utils.load_daily_summary(start_date, end_date)
posts_df = utils.load_all_posts(start_date, end_date)
followers_df = utils.load_followers_history()

if summary_df.empty and posts_df.empty:
    st.warning("No data is available for this date range. Run the data collector and refresh the page.")
    st.stop()

platform_totals = utils.load_platform_totals(start_date, end_date)
facebook = platform_totals["facebook"]
instagram = platform_totals["instagram"]
youtube = platform_totals["youtube"]

posts_count = len(posts_df)
reach_total = facebook["reach"] + instagram["reach"] + youtube["reach"]
total_views_impressions = facebook["impressions"] + instagram["impressions"] + youtube["impressions"]
engagement_total = facebook["engagement"] + instagram["engagement"] + youtube["engagement"]
followers_total = facebook["followers"] + instagram["followers"] + youtube["followers"]

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("All Platforms - Posts", utils.format_count(posts_count))
col2.metric("All Platforms - Reach", utils.format_count(reach_total))
col3.metric("All Platforms - Views / Impressions", utils.format_count(total_views_impressions))
col4.metric("All Platforms - Engagement", utils.format_count(engagement_total))
col5.metric("All Platforms - Followers", utils.format_count(followers_total))

st.markdown("---")
st.markdown("<div class='dashboard-card'><div class='dashboard-card-title'>Platform Breakdown</div></div>", unsafe_allow_html=True)
utils.render_platform_breakdown(platform_totals)

st.markdown("---")
if not summary_df.empty:
    trend_df = summary_df.sort_values("date").copy()
    trend_df["Platform"] = trend_df["platform"].apply(utils.platform_label)
    
    st.markdown("<div class='dashboard-card'><div class='dashboard-card-title'>Live Performance Trends</div></div>", unsafe_allow_html=True)
    tab_reach, tab_views, tab_eng = st.tabs(["📈 Reach Trends", "👁️ Views & Impressions", "🔥 Engagement Trends"])
    
    with tab_reach:
        if "reach" in trend_df.columns:
            fig1 = px.line(
                trend_df,
                x="date",
                y="reach",
                color="Platform",
                markers=True,
                color_discrete_map=teal_platform_colors,
                hover_data={"Platform": True, "reach": ":,.0f"},
                labels={"date": "Date", "reach": "Reach", "Platform": "Platform"},
            )
            st.plotly_chart(utils.chart_layout(fig1, "Daily Reach by Platform"), use_container_width=True)
        else:
            st.info("Reach data is not available.")
            
    with tab_views:
        if "impressions" in trend_df.columns:
            fig2 = px.line(
                trend_df,
                x="date",
                y="impressions",
                color="Platform",
                markers=True,
                color_discrete_map=teal_platform_colors,
                hover_data={"Platform": True, "impressions": ":,.0f"},
                labels={"date": "Date", "impressions": "Views / Impressions", "Platform": "Platform"},
            )
            st.plotly_chart(utils.chart_layout(fig2, "Daily Views & Impressions by Platform"), use_container_width=True)
        else:
            st.info("Views / Impressions data is not available.")
            
    with tab_eng:
        if "engagement" in trend_df.columns:
            fig3 = px.line(
                trend_df,
                x="date",
                y="engagement",
                color="Platform",
                markers=True,
                color_discrete_map=teal_platform_colors,
                hover_data={"Platform": True, "engagement": ":,.0f"},
                labels={"date": "Date", "engagement": "Engagement", "Platform": "Platform"},
            )
            st.plotly_chart(utils.chart_layout(fig3, "Daily Engagement by Platform"), use_container_width=True)
        else:
            st.info("Engagement data is not available.")

st.markdown("---")
st.subheader("Platform Snapshot")
platform_snapshot = pd.DataFrame(
    [
        {"Platform": "Facebook", "Posts": facebook["posts"], "Reach": facebook["reach"], "Impressions": facebook["impressions"], "Engagement": facebook["engagement"], "Followers": facebook["followers"]},
        {"Platform": "Instagram", "Posts": instagram["posts"], "Reach": instagram["reach"], "Impressions": instagram["impressions"], "Engagement": instagram["engagement"], "Followers": instagram["followers"]},
        {"Platform": "YouTube", "Posts": youtube["posts"], "Reach": youtube["reach"], "Impressions": youtube["impressions"], "Engagement": youtube["engagement"], "Followers": youtube["followers"]},
    ]
)
chart_fig = px.bar(
    platform_snapshot,
    x="Platform",
    y=["Reach", "Engagement", "Impressions"],
    barmode="group",
    color_discrete_map={"Reach": "#14B8A6", "Engagement": "#2DD4BF", "Impressions": "#38BDF8"},
    title="Platform Reach, Engagement, and Impressions",
    labels={"value": "Total", "variable": "Metric", "Platform": "Platform"},
)
st.plotly_chart(utils.chart_layout(chart_fig), use_container_width=True)

share_df = pd.DataFrame(
    [
        {"Platform": "Facebook", "Value": facebook["engagement"]},
        {"Platform": "Instagram", "Value": instagram["engagement"]},
        {"Platform": "YouTube", "Value": youtube["engagement"]},
    ]
)
share_fig = px.pie(
    share_df,
    values="Value",
    names="Platform",
    hole=0.45,
    title="Engagement Share by Platform",
    color_discrete_map=teal_platform_colors,
)
share_fig.update_traces(textinfo="percent+label", pull=[0.03, 0.03, 0.03], marker=dict(line=dict(color="white", width=2)))
st.plotly_chart(utils.chart_layout(share_fig), use_container_width=True)

bubble_df = pd.DataFrame(
    [
        {"Platform": "Facebook", "Reach": facebook["reach"], "Engagement": facebook["engagement"], "Followers": facebook["followers"]},
        {"Platform": "Instagram", "Reach": instagram["reach"], "Engagement": instagram["engagement"], "Followers": instagram["followers"]},
        {"Platform": "YouTube", "Reach": youtube["reach"], "Engagement": youtube["engagement"], "Followers": youtube["followers"]},
    ]
)
bubble_fig = px.scatter(
    bubble_df,
    x="Reach",
    y="Engagement",
    size="Followers",
    color="Platform",
    color_discrete_map=teal_platform_colors,
    hover_name="Platform",
    title="Reach vs Engagement by Platform",
    labels={"Reach": "Reach", "Engagement": "Engagement", "Followers": "Followers"},
    size_max=60,
)
bubble_fig.update_traces(marker=dict(line=dict(width=1, color="rgba(15,23,42,0.12)")))
st.plotly_chart(utils.chart_layout(bubble_fig), use_container_width=True)

st.markdown("---")
with st.expander("Today's Recent Posts and Metrics", expanded=True):
    if latest_snapshot_date is not None and latest_snapshot_date.date() < date.today():
        st.info(f"The database has not yet recorded a newer snapshot for today, so this panel is showing the latest available day: {latest_snapshot_date.date().isoformat()}.")

    today_posts_df = utils.load_all_posts(today, today)
    today_summary = utils.load_daily_summary(today, today)

    today_reach = int(today_summary["reach"].sum() if not today_summary.empty else 0)
    today_impressions = int(today_summary["impressions"].sum() if not today_summary.empty else 0)
    today_engagement = int(today_summary["engagement"].sum() if not today_summary.empty else 0)
    today_posts_count = len(today_posts_df)

    today_cols = st.columns(4)
    today_cols[0].metric("Today's Posts", utils.format_count(today_posts_count))
    today_cols[1].metric("Today's Reach", utils.format_count(today_reach))
    today_cols[2].metric("Today's Impressions", utils.format_count(today_impressions))
    today_cols[3].metric("Today's Engagement", utils.format_count(today_engagement))

    if today_posts_df.empty:
        st.info("No posts were published today or data has not yet been collected for today.")
    else:
        display_df = today_posts_df.copy()
        display_df["time"] = display_df["time"].fillna("")
        display_df["datetime_utc"] = pd.to_datetime(
            display_df["date"].astype(str) + " " + display_df["time"].astype(str),
            format="%Y-%m-%d %H:%M:%S",
            errors="coerce",
        )
        display_df["datetime_utc"] = display_df["datetime_utc"].dt.tz_localize("UTC", ambiguous="NaT", nonexistent="NaT")
        display_df["datetime_ist"] = display_df["datetime_utc"].dt.tz_convert("Asia/Kolkata")
        display_df["Time (IST)"] = display_df["datetime_ist"].dt.strftime("%H:%M")
        display_df["Platform"] = display_df["source"].apply(utils.platform_label)

        today_chart = px.bar(
            display_df,
            x="Time (IST)",
            y="engagement",
            color="Platform",
            color_discrete_map=teal_platform_colors,
            text="engagement",
            title="Today's Engagement by Post Time",
            labels={"engagement": "Engagement", "Time (IST)": "Post Time (IST)"},
        )
        today_chart.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
        st.plotly_chart(utils.chart_layout(today_chart), use_container_width=True)

best_posts = utils.load_top_posts(start_date, end_date)
if not best_posts.empty:
    st.markdown("---")
    st.subheader("Top 5 Posts")
    top_posts = best_posts.head(5).copy()
    top_posts["Platform"] = top_posts["platform"].apply(utils.platform_label)
    top_posts["Caption"] = top_posts["caption"].str[:90]
    top_posts = top_posts[["Platform", "date", "engagement", "likes", "comments", "shares", "Caption"]]
    top_posts_fig = px.bar(
        top_posts,
        x="engagement",
        y="Caption",
        color="Platform",
        color_discrete_map=utils.PLATFORM_COLORS,
        orientation="h",
        title="Top 5 Posts by Engagement",
        labels={"engagement": "Engagement Value", "Caption": "Post"},
        hover_data={"Platform": True, "date": True, "likes": True, "comments": True, "shares": True},
    )
    top_posts_fig.update_layout(yaxis={'categoryorder': 'total ascending'})
    st.plotly_chart(utils.chart_layout(top_posts_fig), use_container_width=True)

if len(summary_df) >= 14:
    recent = summary_df.sort_values("date").tail(7)
    previous = summary_df.sort_values("date").iloc[-14:-7]
    if not recent.empty and not previous.empty:
        recent_sum = recent["engagement"].sum()
        previous_sum = previous["engagement"].sum()
        diff = recent_sum - previous_sum
        pct = ((diff / previous_sum) * 100) if previous_sum else 0
        indicator = "Up" if diff >= 0 else "Down"
        st.markdown("<div class='dashboard-card small'><div class='dashboard-card-title'>7-day engagement change</div></div>", unsafe_allow_html=True)
        st.metric("Engagement trend (7d vs prior 7d)", f"{indicator} {pct:.1f}%", f"{utils.format_count(int(diff))} change")

st.markdown(f"**Last updated:** {utils.get_last_updated_text()}")
