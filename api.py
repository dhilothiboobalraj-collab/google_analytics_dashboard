"""FastAPI backend for social media dashboard using Live Graph API."""
import asyncio
from datetime import datetime
import pandas as pd
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
import social_media

app = FastAPI(
    title="Social Media Analytics API (Live)",
    description="API for Facebook and Instagram analytics pulling directly from Meta Graph API",
    version="1.0.0"
)

# Serve static assets (CSS, JS, images) for the interactive dashboard
from fastapi.staticfiles import StaticFiles
app.mount("/static", StaticFiles(directory="static"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    """Redirect to the interactive dashboard."""
    return RedirectResponse(url="/dashboard")

@app.get("/dashboard", response_class=HTMLResponse)
def serve_dashboard():
    """Serve the interactive analytics dashboard."""
    with open("dashboard.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "database": "bypassed (live api mode)"
    }

@app.get("/facebook/posts")
async def get_facebook_posts(
    limit: int = Query(10, description="Number of posts to return", le=50)
):
    """Get recent Facebook posts directly from Graph API."""
    def _fetch():
        token, err = social_media.get_page_token()
        if err:
            return {"error": err}
        result = social_media.fetch_facebook_posts(token, max_posts=limit)
        if result.get("error"):
            return {"error": result["error"]}
        posts = []
        for row in result.get("posts", []):
            posts.append({
                "post_id": row.get("post_id"),
                "created_time": row.get("timestamp").isoformat() if hasattr(row.get("timestamp"), "isoformat") else row.get("time"),
                "created_time_display": row.get("date") + " " + row.get("time"),
                "message": row.get("message"),
                "permalink_url": row.get("permalink_url"),
                "reactions": row.get("reactions"),
                "comments": row.get("comments"),
                "shares": row.get("shares"),
                "total_engagement": row.get("total_engagement"),
                "engagement_rate": row.get("engagement_rate"),
                "post_reach": row.get("post_reach"),
                "post_impressions": row.get("post_impressions"),
                "post_clicks": row.get("post_clicks"),
            })
        return {
            "platform": "facebook",
            "count": len(posts),
            "fan_count": result.get("fan_count", 0),
            "data": posts
        }

    return await asyncio.to_thread(_fetch)

@app.get("/facebook/insights")
async def get_facebook_insights(
    days_back: int = Query(28, description="Insights from last N days", le=90)
):
    """Get Facebook weekly insights directly from Graph API."""
    def _fetch():
        token, err = social_media.get_page_token()
        if err:
            return {"error": err}
        rows, fetch_err = social_media.fetch_fb_weekly_insights(token, days_back=days_back)
        if fetch_err:
            return {"error": fetch_err}
        return {
            "platform": "facebook",
            "metric_type": "weekly_insights",
            "count": len(rows),
            "data": rows
        }

    return await asyncio.to_thread(_fetch)

@app.get("/instagram/posts")
async def get_instagram_posts(
    limit: int = Query(10, description="Number of posts to return", le=50)
):
    """Get recent Instagram posts directly from Graph API."""
    def _fetch():
        token = social_media.USER_ACCESS_TOKEN
        result = social_media.fetch_instagram_posts(token, max_posts=limit)
        if result.get("error"):
            return {"error": result["error"]}
        posts = []
        for row in result.get("posts", []):
            posts.append({
                "media_id": row.get("media_id"),
                "created_time": row.get("date") + " " + row.get("time"),
                "caption": row.get("caption"),
                "permalink": row.get("permalink"),
                "like_count": row.get("like_count"),
                "comments_count": row.get("comments_count"),
                "media_type": row.get("media_type"),
                "impressions": row.get("impressions"),
                "reach": row.get("reach"),
                "saved": row.get("saved"),
                "shares": row.get("shares"),
                "video_views": row.get("video_views"),
                "plays": row.get("plays"),
                "total_interactions": row.get("total_interactions"),
            })
        return {
            "platform": "instagram",
            "count": len(posts),
            "followers_count": result.get("account", {}).get("followers_count", 0),
            "data": posts
        }

    return await asyncio.to_thread(_fetch)

@app.get("/instagram/insights")
async def get_instagram_insights(
    days_back: int = Query(28, description="Insights from last N days", le=90)
):
    """Get Instagram weekly insights directly from Graph API."""
    def _fetch():
        token = social_media.USER_ACCESS_TOKEN
        rows, fetch_err = social_media.fetch_ig_weekly_insights(token, days_back=days_back)
        if fetch_err:
            return {"error": fetch_err}
        return {
            "platform": "instagram",
            "metric_type": "weekly_insights",
            "count": len(rows),
            "data": rows
        }

    return await asyncio.to_thread(_fetch)


@app.get("/youtube/videos")
async def get_youtube_videos(
    limit: int = Query(10, description="Number of videos to return", le=50)
):
    """Get recent YouTube videos directly from API."""
    def _fetch():
        token = social_media.YOUTUBE_API_KEY
        channel = social_media.YOUTUBE_CHANNEL_ID
        result = social_media.fetch_youtube_videos(token, channel, max_videos=limit)
        if result.get("error"):
            return {"error": result["error"]}
        videos = []
        for row in result.get("videos", []):
            videos.append({
                "video_id": row.get("video_id"),
                "created_time": row.get("date") + " " + row.get("time"),
                "title": row.get("title"),
                "permalink": row.get("permalink"),
                "view_count": row.get("view_count"),
                "like_count": row.get("like_count"),
                "comment_count": row.get("comment_count"),
                "engagement_rate": row.get("engagement_rate"),
            })
        return {
            "platform": "youtube",
            "count": len(videos),
            "subscriber_count": result.get("subscriber_count", 0),
            "data": videos
        }

    return await asyncio.to_thread(_fetch)

@app.get("/trend")
async def get_trend(
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    platform: str = Query("all", description="Platform: facebook, instagram, youtube, or all")
):
    """Get engagement trend for a date range dynamically aggregating live post data."""
    try:
        sd = datetime.strptime(start_date, "%Y-%m-%d").date()
        ed = datetime.strptime(end_date, "%Y-%m-%d").date()
    except ValueError:
        return {"error": "Invalid date format. Use YYYY-MM-DD"}

    def _fetch_fb():
        if platform not in ["facebook", "all"]:
            return []
        token, err = social_media.get_page_token()
        if err:
            return []
        fb_res = social_media.fetch_facebook_posts(token, max_posts=50)
        if fb_res.get("error"):
            return []
        result = []
        for p in fb_res.get("posts", []):
            p_date = datetime.strptime(p["date"], "%Y-%m-%d").date()
            if sd <= p_date <= ed:
                result.append({
                    "date": p["date"],
                    "source": "facebook_posts",
                    "total_engagement": p.get("total_engagement", 0),
                    "engagement_rate": p.get("engagement_rate", 0)
                })
        return result

    def _fetch_ig():
        if platform not in ["instagram", "all"]:
            return []
        ig_token = social_media.USER_ACCESS_TOKEN
        ig_res = social_media.fetch_instagram_posts(ig_token, max_posts=50)
        if ig_res.get("error"):
            return []
        result = []
        for p in ig_res.get("posts", []):
            p_date = datetime.strptime(p["date"], "%Y-%m-%d").date()
            if sd <= p_date <= ed:
                result.append({
                    "date": p["date"],
                    "source": "instagram_posts",
                    "total_engagement": p.get("total_interactions", 0),
                    "engagement_rate": p.get("engagement_rate", 0)
                })
        return result

    def _fetch_yt():
        if platform not in ["youtube", "all"]:
            return []
        yt_token = social_media.YOUTUBE_API_KEY
        yt_channel = social_media.YOUTUBE_CHANNEL_ID
        yt_res = social_media.fetch_youtube_videos(yt_token, yt_channel, max_videos=50)
        if yt_res.get("error"):
            return []
        result = []
        for p in yt_res.get("videos", []):
            p_date = datetime.strptime(p["date"], "%Y-%m-%d").date()
            if sd <= p_date <= ed:
                result.append({
                    "date": p["date"],
                    "source": "youtube_videos",
                    "total_engagement": p.get("like_count", 0) + p.get("comment_count", 0),
                    "engagement_rate": p.get("engagement_rate", 0)
                })
        return result

    # Run all three fetches concurrently in thread pool
    fb_data, ig_data, yt_data = await asyncio.gather(
        asyncio.to_thread(_fetch_fb),
        asyncio.to_thread(_fetch_ig),
        asyncio.to_thread(_fetch_yt),
    )

    all_data = fb_data + ig_data + yt_data

    if not all_data:
        return {"message": "No data found for the given date range", "data": []}

    df = pd.DataFrame(all_data)
    
    agg_df = df.groupby(["date", "source"]).agg(
        total_engagement=("total_engagement", "sum"),
        post_count=("total_engagement", "count"),
        avg_engagement_rate=("engagement_rate", "mean")
    ).reset_index()
    
    agg_df = agg_df.sort_values("date", ascending=False)
    
    agg_df["total_engagement"] = agg_df["total_engagement"].astype(int)
    agg_df["post_count"] = agg_df["post_count"].astype(int)
    agg_df["avg_engagement_rate"] = agg_df["avg_engagement_rate"].astype(float).round(3)

    return {
        "start_date": start_date,
        "end_date": end_date,
        "platform": platform,
        "data": agg_df.to_dict(orient="records"),
        "total_posts": int(agg_df["post_count"].sum()),
        "total_engagement": int(agg_df["total_engagement"].sum())
    }

# ---------------------------------------------------------------------
# Helper functions for weekly and monthly aggregations
def aggregate_weekly(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate DataFrame by calendar week.
    Returns a DataFrame with columns: week (e.g., 'W01'), source,
    total_engagement (sum), post_count, avg_engagement_rate.
    """
    df['week'] = df['date'].apply(lambda d: datetime.strptime(d, "%Y-%m-%d").isocalendar()[1])
    agg = df.groupby(['week', 'source']).agg(
        total_engagement=('total_engagement', 'sum'),
        post_count=('total_engagement', 'count'),
        avg_engagement_rate=('engagement_rate', 'mean')
    ).reset_index()
    agg['week'] = agg['week'].apply(lambda w: f"W{w:02d}")
    return agg

def aggregate_monthly(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate DataFrame by month.
    Returns a DataFrame with columns: month (e.g., '2024-07'), source,
    total_engagement, post_count, avg_engagement_rate.
    """
    df['month'] = df['date'].apply(lambda d: datetime.strptime(d, "%Y-%m-%d").strftime('%Y-%m'))
    agg = df.groupby(['month', 'source']).agg(
        total_engagement=('total_engagement', 'sum'),
        post_count=('total_engagement', 'count'),
        avg_engagement_rate=('engagement_rate', 'mean')
    ).reset_index()
    return agg

# ---------------------------------------------------------------------
# New API endpoints for weekly and monthly comparative analysis
@app.get("/analysis/weekly")
async def weekly_analysis(start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
                    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
                    platform: str = Query("all", description="Platform filter (facebook, instagram, youtube, all)")):
    """Return weekly aggregated metrics for the given date range and platform."""
    trend = await get_trend(start_date=start_date, end_date=end_date, platform=platform)
    if trend.get("error"):
        return trend
    df = pd.DataFrame(trend["data"])
    if df.empty:
        return {"period": "weekly", "start_date": start_date, "end_date": end_date, "platform": platform, "data": []}
    weekly_df = aggregate_weekly(df)
    return {
        "period": "weekly",
        "start_date": start_date,
        "end_date": end_date,
        "platform": platform,
        "data": weekly_df.to_dict(orient="records")
    }

@app.get("/analysis/monthly")
async def monthly_analysis(start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
                     end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
                     platform: str = Query("all", description="Platform filter (facebook, instagram, youtube, all)")):
    """Return monthly aggregated metrics for the given date range and platform."""
    trend = await get_trend(start_date=start_date, end_date=end_date, platform=platform)
    if trend.get("error"):
        return trend
    df = pd.DataFrame(trend["data"])
    if df.empty:
        return {"period": "monthly", "start_date": start_date, "end_date": end_date, "platform": platform, "data": []}
    monthly_df = aggregate_monthly(df)
    return {
        "period": "monthly",
        "start_date": start_date,
        "end_date": end_date,
        "platform": platform,
        "data": monthly_df.to_dict(orient="records")
    }

# ---------------------------------------------------------------------
# Best Posting Time endpoint
@app.get("/analysis/best-time")
async def best_posting_time():
    """Analyse best day-of-week and hour-of-day to post across platforms."""
    def _analyze():
        from collections import defaultdict
        import statistics as _stat

        results = {}

        # ── Facebook ──────────────────────────────────────────────────
        token, err = social_media.get_page_token()
        if not err:
            fb_res = social_media.fetch_facebook_posts(token, max_posts=50)
            fb_posts = fb_res.get("posts", [])
            day_eng = defaultdict(list)
            hour_eng = defaultdict(list)
            dow_hour = defaultdict(lambda: defaultdict(list))
            for p in fb_posts:
                try:
                    ts = p.get("timestamp")
                    if ts:
                        if hasattr(ts, "weekday"):
                            dt = ts
                        else:
                            from datetime import datetime as _dt
                            dt = _dt.fromisoformat(str(ts).replace("Z","+00:00"))
                        day = dt.strftime("%A")
                        hour = dt.hour
                        eng = p.get("total_engagement", 0)
                        day_eng[day].append(eng)
                        hour_eng[hour].append(eng)
                        dow_hour[day][hour].append(eng)
                except Exception:
                    pass
            days_order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
            results["facebook"] = {
                "by_day": {d: round(_stat.mean(v),1) for d,v in day_eng.items()},
                "by_hour": {str(h): round(_stat.mean(v),1) for h,v in hour_eng.items()},
                "heatmap": {
                    "days": days_order,
                    "hours": list(range(24)),
                    "values": [[round(_stat.mean(dow_hour[d].get(h,[])) if dow_hour[d].get(h) else 0, 1) for h in range(24)] for d in days_order]
                }
            }

        # ── Instagram ─────────────────────────────────────────────────
        ig_token = social_media.USER_ACCESS_TOKEN
        ig_res = social_media.fetch_instagram_posts(ig_token, max_posts=50)
        ig_posts = ig_res.get("posts", [])
        day_eng = defaultdict(list)
        hour_eng = defaultdict(list)
        dow_hour = defaultdict(lambda: defaultdict(list))
        for p in ig_posts:
            try:
                ts = p.get("timestamp")
                if ts:
                    if hasattr(ts, "weekday"):
                        dt = ts
                    else:
                        from datetime import datetime as _dt
                        dt = _dt.fromisoformat(str(ts).replace("Z","+00:00"))
                    day = dt.strftime("%A")
                    hour = dt.hour
                    eng = p.get("total_interactions", 0)
                    day_eng[day].append(eng)
                    hour_eng[hour].append(eng)
                    dow_hour[day][hour].append(eng)
            except Exception:
                pass
        results["instagram"] = {
            "by_day": {d: round(_stat.mean(v),1) for d,v in day_eng.items()},
            "by_hour": {str(h): round(_stat.mean(v),1) for h,v in hour_eng.items()},
            "heatmap": {
                "days": days_order,
                "hours": list(range(24)),
                "values": [[round(_stat.mean(dow_hour[d].get(h,[])) if dow_hour[d].get(h) else 0, 1) for h in range(24)] for d in days_order]
            }
        }

        # ── YouTube ───────────────────────────────────────────────────
        yt_res = social_media.fetch_youtube_videos(social_media.YOUTUBE_API_KEY, social_media.YOUTUBE_CHANNEL_ID, max_videos=50)
        yt_videos = yt_res.get("videos", [])
        day_eng = defaultdict(list)
        hour_eng = defaultdict(list)
        dow_hour = defaultdict(lambda: defaultdict(list))
        for v in yt_videos:
            try:
                ts = v.get("timestamp")
                if ts:
                    if hasattr(ts, "weekday"):
                        dt = ts
                    else:
                        from datetime import datetime as _dt
                        dt = _dt.fromisoformat(str(ts).replace("Z","+00:00"))
                    day = dt.strftime("%A")
                    hour = dt.hour
                    eng = v.get("view_count", 0)
                    day_eng[day].append(eng)
                    hour_eng[hour].append(eng)
                    dow_hour[day][hour].append(eng)
            except Exception:
                pass
        results["youtube"] = {
            "by_day": {d: round(_stat.mean(v),1) for d,v in day_eng.items()},
            "by_hour": {str(h): round(_stat.mean(v),1) for h,v in hour_eng.items()},
            "heatmap": {
                "days": days_order,
                "hours": list(range(24)),
                "values": [[round(_stat.mean(dow_hour[d].get(h,[])) if dow_hour[d].get(h) else 0, 1) for h in range(24)] for d in days_order]
            }
        }

        return {"platforms": results, "generated_at": datetime.utcnow().isoformat()+"Z"}

    return await asyncio.to_thread(_analyze)


# ---------------------------------------------------------------------
# Platform Comparison endpoint
@app.get("/analysis/platform-comparison")
async def platform_comparison():
    """Compare all platforms side-by-side on key metrics."""
    def _compare():
        import statistics as _stat
        metrics = {}

        # Facebook
        token, err = social_media.get_page_token()
        fb_fans = 0
        if not err:
            fb_res = social_media.fetch_facebook_posts(token, max_posts=50)
            fb_posts = fb_res.get("posts", [])
            fb_fans = fb_res.get("fan_count", 0)
            engs = [p.get("total_engagement", 0) for p in fb_posts]
            reaches = [p.get("post_reach", 0) for p in fb_posts]
            imps = [p.get("post_impressions", 0) for p in fb_posts]
            metrics["facebook"] = {
                "followers": fb_fans,
                "posts": len(fb_posts),
                "total_engagement": sum(engs),
                "avg_engagement": round(_stat.mean(engs),1) if engs else 0,
                "avg_reach": round(_stat.mean(reaches),1) if reaches else 0,
                "avg_impressions": round(_stat.mean(imps),1) if imps else 0,
                "engagement_rate": round(sum(engs)/max(fb_fans,1)*100, 4) if fb_fans else 0,
                "top_engagement": max(engs) if engs else 0,
            }

        # Instagram
        ig_token = social_media.USER_ACCESS_TOKEN
        ig_res = social_media.fetch_instagram_posts(ig_token, max_posts=50)
        ig_posts = ig_res.get("posts", [])
        ig_followers = ig_res.get("account", {}).get("followers_count", 0)
        engs = [p.get("total_interactions", 0) for p in ig_posts]
        reaches = [p.get("reach", 0) for p in ig_posts]
        imps = [p.get("impressions", 0) for p in ig_posts]
        metrics["instagram"] = {
            "followers": ig_followers,
            "posts": len(ig_posts),
            "total_engagement": sum(engs),
            "avg_engagement": round(_stat.mean(engs),1) if engs else 0,
            "avg_reach": round(_stat.mean(reaches),1) if reaches else 0,
            "avg_impressions": round(_stat.mean(imps),1) if imps else 0,
            "engagement_rate": round(sum(engs)/max(ig_followers,1)*100, 4) if ig_followers else 0,
            "top_engagement": max(engs) if engs else 0,
        }

        # YouTube
        yt_res = social_media.fetch_youtube_videos(social_media.YOUTUBE_API_KEY, social_media.YOUTUBE_CHANNEL_ID, max_videos=50)
        yt_videos = yt_res.get("videos", [])
        yt_subs = yt_res.get("subscriber_count", 0)
        views = [v.get("view_count", 0) for v in yt_videos]
        engs = [v.get("like_count", 0)+v.get("comment_count", 0) for v in yt_videos]
        metrics["youtube"] = {
            "followers": yt_subs,
            "posts": len(yt_videos),
            "total_engagement": sum(engs),
            "avg_engagement": round(_stat.mean(engs),1) if engs else 0,
            "avg_reach": round(_stat.mean(views),1) if views else 0,
            "avg_impressions": round(_stat.mean(views),1) if views else 0,
            "engagement_rate": round(sum(engs)/max(yt_subs,1)*100, 4) if yt_subs else 0,
            "top_engagement": max(engs) if engs else 0,
        }

        return {"metrics": metrics, "generated_at": datetime.utcnow().isoformat()+"Z"}

    return await asyncio.to_thread(_compare)


# ---------------------------------------------------------------------
# Reach Analysis endpoint
@app.get("/analysis/reach")
async def reach_analysis():
    """Analyse reach and impressions over time across platforms."""
    def _reach():
        from datetime import datetime as _dt
        timeline = []

        token, err = social_media.get_page_token()
        if not err:
            fb_res = social_media.fetch_facebook_posts(token, max_posts=50)
            for p in fb_res.get("posts", []):
                timeline.append({
                    "platform": "facebook",
                    "date": p.get("date", ""),
                    "reach": p.get("post_reach", 0),
                    "impressions": p.get("post_impressions", 0),
                    "engagement": p.get("total_engagement", 0),
                    "clicks": p.get("post_clicks", 0),
                })

        ig_token = social_media.USER_ACCESS_TOKEN
        ig_res = social_media.fetch_instagram_posts(ig_token, max_posts=50)
        for p in ig_res.get("posts", []):
            timeline.append({
                "platform": "instagram",
                "date": p.get("date", ""),
                "reach": p.get("reach", 0),
                "impressions": p.get("impressions", 0),
                "engagement": p.get("total_interactions", 0),
                "clicks": p.get("saved", 0),
            })

        yt_res = social_media.fetch_youtube_videos(social_media.YOUTUBE_API_KEY, social_media.YOUTUBE_CHANNEL_ID, max_videos=50)
        for v in yt_res.get("videos", []):
            timeline.append({
                "platform": "youtube",
                "date": v.get("date", ""),
                "reach": v.get("view_count", 0),
                "impressions": v.get("view_count", 0),
                "engagement": v.get("like_count", 0)+v.get("comment_count", 0),
                "clicks": v.get("like_count", 0),
            })

        timeline.sort(key=lambda x: x.get("date",""))

        # Aggregate summaries per platform
        import statistics as _stat
        from collections import defaultdict
        plat_agg = defaultdict(lambda: {"reach":[], "impressions":[], "engagement":[]})
        for item in timeline:
            plat_agg[item["platform"]]["reach"].append(item["reach"])
            plat_agg[item["platform"]]["impressions"].append(item["impressions"])
            plat_agg[item["platform"]]["engagement"].append(item["engagement"])

        summaries = {}
        for plat, data in plat_agg.items():
            summaries[plat] = {
                "total_reach": sum(data["reach"]),
                "total_impressions": sum(data["impressions"]),
                "total_engagement": sum(data["engagement"]),
                "avg_reach": round(_stat.mean(data["reach"]),1) if data["reach"] else 0,
                "reach_to_impression_ratio": round(sum(data["reach"])/max(sum(data["impressions"]),1)*100,2),
                "engagement_to_reach_ratio": round(sum(data["engagement"])/max(sum(data["reach"]),1)*100,4),
            }

        return {"timeline": timeline, "summaries": summaries, "generated_at": datetime.utcnow().isoformat()+"Z"}

    return await asyncio.to_thread(_reach)


# ---------------------------------------------------------------------
# Recent Post Analysis endpoint
@app.get("/analysis/recent-posts")
async def recent_posts_analysis(
    limit: int = Query(15, description="Posts per platform to analyse", le=30)
):
    """Get most recent posts from all platforms with full analytics."""
    def _recent():
        posts = []

        token, err = social_media.get_page_token()
        if not err:
            fb_res = social_media.fetch_facebook_posts(token, max_posts=limit)
            for p in fb_res.get("posts", []):
                posts.append({
                    "platform": "facebook",
                    "id": p.get("post_id"),
                    "date": p.get("date",""),
                    "time": p.get("time",""),
                    "content": (p.get("message") or p.get("story") or "")[:200],
                    "engagement": p.get("total_engagement",0),
                    "reach": p.get("post_reach",0),
                    "impressions": p.get("post_impressions",0),
                    "reactions": p.get("reactions",0),
                    "comments": p.get("comments",0),
                    "shares": p.get("shares",0),
                    "engagement_rate": p.get("engagement_rate",0),
                    "url": p.get("permalink_url",""),
                    "media_type": "post",
                })

        ig_token = social_media.USER_ACCESS_TOKEN
        ig_res = social_media.fetch_instagram_posts(ig_token, max_posts=limit)
        for p in ig_res.get("posts", []):
            posts.append({
                "platform": "instagram",
                "id": p.get("media_id"),
                "date": p.get("date",""),
                "time": p.get("time",""),
                "content": (p.get("caption") or "")[:200],
                "engagement": p.get("total_interactions",0),
                "reach": p.get("reach",0),
                "impressions": p.get("impressions",0),
                "reactions": p.get("like_count",0),
                "comments": p.get("comments_count",0),
                "shares": p.get("shares",0) or p.get("saved",0),
                "engagement_rate": p.get("engagement_rate",0),
                "url": p.get("permalink",""),
                "media_type": p.get("media_type","IMAGE"),
            })

        yt_res = social_media.fetch_youtube_videos(social_media.YOUTUBE_API_KEY, social_media.YOUTUBE_CHANNEL_ID, max_videos=limit)
        for v in yt_res.get("videos", []):
            posts.append({
                "platform": "youtube",
                "id": v.get("video_id"),
                "date": v.get("date",""),
                "time": v.get("time",""),
                "content": (v.get("title") or "")[:200],
                "engagement": (v.get("like_count",0)+v.get("comment_count",0)),
                "reach": v.get("view_count",0),
                "impressions": v.get("view_count",0),
                "reactions": v.get("like_count",0),
                "comments": v.get("comment_count",0),
                "shares": 0,
                "engagement_rate": v.get("engagement_rate",0),
                "url": v.get("permalink",""),
                "media_type": "VIDEO",
            })

        posts.sort(key=lambda x: x.get("date","")+" "+x.get("time",""), reverse=True)
        return {"posts": posts, "count": len(posts), "generated_at": datetime.utcnow().isoformat()+"Z"}

    return await asyncio.to_thread(_recent)


# ---------------------------------------------------------------------
# AI Insights endpoint
@app.get("/ai-insights")
async def get_ai_insights():
    """Generate data-driven AI insights from all social media platforms."""
    def _analyze():
        import statistics as _stat
        from collections import defaultdict

        fb_posts, fb_fans = [], 0
        token, err = social_media.get_page_token()
        if not err:
            fb_res = social_media.fetch_facebook_posts(token, max_posts=50)
            fb_posts = fb_res.get("posts", [])
            fb_fans  = fb_res.get("fan_count", 0)

        ig_token = social_media.USER_ACCESS_TOKEN
        ig_res   = social_media.fetch_instagram_posts(ig_token, max_posts=50)
        ig_posts = ig_res.get("posts", [])
        ig_followers = ig_res.get("account", {}).get("followers_count", 0)

        yt_res    = social_media.fetch_youtube_videos(social_media.YOUTUBE_API_KEY, social_media.YOUTUBE_CHANNEL_ID, max_videos=50)
        yt_videos = yt_res.get("videos", [])
        yt_subs   = yt_res.get("subscriber_count", 0)

        insights = []

        fb_eng   = [p.get("total_engagement", 0) for p in fb_posts]
        ig_eng   = [p.get("total_interactions", 0) for p in ig_posts]
        yt_views = [v.get("view_count", 0) for v in yt_videos]

        fb_avg = _stat.mean(fb_eng)   if fb_eng   else 0
        ig_avg = _stat.mean(ig_eng)   if ig_eng   else 0
        yt_avg = _stat.mean(yt_views) if yt_views else 0

        # ── 1. Best platform engagement rate ──────────────────────────
        rates = {}
        if fb_fans   > 0: rates["Facebook"]  = round(fb_avg / fb_fans * 100, 4)
        if ig_followers > 0: rates["Instagram"] = round(ig_avg / ig_followers * 100, 4)
        if yt_subs   > 0: rates["YouTube"]   = round(yt_avg / max(yt_subs, 1) * 100, 4)
        if rates:
            best  = max(rates, key=rates.get)
            worst = min(rates, key=rates.get)
            insights.append({
                "id": "engagement_champion",
                "icon": "🏆", "type": "positive", "platform": best.lower(),
                "title": f"{best} Is Your Top Platform",
                "description": f"{best} leads with a {rates[best]:.4f}% engagement rate — "
                               f"{round(rates[best]/max(rates[worst],0.0001),1)}× higher than {worst}. Double down here.",
                "metric": f"{rates[best]:.4f}%", "metric_label": "Engagement Rate",
                "chart_data": {"labels": list(rates.keys()), "values": list(rates.values())},
                "chart_type": "bar",
            })

        # ── 2. Best day to post (Facebook) ───────────────────────────
        if fb_posts:
            day_map = defaultdict(list)
            for p in fb_posts:
                try:
                    day = datetime.strptime(p["date"], "%Y-%m-%d").strftime("%A")
                    day_map[day].append(p.get("total_engagement", 0))
                except Exception:
                    pass
            if day_map:
                day_avgs = {d: round(_stat.mean(v), 1) for d, v in day_map.items()}
                best_day = max(day_avgs, key=day_avgs.get)
                days_order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
                ordered = {d: day_avgs.get(d, 0) for d in days_order}
                insights.append({
                    "id": "best_day", "icon": "📅", "type": "info", "platform": "facebook",
                    "title": f"Post on {best_day} for Best Results",
                    "description": f"Facebook posts on {best_day}s average {int(day_avgs[best_day]):,} engagements — your strongest day.",
                    "metric": best_day, "metric_label": "Best Day",
                    "chart_data": {"labels": list(ordered.keys()), "values": list(ordered.values())},
                    "chart_type": "bar",
                })

        # ── 3. Instagram media type breakdown ─────────────────────────
        if ig_posts:
            type_map = defaultdict(list)
            for p in ig_posts:
                type_map[p.get("media_type","UNKNOWN")].append(p.get("total_interactions", 0))
            type_avgs = {t: round(_stat.mean(v), 1) for t, v in type_map.items()}
            best_type = max(type_avgs, key=type_avgs.get)
            insights.append({
                "id": "ig_media_type", "icon": "📸", "type": "positive", "platform": "instagram",
                "title": f"{best_type.title()} Content Wins on Instagram",
                "description": f"{best_type.title()} posts average {int(type_avgs[best_type]):,} interactions — your best format. Create more of it.",
                "metric": best_type.title(), "metric_label": "Best Format",
                "chart_data": {"labels": list(type_avgs.keys()), "values": list(type_avgs.values())},
                "chart_type": "donut",
            })

        # ── 4. Facebook engagement consistency ────────────────────────
        if fb_eng and len(fb_eng) > 1:
            cv = _stat.stdev(fb_eng) / max(fb_avg, 1) * 100
            label = "Consistent" if cv < 60 else "Variable"
            insights.append({
                "id": "fb_consistency", "icon": "📊",
                "type": "positive" if cv < 60 else "warning", "platform": "facebook",
                "title": f"Facebook Engagement Is {label}",
                "description": f"Coefficient of variation: {round(cv,1)}%. "
                               + ("Great consistency — your audience reliably engages." if cv < 60 else
                                  "High variability — some posts greatly outperform others. Analyse your top posts."),
                "metric": f"{round(cv,1)}%", "metric_label": "Variability",
                "chart_data": {"labels": [f"#{i+1}" for i in range(min(20,len(fb_eng)))], "values": fb_eng[:20]},
                "chart_type": "line",
            })

        # ── 5. YouTube like-to-view rate ──────────────────────────────
        if yt_videos:
            like_rates = [v.get("like_count",0)/max(v.get("view_count",1),1)*100 for v in yt_videos]
            avg_lr = round(_stat.mean(like_rates), 3)
            insights.append({
                "id": "yt_like_rate", "icon": "▶️",
                "type": "positive" if avg_lr > 2 else "info", "platform": "youtube",
                "title": f"YouTube Like Rate: {avg_lr:.3f}%",
                "description": f"Viewers like {avg_lr:.3f}% of views on average. "
                               + ("Strong positive audience reception!" if avg_lr > 2 else
                                  "Below 2% — experiment with stronger CTAs and more engaging thumbnails."),
                "metric": f"{avg_lr:.3f}%", "metric_label": "Like-to-View Rate",
                "chart_data": {"labels": [v.get("title","")[:18]+"…" for v in yt_videos[:10]],
                               "values": [round(v.get("like_count",0)/max(v.get("view_count",1),1)*100,3) for v in yt_videos[:10]]},
                "chart_type": "bar",
            })

        # ── 6. Total cross-platform audience ──────────────────────────
        total_audience = fb_fans + ig_followers + yt_subs
        total_eng_all  = sum(fb_eng) + sum(ig_eng) + sum(v.get("like_count",0)+v.get("comment_count",0) for v in yt_videos)
        overall_rate   = round(total_eng_all / max(total_audience, 1) * 100, 4) if total_audience else 0
        insights.append({
            "id": "cross_platform_audience", "icon": "🌐",
            "type": "positive" if total_audience > 500 else "info", "platform": "all",
            "title": "Total Cross-Platform Reach",
            "description": f"You reach {total_audience:,} followers/subscribers across all platforms with a {overall_rate:.4f}% combined engagement rate.",
            "metric": f"{total_audience:,}", "metric_label": "Total Audience",
            "chart_data": {"labels":["Facebook","Instagram","YouTube"], "values":[fb_fans,ig_followers,yt_subs]},
            "chart_type": "donut",
        })

        # ── 7. Star post (top Facebook) ───────────────────────────────
        if fb_posts:
            top = max(fb_posts, key=lambda p: p.get("total_engagement",0))
            insights.append({
                "id": "star_post", "icon": "⭐",
                "type": "positive", "platform": "facebook",
                "title": "Star Facebook Post",
                "description": f"Posted {top.get('date','')}: {top.get('total_engagement',0):,} engagements · {top.get('reactions',0):,} reactions · {top.get('comments',0):,} comments. Use as a content template.",
                "metric": f"{top.get('total_engagement',0):,}", "metric_label": "Peak Engagements",
                "post_url": top.get("permalink_url",""),
                "chart_data": None, "chart_type": None,
            })

        # ── 8. Publishing velocity ────────────────────────────────────
        all_count = len(fb_posts) + len(ig_posts) + len(yt_videos)
        insights.append({
            "id": "publishing_velocity", "icon": "🚀",
            "type": "positive" if all_count > 100 else "info", "platform": "all",
            "title": f"Publishing Velocity: {all_count} Pieces",
            "description": f"{len(fb_posts)} FB posts · {len(ig_posts)} IG posts · {len(yt_videos)} YT videos. "
                           + ("Excellent output!" if all_count > 100 else "Increasing frequency boosts algorithm reach."),
            "metric": str(all_count), "metric_label": "Total Content",
            "chart_data": {"labels":["Facebook","Instagram","YouTube"], "values":[len(fb_posts),len(ig_posts),len(yt_videos)]},
            "chart_type": "bar",
        })

        # ── Health score ──────────────────────────────────────────────
        pos   = sum(1 for i in insights if i["type"] == "positive")
        score = min(100, round(pos / max(len(insights),1) * 60 + min(total_audience/200,25) + min(all_count/5,15)))

        return {
            "insights": insights,
            "summary": {
                "health_score": score,
                "total_audience": total_audience,
                "total_content": all_count,
                "overall_engagement_rate": overall_rate,
                "active_platforms": len([x for x in [fb_posts,ig_posts,yt_videos] if x]),
            },
            "generated_at": datetime.utcnow().isoformat() + "Z",
        }

    return await asyncio.to_thread(_analyze)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)

