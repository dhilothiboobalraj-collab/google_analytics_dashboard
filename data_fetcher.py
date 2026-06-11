"""Data fetcher module for Facebook and Instagram APIs."""
import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests
from sqlalchemy import inspect, text
from database import (
    engine,
    init_db,
    get_session,
    MetricData,
    FacebookPost,
    InstagramPost,
    YouTubeVideo,
    DailySummary,
    FollowersHistory,
    BestPostingTime,
    AlertsLog,
    TopPost,
)


BASE = "https://graph.facebook.com/v25.0"
FB_PAGE_ID = load_env_value("FB_PAGE_ID", "")
IG_USER_ID = load_env_value("IG_USER_ID", "")
MAX_POSTS = 50
WEEKLY_DAYS = 28


def load_env_value(key, default=""):
    """Load environment variable from .env file or system environment."""
    value = os.getenv(key)
    if value:
        return value

    env_path = ".env"
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8-sig") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                env_key, env_value = line.split("=", 1)
                if env_key.strip().lstrip("\ufeff") == key:
                    return env_value.strip().strip('"').strip("'")

    return default


def load_int_env(key, default=0):
    value = load_env_value(key, str(default))
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# Platform-specific alert thresholds for a medium-size account.
# Override in `.env` with ALERT_THRESHOLD_FACEBOOK or ALERT_THRESHOLD_INSTAGRAM.
ALERT_THRESHOLD_FACEBOOK = load_int_env("ALERT_THRESHOLD_FACEBOOK", 500)
ALERT_THRESHOLD_INSTAGRAM = load_int_env("ALERT_THRESHOLD_INSTAGRAM", 1000)
ALERT_THRESHOLD_YOUTUBE = load_int_env("ALERT_THRESHOLD_YOUTUBE", 5000)

USER_ACCESS_TOKEN = load_env_value("USER_ACCESS_TOKEN")
YOUTUBE_API_KEY = load_env_value("YOUTUBE_API_KEY")
YOUTUBE_CHANNEL_ID = load_env_value("YOUTUBE_CHANNEL_ID")


def get_page_token():
    """Exchange the user token for the Page token."""
    print("Getting Page Access Token...")
    resp = requests.get(
        f"{BASE}/me/accounts",
        params={
            "fields": "id,name,access_token",
            "access_token": USER_ACCESS_TOKEN,
        },
        timeout=30,
    ).json()

    print(f"FB /me/accounts raw response: {json.dumps(resp, indent=2, ensure_ascii=False)}")

    if "error" in resp:
        return None, resp["error"].get("message", "Token error")

    for page in resp.get("data", []):
        if page.get("id") == FB_PAGE_ID:
            print(f"Got Page Token for {page.get('name', FB_PAGE_ID)}")
            return page.get("access_token"), None

    return None, f"Page ID {FB_PAGE_ID} not found"


def fetch_fb_weekly_insights(page_token, days_back=WEEKLY_DAYS):
    """Fetch Facebook page weekly insights."""
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days_back)

    print(f"Fetching FB weekly insights: {start_date} to {end_date}")

    url = f"{BASE}/{FB_PAGE_ID}/insights"
    params = {
        "metric": "page_posts_impressions",
        "period": "day",
        "since": start_date.strftime("%Y-%m-%d"),
        "until": end_date.strftime("%Y-%m-%d"),
        "access_token": page_token,
    }

    resp = requests.get(url, params=params, timeout=30).json()
    print(f"FB Weekly Raw Response: {json.dumps(resp, indent=2, ensure_ascii=False)}")

    if "error" in resp:
        return [], resp["error"].get("message", "FB weekly insights error")

    rows = []
    for metric in resp.get("data", []):
        for value in metric.get("values", []):
            rows.append(
                {
                    "date": value.get("end_time", "")[:10],
                    "metric": metric.get("name"),
                    "value": value.get("value", 0),
                }
            )

    if not rows:
        return [], "FB weekly returned empty data array"

    return rows, None


def fetch_ig_weekly_insights(user_token, days_back=WEEKLY_DAYS):
    """Fetch Instagram account weekly insights."""
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days_back)

    print(f"Fetching IG weekly insights: {start_date} to {end_date}")

    url = f"{BASE}/{IG_USER_ID}/insights"
    all_rows = []

    params1 = {
        "metric": "views,reach",
        "period": "day",
        "since": start_date.strftime("%Y-%m-%d"),
        "until": end_date.strftime("%Y-%m-%d"),
        "access_token": user_token,
    }
    resp1 = requests.get(url, params=params1, timeout=30).json()
    print(f"IG Weekly Raw Response (views/reach): {json.dumps(resp1, indent=2, ensure_ascii=False)}")
    if "error" not in resp1:
        for metric in resp1.get("data", []):
            for value in metric.get("values", []):
                all_rows.append(
                    {
                        "date": value.get("end_time", "")[:10],
                        "metric": metric.get("name"),
                        "value": value.get("value", 0),
                    }
                )

    params2 = {
        "metric": "profile_views,accounts_engaged,total_interactions",
        "period": "day",
        "metric_type": "total_value",
        "since": start_date.strftime("%Y-%m-%d"),
        "until": end_date.strftime("%Y-%m-%d"),
        "access_token": user_token,
    }
    resp2 = requests.get(url, params=params2, timeout=30).json()
    print(f"IG Weekly Raw Response (total_value): {json.dumps(resp2, indent=2, ensure_ascii=False)}")
    if "error" not in resp2:
        for metric in resp2.get("data", []):
            all_rows.append(
                {
                    "date": end_date.strftime("%Y-%m-%d"),
                    "metric": f"{metric.get('name')}_total",
                    "value": metric.get("total_value", {}).get("value", 0),
                }
            )

    if not all_rows:
        return [], "IG weekly returned empty data array"

    return all_rows, None


def fetch_facebook_posts(page_token, max_posts=MAX_POSTS):
    """Fetch Facebook page posts with engagement metrics."""
    print("Fetching Facebook posts...")

    overview = requests.get(
        f"{BASE}/{FB_PAGE_ID}",
        params={
            "fields": "name,fan_count,followers_count,category,about",
            "access_token": page_token,
        },
        timeout=30,
    ).json()

    if "error" in overview:
        return {
            "error": overview["error"].get("message", "Facebook overview fetch failed"),
            "overview": None,
            "fan_count": 0,
            "total_posts": 0,
            "posts": [],
        }

    fan_count = overview.get("fan_count", 0) or 0
    print(f"Got Page: {overview.get('name', FB_PAGE_ID)} | Fans: {fan_count}")

    all_posts = []
    url = f"{BASE}/{FB_PAGE_ID}/posts"
    params = {
        "fields": "id,created_time,message,permalink_url",
        "limit": max_posts,
        "access_token": page_token,
    }

    while url and len(all_posts) < max_posts:
        resp = requests.get(url, params=params if url.endswith("/posts") else {}, timeout=30).json()
        if "error" in resp:
            return {
                "error": resp["error"].get("message", "Facebook posts fetch failed"),
                "overview": overview,
                "fan_count": fan_count,
                "total_posts": len(all_posts),
                "posts": all_posts,
            }

        posts = resp.get("data", [])
        if not posts:
            break

        for post in posts:
            if len(all_posts) >= max_posts:
                break

            pid = post["id"]
            print(f"Processing Facebook post {len(all_posts) + 1}/{max_posts}: {pid}")

            stats = requests.get(
                f"{BASE}/{pid}",
                params={
                    "fields": "reactions.summary(true),comments.summary(true),shares",
                    "access_token": page_token,
                },
                timeout=30,
            ).json()

            insights = requests.get(
                f"{BASE}/{pid}/insights",
                params={
                    "metric": "post_impressions,post_reach,post_clicks",
                    "period": "lifetime",
                    "access_token": page_token,
                },
                timeout=30,
            ).json()

            stats_error = stats.get("error", {}).get("message") if isinstance(stats, dict) else None
            insights_error = insights.get("error", {}).get("message") if isinstance(insights, dict) else None

            reach_data = {}
            for item in insights.get("data", []) if isinstance(insights, dict) else []:
                values = item.get("values", [])
                if values:
                    reach_data[item.get("name")] = values[-1].get("value", 0)

            if isinstance(insights, dict) and "data" in insights and not any(item.get("values") for item in insights.get("data", [])):
                print(f"Facebook post {pid} insights returned empty values: {insights}")

            reactions = stats.get("reactions", {}).get("summary", {}).get("total_count", 0) if isinstance(stats, dict) else 0
            comments = stats.get("comments", {}).get("summary", {}).get("total_count", 0) if isinstance(stats, dict) else 0
            shares = stats.get("shares", {}).get("count", 0) if isinstance(stats, dict) else 0
            total_engagement = reactions + comments + shares

            all_posts.append(
                {
                    "post_id": pid,
                    "created_time": post.get("created_time"),
                    "permalink_url": post.get("permalink_url"),
                    "date": post["created_time"][:10],
                    "time": post["created_time"][11:19],
                    "timestamp": datetime.fromisoformat(post["created_time"].replace("Z", "+00:00")),
                    "message": post.get("message", "Media Post")[:300],
                    "reactions": reactions,
                    "comments": comments,
                    "shares": shares,
                    "total_engagement": total_engagement,
                    "engagement_rate": round(total_engagement / fan_count * 100, 3) if fan_count > 0 else 0,
                    "post_reach": reach_data.get("post_reach", 0),
                    "post_impressions": reach_data.get("post_impressions", 0),
                    "post_clicks": reach_data.get("post_clicks", 0),
                    "stats_error": stats_error,
                    "insights_error": insights_error,
                }
            )
            time.sleep(0.15)

        url = resp.get("paging", {}).get("next")
        params = {}
        print(f"Facebook posts collected: {len(all_posts)}")

    return {
        "error": None,
        "overview": overview,
        "fan_count": fan_count,
        "total_posts": len(all_posts),
        "posts": all_posts,
    }


def fetch_instagram_posts(user_token, max_posts=MAX_POSTS):
    """Fetch Instagram media posts with engagement and insights."""
    print("Fetching Instagram posts...")

    account_data = requests.get(
        f"{BASE}/{IG_USER_ID}",
        params={
            "fields": "username,followers_count,follows_count,media_count,biography,website",
            "access_token": user_token,
        },
        timeout=30,
    ).json()

    if "error" in account_data:
        return {
            "error": account_data["error"].get("message", "Instagram account fetch failed"),
            "account": None,
            "total_posts": 0,
            "posts": [],
        }

    all_posts = []
    posts_url = f"{BASE}/{IG_USER_ID}/media"
    posts_params = {
        "fields": "id,caption,timestamp,like_count,comments_count,media_type,media_product_type,permalink,insights.metric(impressions,reach,saved,shares,total_interactions)",
        "access_token": user_token,
        "limit": max_posts,
    }

    next_url = posts_url
    while next_url:
        resp = requests.get(next_url, params=posts_params if next_url == posts_url else {}, timeout=30).json()
        if "error" in resp:
            return {
                "error": resp["error"].get("message", "Instagram posts fetch failed"),
                "account": account_data,
                "total_posts": len(all_posts),
                "posts": all_posts,
            }

        media_items = resp.get("data", [])
        if not media_items:
            break

        for media in media_items:
            if len(all_posts) >= max_posts:
                break

            insights = {}
            if isinstance(media.get("insights"), dict):
                for metric in media["insights"].get("data", []):
                    values = metric.get("values", [])
                    if values:
                        insights[metric.get("name")] = values[0].get("value", 0)

            like_count = media.get("like_count", 0) or 0
            comments_count = media.get("comments_count", 0) or 0
            shares = insights.get("shares", 0) or 0
            reach = insights.get("reach", 0) or 0
            engagement_rate = round((like_count + comments_count + shares) / reach * 100, 3) if reach > 0 else 0.0

            all_posts.append(
                {
                    "media_id": media.get("id"),
                    "date": media.get("timestamp", "")[:10],
                    "time": media.get("timestamp", "")[11:19] if media.get("timestamp") else "",
                    "timestamp": datetime.fromisoformat(media["timestamp"].replace("Z", "+00:00")) if media.get("timestamp") else None,
                    "caption": media.get("caption", "").strip()[:300],
                    "like_count": like_count,
                    "comments_count": comments_count,
                    "media_type": media.get("media_type"),
                    "media_product_type": media.get("media_product_type"),
                    "permalink": media.get("permalink"),
                    "impressions": insights.get("impressions", 0),
                    "reach": reach,
                    "saved": insights.get("saved", 0),
                    "shares": shares,
                    "video_views": insights.get("video_views", 0),
                    "plays": insights.get("plays", 0),
                    "total_interactions": insights.get("total_interactions", 0),
                    "engagement_rate": engagement_rate,
                }
            )

        next_url = resp.get("paging", {}).get("next")
        posts_params = {}

    return {
        "error": None,
        "account": account_data,
        "total_posts": len(all_posts),
        "posts": all_posts,
    }



def fetch_youtube_videos(api_key, channel_id, max_videos=MAX_POSTS):
    """Fetch YouTube channel stats and recent videos."""
    print("Fetching YouTube data...")
    if not api_key or not channel_id:
        return {"error": "Missing YouTube credentials", "channel": None, "subscriber_count": 0, "videos": []}
        
    channel_url = f"https://www.googleapis.com/youtube/v3/channels?part=statistics,snippet&id={channel_id}&key={api_key}"
    try:
        channel_resp = requests.get(channel_url, timeout=30).json()
    except Exception as e:
        return {"error": str(e), "channel": None, "subscriber_count": 0, "videos": []}
        
    if "error" in channel_resp:
        return {"error": channel_resp["error"].get("message"), "channel": None, "subscriber_count": 0, "videos": []}
        
    if not channel_resp.get("items"):
        return {"error": "Channel not found", "channel": None, "subscriber_count": 0, "videos": []}
        
    channel_info = channel_resp["items"][0]
    stats = channel_info.get("statistics", {})
    subscriber_count = int(stats.get("subscriberCount", 0))
    
    search_url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&channelId={channel_id}&maxResults={max_videos}&order=date&type=video&key={api_key}"
    try:
        search_resp = requests.get(search_url, timeout=30).json()
    except Exception as e:
        return {"error": str(e), "channel": channel_info, "subscriber_count": subscriber_count, "videos": []}
        
    if "error" in search_resp:
        return {"error": search_resp["error"].get("message"), "channel": channel_info, "subscriber_count": subscriber_count, "videos": []}
        
    video_ids = [item["id"]["videoId"] for item in search_resp.get("items", []) if item["id"].get("videoId")]
    if not video_ids:
        return {"error": None, "channel": channel_info, "subscriber_count": subscriber_count, "videos": []}
        
    videos_url = f"https://www.googleapis.com/youtube/v3/videos?part=statistics,snippet&id={','.join(video_ids)}&key={api_key}"
    try:
        videos_resp = requests.get(videos_url, timeout=30).json()
    except Exception as e:
        return {"error": str(e), "channel": channel_info, "subscriber_count": subscriber_count, "videos": []}
        
    videos = []
    for item in videos_resp.get("items", []):
        snippet = item.get("snippet", {})
        statistics = item.get("statistics", {})
        
        published_at = snippet.get("publishedAt", "")
        try:
            dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
            date_str = dt.strftime("%Y-%m-%d")
            time_str = dt.strftime("%H:%M:%S")
        except Exception:
            date_str = ""
            time_str = ""
            dt = datetime.now()
            
        view_count = int(statistics.get("viewCount", 0))
        like_count = int(statistics.get("likeCount", 0))
        comment_count = int(statistics.get("commentCount", 0))
        engagement = like_count + comment_count
        engagement_rate = round((engagement / view_count) * 100, 3) if view_count > 0 else 0.0
        
        videos.append({
            "video_id": item["id"],
            "date": date_str,
            "time": time_str,
            "timestamp": dt,
            "title": snippet.get("title", ""),
            "description": snippet.get("description", "")[:5000],
            "view_count": view_count,
            "like_count": like_count,
            "comment_count": comment_count,
            "engagement_rate": engagement_rate,
            "thumbnail_url": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
            "permalink": f"https://www.youtube.com/watch?v={item['id']}"
        })
        
    return {
        "error": None,
        "channel": channel_info,
        "subscriber_count": subscriber_count,
        "videos": videos
    }


def save_to_csv(records, filename, output_dir="output"):
    """Save records to CSV file."""
    if not records:
        print(f"No records to save for {filename}")
        return

    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, filename)
    pd.DataFrame.from_records(records).to_csv(filepath, index=False, encoding="utf-8-sig")
    print(f"Saved {len(records)} records to {filepath}")


def save_to_database(records, table_name):
    """Save records to SQLite database."""
    if not records:
        print(f"No records to save for {table_name}")
        return

    df = pd.DataFrame(records)
    inspector = inspect(engine)
    if inspector.has_table(table_name):
        existing_columns = [col["name"] for col in inspector.get_columns(table_name)]
        df = df[[c for c in df.columns if c in existing_columns]]

        if table_name in ("fb_weekly_insights", "ig_weekly_insights") and "date" in df.columns and "metric" in df.columns:
            with engine.begin() as conn:
                for _, row in df.iterrows():
                    conn.execute(
                        text(f"DELETE FROM {table_name} WHERE date = :date AND metric = :metric"),
                        {"date": row.get("date"), "metric": row.get("metric")},
                    )

    df.to_sql(table_name, engine, if_exists="append", index=False)
    print(f"Saved {len(records)} records to database table: {table_name}")


def save_posts_to_db(records, model_class, id_field):
    """Upsert post records into ORM-backed table using SQLAlchemy session.

    - records: list of dicts
    - model_class: ORM class (FacebookPost or InstagramPost)
    - id_field: unique identifier field name in record (e.g., 'post_id' or 'media_id')
    """
    if not records:
        print(f"No post records to save for {model_class.__tablename__}")
        return

    session = get_session()
    try:
        for rec in records:
            key = rec.get(id_field)
            if not key:
                continue

            existing = (
                session.query(model_class).filter(getattr(model_class, id_field) == key).one_or_none()
            )

            if existing:
                for k, v in rec.items():
                    if hasattr(existing, k):
                        setattr(existing, k, v)
            else:
                # Only pass kwargs that the model accepts
                obj_kwargs = {k: v for k, v in rec.items() if hasattr(model_class, k)}
                obj = model_class(**obj_kwargs)
                session.add(obj)

        session.commit()
        print(f"Upserted {len(records)} records into {model_class.__tablename__}")
    except Exception as e:
        session.rollback()
        print(f"Error saving posts to db: {e}")
    finally:
        session.close()


def save_metrics_to_db(metric_records):
    """Save normalized metric data to metrics table for Power BI."""
    if not metric_records:
        print("No metrics to save")
        return

    # Clean up any duplicate metric rows so old repeated collections do not inflate totals.
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "DELETE FROM metrics WHERE rowid NOT IN (SELECT MIN(rowid) FROM metrics GROUP BY date, time, metric, source, category)"
                )
            )
    except Exception as e:
        print(f"Warning: metrics dedupe failed: {e}")
    
    session = get_session()
    try:
        for record in metric_records:
            record_time = record.get("time") or ""
            record_category = record.get("category") or ""
            if record.get("date") and record.get("metric") and record.get("source"):
                session.execute(
                    text(
                        "DELETE FROM metrics WHERE date = :date AND time = :time AND metric = :metric AND source = :source AND category = :category"
                    ),
                    {
                        "date": record.get("date"),
                        "time": record_time,
                        "metric": record.get("metric"),
                        "source": record.get("source"),
                        "category": record_category,
                    },
                )

            metric = MetricData(
                date=record.get("date"),
                time=record_time,
                timestamp=datetime.fromisoformat(f"{record.get('date')} {record.get('time', '00:00:00')}") if record.get("date") else datetime.now(),
                metric=record.get("metric"),
                source=record.get("source"),
                category=record_category,
                value=record.get("value", 0),
                unit=record.get("unit", "count")
            )
            session.add(metric)
        
        session.commit()
        print(f"Saved {len(metric_records)} metric records to Power BI metrics table")
    except Exception as e:
        session.rollback()
        print(f"Error saving metrics: {e}")
    finally:
        session.close()


def send_alert(platform, title, payload=None):
    """Simple alert hook — logs the alert and stores the alert in SQLite."""
    msg = f"ALERT [{platform.upper()}] {title}"
    print(msg)
    try:
        os.makedirs("output", exist_ok=True)
        with open(os.path.join("output", "alerts.log"), "a", encoding="utf-8") as f:
            f.write(f"{datetime.utcnow().isoformat()} | {platform} | {title}\n")
    except Exception:
        pass

    try:
        session = get_session()
        session.add(
            AlertsLog(
                platform=platform,
                alert_type="reach_threshold",
                message=title,
                details=json.dumps(payload, default=str, ensure_ascii=False) if payload else None,
                timestamp=datetime.utcnow(),
            )
        )
        session.commit()
    except Exception as e:
        try:
            session.rollback()
        except Exception:
            pass
        print(f"Error saving alert to database: {e}")
    finally:
        try:
            session.close()
        except Exception:
            pass


def compute_daily_summary_and_followers(fb_fans=None, ig_followers=None, yt_subscribers=None, summary_date=None):
    """Aggregate daily reach/impressions/engagement and store followers snapshot."""
    session = get_session()
    summary_date = summary_date or datetime.now().strftime("%Y-%m-%d")
    try:
        # Facebook daily
        try:
            fb_df = pd.read_sql_table("facebook_posts", engine)
        except Exception:
            fb_df = pd.DataFrame()

        if not fb_df.empty:
            fb_agg = fb_df.groupby("date").agg({
                "post_reach": "sum",
                "post_impressions": "sum",
                "total_engagement": "sum",
            }).reset_index()

            # If post-level reach/impressions are missing, fall back to page-level insights stored in metrics.
            if fb_agg["post_reach"].sum() == 0 and fb_agg["post_impressions"].sum() == 0:
                try:
                    metrics_df = pd.read_sql_query(
                        "SELECT date, metric, SUM(value) as total FROM metrics WHERE source = 'facebook' AND metric IN ('page_impressions', 'page_posts_impressions') GROUP BY date, metric",
                        engine,
                    )
                    if not metrics_df.empty:
                        fb_agg = metrics_df.pivot(index='date', columns='metric', values='total').reset_index().fillna(0)
                        if 'page_impressions' in fb_agg.columns:
                            fb_agg['post_reach'] = fb_agg['page_impressions'].astype(int)
                        elif 'page_posts_impressions' in fb_agg.columns:
                            fb_agg['post_reach'] = fb_agg['page_posts_impressions'].astype(int)
                        else:
                            fb_agg['post_reach'] = 0

                        if 'page_posts_impressions' in fb_agg.columns:
                            fb_agg['post_impressions'] = fb_agg['page_posts_impressions'].astype(int)
                        elif 'page_impressions' in fb_agg.columns:
                            fb_agg['post_impressions'] = fb_agg['page_impressions'].astype(int)
                        else:
                            fb_agg['post_impressions'] = 0

                        fb_agg['total_engagement'] = 0
                except Exception:
                    pass

            for _, row in fb_agg.iterrows():
                date = row["date"]
                reach = int(row.get("post_reach", 0) or 0)
                impressions = int(row.get("post_impressions", 0) or 0)
                engagement = int(row.get("total_engagement", 0) or 0)

                existing = (
                    session.query(DailySummary)
                    .filter(DailySummary.date == date, DailySummary.platform == "facebook")
                    .one_or_none()
                )
                if existing:
                    existing.reach = reach
                    existing.impressions = impressions
                    existing.engagement = engagement
                else:
                    session.add(DailySummary(date=date, platform="facebook", reach=reach, impressions=impressions, engagement=engagement))

        # Instagram daily
        try:
            ig_df = pd.read_sql_table("instagram_posts", engine)
        except Exception:
            ig_df = pd.DataFrame()

        if not ig_df.empty:
            ig_agg = ig_df.groupby("date").agg({
                "reach": "sum",
                "impressions": "sum",
                "total_interactions": "sum",
            }).reset_index()

            if ig_agg["impressions"].sum() == 0:
                try:
                    view_rows = pd.read_sql_query(
                        "SELECT date, SUM(value) as impressions FROM metrics WHERE source = 'instagram' AND metric = 'views' GROUP BY date",
                        engine,
                    )
                    if not view_rows.empty:
                        ig_agg = view_rows.rename(columns={"impressions": "impressions"})
                        ig_agg["reach"] = 0
                        ig_agg["total_interactions"] = 0
                except Exception:
                    pass

            for _, row in ig_agg.iterrows():
                date = row["date"]
                reach = int(row.get("reach", 0) or 0)
                impressions = int(row.get("impressions", 0) or 0)
                engagement = int(row.get("total_interactions", 0) or 0)

                existing = (
                    session.query(DailySummary)
                    .filter(DailySummary.date == date, DailySummary.platform == "instagram")
                    .one_or_none()
                )
                if existing:
                    existing.reach = reach
                    existing.impressions = impressions
                    existing.engagement = engagement
                else:
                    session.add(DailySummary(date=date, platform="instagram", reach=reach, impressions=impressions, engagement=engagement))


        # YouTube daily
        try:
            yt_df = pd.read_sql_table("youtube_videos", engine)
        except Exception:
            yt_df = pd.DataFrame()

        if not yt_df.empty:
            yt_df['engagement'] = yt_df['like_count'] + yt_df['comment_count']
            yt_agg = yt_df.groupby("date").agg({
                "view_count": "sum",
                "engagement": "sum",
            }).reset_index()

            for _, row in yt_agg.iterrows():
                date = row["date"]
                views = int(row.get("view_count", 0) or 0)
                engagement = int(row.get("engagement", 0) or 0)

                existing = (
                    session.query(DailySummary)
                    .filter(DailySummary.date == date, DailySummary.platform == "youtube")
                    .one_or_none()
                )
                if existing:
                    existing.impressions = views
                    existing.reach = views
                    existing.engagement = engagement
                else:
                    session.add(DailySummary(date=date, platform="youtube", reach=views, impressions=views, engagement=engagement))

        def _calculate_growth(platform, current_followers):

            if current_followers is None:
                return 0.0
            previous = (
                session.query(FollowersHistory)
                .filter(FollowersHistory.platform == platform, FollowersHistory.date < summary_date)
                .order_by(FollowersHistory.date.desc())
                .first()
            )
            if previous and previous.followers > 0:
                return round((current_followers - previous.followers) / previous.followers * 100, 3)
            return 0.0

        if fb_fans is not None:
            fb_growth = _calculate_growth("facebook", fb_fans)
            existing_fh = (
                session.query(FollowersHistory)
                .filter(FollowersHistory.date == summary_date, FollowersHistory.platform == "facebook")
                .one_or_none()
            )
            if existing_fh:
                existing_fh.followers = fb_fans
                existing_fh.growth_rate = fb_growth
            else:
                session.add(FollowersHistory(date=summary_date, platform="facebook", followers=fb_fans, growth_rate=fb_growth))

            existing_summary = (
                session.query(DailySummary)
                .filter(DailySummary.date == summary_date, DailySummary.platform == "facebook")
                .one_or_none()
            )
            if existing_summary:
                existing_summary.followers = fb_fans
                existing_summary.followers_growth = fb_growth
            else:
                session.add(DailySummary(date=summary_date, platform="facebook", followers=fb_fans, followers_growth=fb_growth))

        if ig_followers is not None:
            ig_growth = _calculate_growth("instagram", ig_followers)
            existing_fh = (
                session.query(FollowersHistory)
                .filter(FollowersHistory.date == summary_date, FollowersHistory.platform == "instagram")
                .one_or_none()
            )
            if existing_fh:
                existing_fh.followers = ig_followers
                existing_fh.growth_rate = ig_growth
            else:
                session.add(FollowersHistory(date=summary_date, platform="instagram", followers=ig_followers, growth_rate=ig_growth))

            existing_summary = (
                session.query(DailySummary)
                .filter(DailySummary.date == summary_date, DailySummary.platform == "instagram")
                .one_or_none()
            )
            if existing_summary:
                existing_summary.followers = ig_followers
                existing_summary.followers_growth = ig_growth
            else:
                session.add(DailySummary(date=summary_date, platform="instagram", followers=ig_followers, followers_growth=ig_growth))


        if yt_subscribers is not None:
            yt_growth = _calculate_growth("youtube", yt_subscribers)
            existing_fh = (
                session.query(FollowersHistory)
                .filter(FollowersHistory.date == summary_date, FollowersHistory.platform == "youtube")
                .one_or_none()
            )
            if existing_fh:
                existing_fh.followers = yt_subscribers
                existing_fh.growth_rate = yt_growth
            else:
                session.add(FollowersHistory(date=summary_date, platform="youtube", followers=yt_subscribers, growth_rate=yt_growth))

            existing_summary = (
                session.query(DailySummary)
                .filter(DailySummary.date == summary_date, DailySummary.platform == "youtube")
                .one_or_none()
            )
            if existing_summary:
                existing_summary.followers = yt_subscribers
                existing_summary.followers_growth = yt_growth
            else:
                session.add(DailySummary(date=summary_date, platform="youtube", followers=yt_subscribers, followers_growth=yt_growth))

        session.commit()
        print("Computed and saved daily summary and follower snapshots.")
    except Exception as e:
        session.rollback()
        print(f"Error computing daily summary: {e}")
    finally:
        session.close()


def compute_best_posting_time_and_top_posts(top_n=10):
    """Compute average engagement per posting hour and top posts overall."""
    session = get_session()
    try:
        try:
            fb_df = pd.read_sql_table("facebook_posts", engine)
        except Exception:
            fb_df = pd.DataFrame()

        try:
            ig_df = pd.read_sql_table("instagram_posts", engine)
        except Exception:
            ig_df = pd.DataFrame()

        combined = pd.DataFrame()
        if not fb_df.empty:
            fb_df = fb_df.rename(columns={"reactions": "likes", "total_engagement": "engagement"})
            fb_df["platform"] = "facebook"
            combined = pd.concat([combined, fb_df], ignore_index=True, sort=False)
        if not ig_df.empty:
            ig_df = ig_df.rename(columns={"like_count": "likes", "total_interactions": "engagement"})
            ig_df["platform"] = "instagram"
            combined = pd.concat([combined, ig_df], ignore_index=True, sort=False)

        if not combined.empty:
            # Ensure a datetime field
            if "created_time" in combined.columns:
                combined["created_time_parsed"] = pd.to_datetime(combined["created_time"], errors="coerce")
            else:
                combined["created_time_parsed"] = pd.to_datetime(combined["date"] + " " + combined.get("time", "00:00:00"), errors="coerce")

            # Safely extract hour, handling NaT values
            def _safe_hour(ts):
                try:
                    if pd.isna(ts):
                        return -1
                    return int(ts.hour)
                except Exception:
                    return -1

            combined["hour"] = combined["created_time_parsed"].apply(_safe_hour)

            hour_grp = combined.groupby("hour").agg({"engagement": "mean"}).reset_index()
            # Clear existing best_posting_time table
            session.query(BestPostingTime).delete()
            for _, row in hour_grp.iterrows():
                if row["hour"] >= 0:
                    session.add(BestPostingTime(hour=int(row["hour"]), avg_engagement=float(row["engagement"] or 0)))

            # Top posts
            combined["engagement"] = combined["engagement"].apply(lambda v: int(v) if pd.notna(v) else 0)
            top_posts_df = combined.sort_values("engagement", ascending=False).head(top_n)

            # Clear existing top_posts table
            session.query(TopPost).delete()

            def _safe_int(val):
                try:
                    if pd.isna(val):
                        return 0
                    return int(val)
                except Exception:
                    try:
                        return int(float(val))
                    except Exception:
                        return 0

            def _safe_id(primary, fallback):
                if pd.notna(primary) and primary != "":
                    return str(primary)
                if pd.notna(fallback) and fallback != "":
                    return str(fallback)
                return None

            def _safe_comments(row):
                if pd.notna(row.get("comments")):
                    return _safe_int(row.get("comments"))
                return _safe_int(row.get("comments_count"))

            for _, row in top_posts_df.iterrows():
                pid = _safe_id(row.get("post_id"), row.get("media_id"))
                if not pid:
                    continue

                session.add(
                    TopPost(
                        post_id=pid,
                        platform=row.get("platform"),
                        date=row.get("date"),
                        time=row.get("time"),
                        caption=row.get("message") or row.get("caption"),
                        likes=_safe_int(row.get("likes", 0)),
                        comments=_safe_comments(row),
                        shares=_safe_int(row.get("shares", 0)),
                        engagement=_safe_int(row.get("engagement", 0)),
                    )
                )

        session.commit()
        print("Computed best posting times and top posts.")
    except Exception as e:
        session.rollback()
        print(f"Error computing posting time/top posts: {e}")
    finally:
        session.close()


def export_dashboard_data(page_token, user_token):
    """Fetch and export all dashboard data with Power BI metrics table."""
    print("\n=== Starting Data Export ===\n")
    
    # Initialize database with Power BI schema
    init_db()

    # Fetch Facebook insights
    fb_insights, fb_insights_error = fetch_fb_weekly_insights(page_token)
    if fb_insights_error:
        print(f"Facebook insights error: {fb_insights_error}")
    else:
        save_to_csv(fb_insights, "fb_weekly_insights.csv")
        save_to_database(fb_insights, "fb_weekly_insights")
        
        # Save to Power BI metrics table
        metrics = [
            {
                "date": insight["date"],
                "time": "00:00:00",
                "metric": insight["metric"],
                "source": "facebook",
                "category": "page_insights",
                "value": insight["value"],
                "unit": "impressions" if "impression" in insight["metric"].lower() else "count"
            }
            for insight in fb_insights
        ]
        save_metrics_to_db(metrics)

    # Fetch Facebook posts
    fb_response = fetch_facebook_posts(page_token)
    if fb_response.get("error"):
        print(f"Facebook posts error: {fb_response['error']}")
    else:
        fb_posts = fb_response.get("posts", [])
        save_to_csv(fb_posts, "fb_posts.csv")
        # Upsert posts into ORM-backed table so historical snapshots are preserved
        save_posts_to_db(fb_posts, FacebookPost, "post_id")
        # Alerting: notify if any post impressions exceed threshold
        fb_threshold = ALERT_THRESHOLD_FACEBOOK
        for post in fb_posts:
            try:
                imps = int(post.get("post_impressions", 0) or 0)
                if imps >= fb_threshold:
                    send_alert(
                        "facebook",
                        f"Post {post.get('post_id')} reached {imps} impressions",
                        post,
                    )
            except Exception:
                continue
        
        # Save post engagement metrics to Power BI table
        post_metrics = []
        for post in fb_posts:
            post_metrics.append(
                {
                    "date": post["date"],
                    "time": post.get("time", "00:00:00"),
                    "metric": "total_engagement",
                    "source": "facebook",
                    "category": "post_engagement",
                    "value": post["total_engagement"],
                    "unit": "count"
                }
            )
            post_metrics.append(
                {
                    "date": post["date"],
                    "time": post.get("time", "00:00:00"),
                    "metric": "engagement_rate",
                    "source": "facebook",
                    "category": "post_engagement",
                    "value": post.get("engagement_rate", 0),
                    "unit": "percentage"
                }
            )
        save_metrics_to_db(post_metrics)

    # Fetch Instagram insights
    ig_insights, ig_insights_error = fetch_ig_weekly_insights(user_token)
    if ig_insights_error:
        print(f"Instagram insights error: {ig_insights_error}")
    else:
        save_to_csv(ig_insights, "ig_weekly_insights.csv")
        save_to_database(ig_insights, "ig_weekly_insights")
        
        # Save to Power BI metrics table
        metrics = [
            {
                "date": insight["date"],
                "time": "00:00:00",
                "metric": insight["metric"],
                "source": "instagram",
                "category": "account_insights",
                "value": insight["value"],
                "unit": "views" if "views" in insight["metric"].lower() else "reach" if "reach" in insight["metric"].lower() else "count"
            }
            for insight in ig_insights
        ]
        save_metrics_to_db(metrics)

    # Fetch Instagram posts
    ig_response = fetch_instagram_posts(user_token)
    if ig_response.get("error"):
        print(f"Instagram posts error: {ig_response['error']}")
    else:
        ig_posts = ig_response.get("posts", [])
        save_to_csv(ig_posts, "ig_posts.csv")
        save_posts_to_db(ig_posts, InstagramPost, "media_id")
        # Alerting for Instagram impressions
        ig_threshold = ALERT_THRESHOLD_INSTAGRAM
        for post in ig_posts:
            try:
                imps = int(post.get("impressions", 0) or 0)
                if imps >= ig_threshold:
                    send_alert(
                        "instagram",
                        f"Media {post.get('media_id')} reached {imps} impressions",
                        post,
                    )
            except Exception:
                continue
        
        # Save media engagement metrics to Power BI table
        post_metrics = []
        for post in ig_posts:
            post_metrics.append(
                {
                    "date": post["date"],
                    "time": post.get("time", "00:00:00"),
                    "metric": "total_interactions",
                    "source": "instagram",
                    "category": "media_engagement",
                    "value": post["total_interactions"],
                    "unit": "count"
                }
            )
            post_metrics.append(
                {
                    "date": post["date"],
                    "time": post.get("time", "00:00:00"),
                    "metric": "engagement_rate",
                    "source": "instagram",
                    "category": "media_engagement",
                    "value": post.get("engagement_rate", 0),
                    "unit": "percentage"
                }
            )
        save_metrics_to_db(post_metrics)

    
    # Fetch YouTube videos
    yt_response = fetch_youtube_videos(YOUTUBE_API_KEY, YOUTUBE_CHANNEL_ID)
    if yt_response.get("error"):
        print(f"YouTube videos error: {yt_response['error']}")
    else:
        yt_videos = yt_response.get("videos", [])
        save_to_csv(yt_videos, "yt_videos.csv")
        save_posts_to_db(yt_videos, YouTubeVideo, "video_id")
        
        # Alerting for YouTube views
        yt_threshold = ALERT_THRESHOLD_YOUTUBE
        for video in yt_videos:
            try:
                views = int(video.get("view_count", 0) or 0)
                if views >= yt_threshold:
                    send_alert(
                        "youtube",
                        f"Video {video.get('video_id')} reached {views} views",
                        video,
                    )
            except Exception:
                continue
        
        # Save video engagement metrics to Power BI table
        post_metrics = []
        for video in yt_videos:
            post_metrics.append(
                {
                    "date": video["date"],
                    "time": video.get("time", "00:00:00"),
                    "metric": "total_interactions",
                    "source": "youtube",
                    "category": "video_engagement",
                    "value": video["like_count"] + video["comment_count"],
                    "unit": "count"
                }
            )
            post_metrics.append(
                {
                    "date": video["date"],
                    "time": video.get("time", "00:00:00"),
                    "metric": "engagement_rate",
                    "source": "youtube",
                    "category": "video_engagement",
                    "value": video.get("engagement_rate", 0),
                    "unit": "percentage"
                }
            )
        save_metrics_to_db(post_metrics)

    print("\n=== Data Export Complete ===\n")

    # Compute and persist analytics: daily summaries, followers snapshots, best posting times, top posts
    compute_daily_summary_and_followers(
        fb_fans=fb_response.get("fan_count") if fb_response else None,
        ig_followers=ig_response.get("account", {}).get("followers_count") if ig_response and ig_response.get("account") else None,
        yt_subscribers=yt_response.get("subscriber_count") if yt_response else None,
    )
    compute_best_posting_time_and_top_posts()

    print("Database ready for Power BI integration!")
    print("Tables available: metrics (Power BI), facebook_posts, instagram_posts, daily_summary, followers_history, best_posting_time, top_posts, etc.")
    print_run_summary()


def print_run_summary():
    db_path = Path("social_media.db")
    updated = "unknown"
    if db_path.exists():
        updated = datetime.fromtimestamp(db_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")

    with engine.connect() as conn:
        fb_posts_count = conn.execute(text("SELECT COUNT(*) FROM facebook_posts")).scalar() or 0
        ig_posts_count = conn.execute(text("SELECT COUNT(*) FROM instagram_posts")).scalar() or 0
        daily_summary_count = conn.execute(text("SELECT COUNT(*) FROM daily_summary")).scalar() or 0
        metrics_count = conn.execute(text("SELECT COUNT(*) FROM metrics")).scalar() or 0
        alerts_count = conn.execute(text("SELECT COUNT(*) FROM alerts_log")).scalar() or 0
        latest_alert = conn.execute(
            text(
                "SELECT timestamp, platform, alert_type, message FROM alerts_log ORDER BY timestamp DESC LIMIT 1"
            )
        ).mappings().first()

    print("\n=== Run Summary ===")
    print(f"Database file: {db_path.resolve()}")
    print(f"Last DB update: {updated}")
    print(f"Facebook posts stored: {fb_posts_count}")
    print(f"Instagram posts stored: {ig_posts_count}")
    print(f"Daily summary rows: {daily_summary_count}")
    print(f"Metrics rows: {metrics_count}")
    print(f"Alerts logged: {alerts_count}")
    if latest_alert:
        print(
            f"Last alert: [{latest_alert['platform']}] {latest_alert['alert_type']} - {latest_alert['message']} ({latest_alert['timestamp']})"
        )
    else:
        print("Last alert: none")


def main():
    """Main entry point for data fetcher."""
    if not USER_ACCESS_TOKEN:
        raise SystemExit("USER_ACCESS_TOKEN is not set. Add it to the environment or .env file.")

    page_token, page_error = get_page_token()
    if page_error:
        print(f"Warning: Could not obtain page token: {page_error}")
        page_token = None

    export_dashboard_data(page_token, USER_ACCESS_TOKEN)


if __name__ == "__main__":
    main()
