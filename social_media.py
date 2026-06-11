import json
import os
import time
from datetime import datetime, timedelta

import pandas as pd
import requests

from data_fetcher import main as run_pipeline


BASE = "https://graph.facebook.com/v25.0"
FB_PAGE_ID = load_env_value("FB_PAGE_ID", "")
IG_USER_ID = load_env_value("IG_USER_ID", "")
MAX_POSTS = 50
WEEKLY_DAYS = 28


def load_env_value(key, default=""):
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


USER_ACCESS_TOKEN = load_env_value("USER_ACCESS_TOKEN")


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
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days_back)

    print(f"Fetching IG weekly insights: {start_date} to {end_date}")

    url = f"{BASE}/{IG_USER_ID}/insights"
    all_rows = []

    params1 = {
        "metric": "reach",
        "period": "day",
        "since": start_date.strftime("%Y-%m-%d"),
        "until": end_date.strftime("%Y-%m-%d"),
        "access_token": user_token,
    }
    resp1 = requests.get(url, params=params1, timeout=30).json()
    print(f"IG Weekly Raw Response (reach): {json.dumps(resp1, indent=2, ensure_ascii=False)}")
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
                    reach_data[item.get("name")] = values[0].get("value", 0)

            reactions = stats.get("reactions", {}).get("summary", {}).get("total_count", 0) if isinstance(stats, dict) else 0
            comments = stats.get("comments", {}).get("summary", {}).get("total_count", 0) if isinstance(stats, dict) else 0
            shares = stats.get("shares", {}).get("count", 0) if isinstance(stats, dict) else 0
            total_engagement = reactions + comments + shares

            all_posts.append(
                {
                    "post_id": pid,
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

            all_posts.append(
                {
                    "media_id": media.get("id"),
                    "date": media.get("timestamp", "")[:10],
                    "time": media.get("timestamp", "")[11:19] if media.get("timestamp") else "",
                    "timestamp": datetime.fromisoformat(media["timestamp"].replace("Z", "+00:00")) if media.get("timestamp") else None,
                    "caption": media.get("caption", "").strip()[:300],
                    "like_count": media.get("like_count", 0) or 0,
                    "comments_count": media.get("comments_count", 0) or 0,
                    "media_type": media.get("media_type"),
                    "media_product_type": media.get("media_product_type"),
                    "permalink": media.get("permalink"),
                    "impressions": insights.get("impressions", 0),
                    "reach": insights.get("reach", 0),
                    "saved": insights.get("saved", 0),
                    "shares": insights.get("shares", 0),
                    "video_views": insights.get("video_views", 0),
                    "plays": insights.get("plays", 0),
                    "total_interactions": insights.get("total_interactions", 0),
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



YOUTUBE_API_KEY = load_env_value("YOUTUBE_API_KEY")
YOUTUBE_CHANNEL_ID = load_env_value("YOUTUBE_CHANNEL_ID")

def fetch_youtube_videos(api_key, channel_id, max_videos=MAX_POSTS):
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
    if not records:
        print(f"No records to save for {filename}")
        return

    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, filename)
    pd.DataFrame.from_records(records).to_csv(filepath, index=False, encoding="utf-8-sig")
    print(f"Saved {len(records)} records to {filepath}")


def build_combined_dataframe(fb_insights, fb_posts, ig_insights):
    frames = []

    if fb_insights:
        df = pd.DataFrame.from_records(fb_insights)
        df["source"] = "fb_weekly_insights"
        frames.append(df)

    if fb_posts:
        df = pd.DataFrame.from_records(fb_posts)
        df["source"] = "fb_posts"
        frames.append(df)

    if ig_insights:
        df = pd.DataFrame.from_records(ig_insights)
        df["source"] = "ig_weekly_insights"
        frames.append(df)

    if not frames:
        return None

    return pd.concat(frames, ignore_index=True, sort=False)


def save_combined_csv(fb_insights, fb_posts, ig_insights, filename="dashboard_combined.csv", output_dir="output"):
    combined_df = build_combined_dataframe(fb_insights, fb_posts, ig_insights)
    if combined_df is None or combined_df.empty:
        print("No combined records to save")
        return

    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, filename)
    combined_df.to_csv(filepath, index=False, encoding="utf-8-sig")
    print(f"Saved combined dashboard file to {filepath}")


def export_dashboard_csv(page_token, user_token):
    fb_insights = []
    fb_posts = []
    ig_insights = []
    ig_posts = []

    if page_token:
        fb_insights, fb_insights_error = fetch_fb_weekly_insights(page_token)
        if fb_insights_error:
            print(f"Facebook insights error: {fb_insights_error}")
        else:
            save_to_csv(fb_insights, "fb_weekly_insights.csv")

        fb_response = fetch_facebook_posts(page_token)
        if fb_response.get("error"):
            print(f"Facebook posts error: {fb_response['error']}")
        else:
            fb_posts = fb_response.get("posts", [])
            save_to_csv(fb_posts, "fb_posts.csv")
    else:
        print("Skipping Facebook exports because page token could not be obtained.")

    ig_insights, ig_insights_error = fetch_ig_weekly_insights(user_token)
    if ig_insights_error:
        print(f"Instagram insights error: {ig_insights_error}")
    else:
        save_to_csv(ig_insights, "ig_weekly_insights.csv")

    ig_response = fetch_instagram_posts(user_token)
    if ig_response.get("error"):
        print(f"Instagram posts error: {ig_response['error']}")
    else:
        ig_posts = ig_response.get("posts", [])
        save_to_csv(ig_posts, "ig_posts.csv")

    save_combined_csv(fb_insights, fb_posts, ig_insights)

    yt_response = fetch_youtube_videos(YOUTUBE_API_KEY, YOUTUBE_CHANNEL_ID)
    if yt_response.get("error"):
        print(f"YouTube posts error: {yt_response['error']}")
    else:
        yt_videos = yt_response.get("videos", [])
        save_to_csv(yt_videos, "yt_videos.csv")



def main():
    if not USER_ACCESS_TOKEN:
        raise SystemExit("USER_ACCESS_TOKEN is not set. Add it to the environment or .env file.")

    run_pipeline()


if __name__ == "__main__":
    main()
