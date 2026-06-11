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
    "Post Performance",
    "Filter posts by time, platform, and caption text, then inspect engagement from the newest live data.",
)
selection, custom_range = utils.build_date_filter()
start_date, end_date = utils.get_date_range(selection, custom_range)

platform_select = st.radio("Platform", ["All", "Facebook", "Instagram", "YouTube"], horizontal=True)

posts_df = utils.load_all_posts(start_date, end_date, platform=platform_select.lower() if platform_select != "All" else "all")

if posts_df.empty:
    st.warning("No post performance data available for this date range.")
    st.stop()

st.markdown("<div class='dashboard-card'><div class='dashboard-card-title'>Post performance summary</div><p>If raw post impressions are unavailable from the Meta API, post reach is shown as a fallback proxy.</p></div>", unsafe_allow_html=True)

hour_range = st.slider(
    "Posting hour range",
    0,
    23,
    (0, 23),
    format="%02d:00",
)

posts_df = posts_df.copy()
posts_df["time"] = posts_df["time"].fillna("")
posts_df["datetime_utc"] = pd.to_datetime(
    posts_df["date"].astype(str) + " " + posts_df["time"].astype(str),
    format="%Y-%m-%d %H:%M:%S",
    errors="coerce",
)
posts_df.loc[posts_df["datetime_utc"].isna(), "datetime_utc"] = pd.to_datetime(
    posts_df.loc[posts_df["datetime_utc"].isna(), "date"].astype(str),
    errors="coerce",
)
posts_df["datetime_utc"] = posts_df["datetime_utc"].dt.tz_localize("UTC", ambiguous="NaT", nonexistent="NaT")
posts_df["datetime_ist"] = posts_df["datetime_utc"].dt.tz_convert("Asia/Kolkata")
posts_df["time_ist"] = posts_df["datetime_ist"].dt.strftime("%H:%M")
posts_df["post_time"] = posts_df["datetime_ist"].dt.hour
posts_df = posts_df[(posts_df["post_time"] >= hour_range[0]) & (posts_df["post_time"] <= hour_range[1])]

search = st.text_input("Search captions", placeholder="Search text in captions")
if search:
    posts_df = posts_df[posts_df["caption"].str.contains(search, case=False, na=False)]

sort_by = st.selectbox("Sort posts by", ["Most recent", "Highest engagement", "Impressions", "Reach"], index=0)
if sort_by == "Most recent":
    posts_df = posts_df.sort_values(by=["datetime_ist"], ascending=[False])
elif sort_by == "Highest engagement":
    posts_df = posts_df.sort_values(by=["engagement", "datetime_ist"], ascending=[False, False])
elif sort_by == "Impressions":
    posts_df = posts_df.sort_values(by=["impressions", "datetime_ist"], ascending=[False, False])
else:
    posts_df = posts_df.sort_values(by=["reach", "datetime_ist"], ascending=[False, False])

st.markdown(
    """
    <div class='dashboard-card-grid'>
      <div class='dashboard-card'>
        <div class='dashboard-card-title'>Posts found</div>
        <p>Showing the newest posts and engagement performance for the selected platform and time window.</p>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

chart_metric = st.selectbox("Chart metric", ["engagement", "reach", "impressions", "likes", "comments", "shares"], index=0)
chart_df = posts_df.sort_values(by=["datetime_ist"], ascending=False).head(15).copy()
if not chart_df.empty:
    chart_df["published_ist"] = chart_df["datetime_ist"].dt.strftime("%Y-%m-%d %H:%M")
    chart_df["caption_preview"] = chart_df["caption"].str.slice(0, 80)
    chart_df["Platform"] = chart_df["source"].apply(utils.platform_label)
    # Shorten caption more for the axis label, keep full for hover
    chart_df["post_label"] = chart_df["Platform"] + " | " + chart_df["published_ist"]
    
    st.markdown("<div class='dashboard-card'><div class='dashboard-card-title'>Recent post engagement</div></div>", unsafe_allow_html=True)
    # Map colors to platforms
    color_map = {"Facebook": utils.FB_COLOR, "Instagram": utils.IG_COLOR, "YouTube": utils.YT_COLOR}
    
    fig = px.bar(
        chart_df,
        y="post_label",
        x=chart_metric,
        color="Platform",
        color_discrete_map=color_map,
        orientation="h",
        text=chart_metric,
        hover_data={
            "Platform": False,
            "post_label": False,
            "caption_preview": True,
            "reach": ":,.0f",
            "impressions": ":,.0f",
            "engagement": ":,.0f",
            "likes": ":,.0f",
            "comments": ":,.0f",
            "shares": ":,.0f",
        },
        labels={"post_label": "Post", chart_metric: f"{chart_metric.title()} Value"},
    )
    fig.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
    fig.update_layout(
        yaxis={'categoryorder': 'total ascending'},
        height=500 + (len(chart_df) * 20),
        showlegend=True,
    )
    
    # Apply standard layout but override some axes for horizontal bar
    fig = utils.chart_layout(fig, f"Recent Posts by {chart_metric.title()}")
    fig.update_yaxes(title_text="", tickmode="linear")
    st.plotly_chart(fig, use_container_width=True)

    top_post = chart_df.loc[chart_df[chart_metric].idxmax()]
    avg_metric = chart_df[chart_metric].mean()
    card_cols = st.columns(3)
    card_cols[0].metric("Top Post", top_post["content_id"][:18])
    card_cols[1].metric(f"Peak {chart_metric.title()}", utils.format_count(int(top_post[chart_metric])))
    card_cols[2].metric(f"Average {chart_metric.title()}", utils.format_count(int(avg_metric)))

    scatter_fig = px.scatter(
        chart_df,
        x="reach",
        y="engagement",
        size=chart_metric,
        color="Platform",
        color_discrete_map={"Facebook": utils.FB_COLOR, "Instagram": utils.IG_COLOR, "YouTube": utils.YT_COLOR},
        hover_name="content_id",
        hover_data={"Platform": True, "published_ist": True, "caption_preview": True},
        title="Reach vs Engagement Snapshot",
        labels={"reach": "Reach", "engagement": "Engagement", "Platform": "Platform"},
        size_max=55,
    )
    st.plotly_chart(utils.chart_layout(scatter_fig), use_container_width=True)

st.info("Use the recent-post visualization page for deeper comparisons and richer interactive post insights.")
