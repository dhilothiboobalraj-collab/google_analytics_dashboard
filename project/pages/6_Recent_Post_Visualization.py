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
    "Recent Post Visualization",
    "Interact with the latest posts, compare their engagement shape, and watch charts reload as new snapshots arrive.",
)
selection, custom_range = utils.build_date_filter()
start_date, end_date = utils.get_date_range(selection, custom_range)

st.markdown("<div class='dashboard-card small'><div class='dashboard-card-title'>Visualization settings</div><p>Pick the platform, metric, and post count to drive the recent post charts.</p></div>", unsafe_allow_html=True)
controls_container = st.container(border=True)
with controls_container:
    col1, col2, col3 = st.columns([1.5, 1.5, 2])
    with col1:
        platform_select = st.radio(
            "Platform Filter",
            ["All", "Facebook", "Instagram", "YouTube"],
            horizontal=True,
            help="Show posts from all platforms or filter to a specific network."
        )
    with col2:
        metric_options = ["engagement", "reach", "impressions", "likes", "comments", "shares"]
        chart_metric = st.selectbox(
            "Performance Metric",
            metric_options,
            index=0,
            format_func=lambda x: x.title(),
            help="Choose which interaction metric to display on the charts."
        )

posts_df = utils.load_all_posts(start_date, end_date, platform=platform_select.lower() if platform_select != "All" else "all")

if posts_df.empty:
    st.warning("No post data available for the selected date range.")
    st.stop()

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
posts_df["published_ist"] = posts_df["datetime_ist"].dt.strftime("%Y-%m-%d %H:%M")

with controls_container:
    with col3:
        recent_count = min(20, len(posts_df))
        recent_posts_count = st.slider(
            "Display Limit (Recent Posts)",
            min_value=1,
            max_value=recent_count,
            value=min(10, recent_count),
            help="Select how many of the most recent posts to include in the visual charts."
        )

recent_df = posts_df.sort_values(by=["datetime_ist"], ascending=False).head(recent_posts_count)
recent_df = recent_df.copy()
recent_df["Platform"] = recent_df["source"].apply(utils.platform_label)
recent_df["Value Belongs To"] = recent_df["Platform"] + " - " + chart_metric.title()

if not recent_df.empty:
    metric_label = chart_metric.title()
    top_post = recent_df.loc[recent_df[chart_metric].idxmax()]
    avg_metric = recent_df[chart_metric].mean()

    st.markdown("<div class='dashboard-card small'><div class='dashboard-card-title'>Recent post snapshot</div><p>A quick performance summary for the most recent posts in this range.</p></div>", unsafe_allow_html=True)
    st.caption("Visual summaries update instantly as you switch platforms or performance metrics.")
    metric_cards = st.columns(3)
    metric_cards[0].metric("Top Post", str(top_post["content_id"])[:16])
    metric_cards[1].metric(f"Peak {metric_label}", utils.format_count(int(top_post[chart_metric])))
    metric_cards[2].metric(f"Average {metric_label}", utils.format_count(int(avg_metric)))

    bar_fig = px.bar(
        recent_df,
        x="published_ist",
        y=chart_metric,
        color="Platform",
        color_discrete_map=utils.PLATFORM_COLORS,
        text=chart_metric,
        title=f"Top {recent_posts_count} Recent Posts by {chart_metric.title()}",
        labels={"published_ist": "Published (IST)", chart_metric: f"{chart_metric.title()} Value", "Platform": "Platform"},
        hover_data={
            "Platform": True,
            "content_id": True,
            "caption": True,
            "reach": True,
            "impressions": True,
            "engagement": True,
            "likes": True,
            "comments": True,
            "shares": True,
        },
    )
    bar_fig.update_traces(texttemplate="%{text:.0f}", textposition="outside", marker=dict(line=dict(width=0, color='rgba(0,0,0,0)')))
    bar_fig.update_layout(xaxis_tickangle=-45, uniformtext_minsize=8, uniformtext_mode="hide", legend_title_text="Platform")
    st.plotly_chart(utils.chart_layout(bar_fig), use_container_width=True)

    post_share_df = recent_df.groupby("Platform", as_index=False).size().rename(columns={"size": "Post Count"})
    post_share_fig = px.pie(
        post_share_df,
        values="Post Count",
        names="Platform",
        hole=0.45,
        title="Recent Post Share by Platform",
        color_discrete_map=utils.PLATFORM_COLORS,
    )
    post_share_fig.update_traces(textinfo="percent+label", pull=[0.03, 0.03, 0.03], marker=dict(line=dict(color="white", width=2)))
    st.plotly_chart(utils.chart_layout(post_share_fig), use_container_width=True)

    scatter_fig = px.scatter(
        recent_df,
        x="reach",
        y="engagement",
        size=chart_metric,
        color="Platform",
        color_discrete_map=utils.PLATFORM_COLORS,
        hover_name="content_id",
        hover_data={
            "Platform": True,
            "published_ist": True,
            "caption": True,
            "impressions": True,
            "likes": True,
            "comments": True,
            "shares": True,
        },
        title="Reach vs Engagement for Recent Posts",
        labels={"reach": "Reach Value", "engagement": "Engagement Value", "Platform": "Platform"},
        size_max=55,
    )
    scatter_fig.update_traces(marker=dict(line=dict(width=0, color='rgba(0,0,0,0)')))
    scatter_fig.update_layout(legend_title_text="Platform")
    st.plotly_chart(utils.chart_layout(scatter_fig), use_container_width=True)

    trend_fig = px.line(
        recent_df.sort_values("published_ist"),
        x="published_ist",
        y=chart_metric,
        color="Platform",
        markers=True,
        color_discrete_map=utils.PLATFORM_COLORS,
        title=f"Recent {chart_metric.title()} Trend by Platform",
        labels={"published_ist": "Published (IST)", chart_metric: f"{chart_metric.title()} Value", "Platform": "Platform"},
    )
    st.plotly_chart(utils.chart_layout(trend_fig), use_container_width=True)

else:
    st.warning("No recent posts are available to visualize.")
