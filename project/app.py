import threading
import time

import streamlit as st

try:
    import utils
except ImportError:
    from project import utils

try:
    import data_fetcher
except ImportError:
    data_fetcher = None


def start_background_fetch(interval_seconds: int = 300):
    if data_fetcher is None:
        return

    def worker():
        while True:
            try:
                data_fetcher.main()
            except Exception as exc:
                print(f"Background fetch failed: {exc}")
                
            try:
                from project import ai_insights
                from datetime import datetime
                daily = ai_insights.get_latest_insight("daily")
                if not daily or daily.timestamp.date() < datetime.now().date():
                    print("Generating daily AI insight...")
                    ai_insights.generate_insight("daily")
                    
                weekly = ai_insights.get_latest_insight("weekly")
                if not weekly or (datetime.now() - weekly.timestamp).days >= 7:
                    print("Generating weekly AI insight...")
                    ai_insights.generate_insight("weekly")
            except Exception as e:
                print(f"Background AI generation failed: {e}")
                
            time.sleep(interval_seconds)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()


@st.cache_resource
def get_background_fetcher(interval_seconds: int = 300):
    start_background_fetch(interval_seconds)
    return True


st.set_page_config(
    page_title="Social Analytics Dashboard",
    page_icon=":chart_with_upwards_trend:",
    layout="wide",
    initial_sidebar_state="expanded",
)

get_background_fetcher(60)

utils.inject_dashboard_style()
utils.setup_refresh()

with st.sidebar:
    st.markdown("### Live controls")
    if st.button("Fetch latest data", use_container_width=True):
        if data_fetcher is None:
            st.error("Data fetcher is not available.")
        else:
            with st.spinner("Collecting the newest analytics and generating fresh AI insights..."):
                try:
                    data_fetcher.main()
                    st.cache_data.clear()
                    
                    try:
                        from project import ai_insights
                        ai_insights.generate_insight("daily")
                    except Exception as ai_exc:
                        print(f"AI Insight generation failed during manual fetch: {ai_exc}")
                        
                    st.success("Latest data and insights fetched! Refreshing dashboard.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Fetch failed: {exc}")
    st.caption(f"Auto-refresh: every {utils.REFRESH_INTERVAL_MS // 1000}s")

utils.render_page_header(
    "Social Media Analytics Dashboard",
    "A live command center for Facebook and Instagram performance, refreshed from your local analytics database.",
)

col1, col2 = st.columns([3, 1])
with col1:
    st.subheader("Live Summary")
    st.markdown(
        "This dashboard reads data from `social_media.db` and reflects your latest Facebook and Instagram analytics snapshots. "
        "The background collector runs every 5 minutes while the app is open, and the browser view refreshes automatically."
    )

with col2:
    st.metric("Last Updated", utils.get_last_updated_text())

summary_df = utils.load_daily_summary()
followers_df = utils.load_followers_history()

if summary_df.empty and followers_df.empty:
    st.warning("No analytics data is available yet. Run the data collector to populate the database.")
else:
    total_posts = len(utils.load_all_posts())
    total_reach = int(summary_df["reach"].sum()) if not summary_df.empty else 0
    ig_views, fb_impressions, yt_views, total_views_impressions = utils.load_views_impressions()
    total_engagement = int(summary_df["engagement"].sum()) if not summary_df.empty else 0
    total_followers = int(followers_df.sort_values(by="date").tail(1)["followers"].squeeze()) if not followers_df.empty else 0
    platform_totals = utils.load_platform_totals()

    cards = st.columns(5)
    cards[0].metric("All Platforms - Posts", utils.format_count(total_posts))
    cards[1].metric("All Platforms - Reach", utils.format_count(total_reach))
    cards[2].metric("All Platforms - Views / Impressions", utils.format_count(total_views_impressions))
    cards[3].metric("All Platforms - Engagement", utils.format_count(total_engagement))
    cards[4].metric("All Platforms - Followers", utils.format_count(total_followers))

    st.markdown("---")
    card_row = st.columns(3)
    card_row[0].metric("Instagram Views", utils.format_count(ig_views))
    card_row[1].metric("Facebook Page Impressions", utils.format_count(fb_impressions))
    card_row[2].metric("YouTube Views", utils.format_count(yt_views))

    st.markdown("---")
    utils.render_platform_breakdown(platform_totals)

    st.markdown("---")
    st.info("Use the sidebar pages for executive trends, post performance, recent-post visualization, best posting time, and platform comparison.")
