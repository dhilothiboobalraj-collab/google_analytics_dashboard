import os
import json
import requests
from datetime import datetime, timedelta
import pandas as pd

import sys
from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from database import get_session, AIInsight, init_db
import project.utils as utils

def load_env_value(key, default=""):
    value = os.getenv(key)
    if value: return value
    env_path = ROOT_DIR / ".env"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8-sig") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line: continue
                env_key, env_value = line.split("=", 1)
                if env_key.strip().lstrip("\ufeff") == key:
                    return env_value.strip().strip('"').strip("'")
    return default

API_KEY = load_env_value("DIGITALOCEAN_API_KEY")
API_URL = load_env_value("DIGITALOCEAN_URL")
MODEL_NAME = load_env_value("DIGITALOCEAN_MODEL", "anthropic-claude-4.5-sonnet")

def fetch_dashboard_context(insight_type="daily"):
    import api
    
    # 1. Fetch FB posts live via api.py
    fb_res = api.get_facebook_posts(limit=10)
    fb_posts = []
    fb_followers = 0
    if not fb_res.get("error"):
        fb_posts = fb_res.get("data", [])
        fb_followers = fb_res.get("fan_count", 0)
            
    # 2. Fetch IG posts live via api.py
    ig_res = api.get_instagram_posts(limit=10)
    ig_posts = []
    ig_followers = 0
    if not ig_res.get("error"):
        ig_posts = ig_res.get("data", [])
        ig_followers = ig_res.get("followers_count", 0)

    # 3. Fetch YT videos live via api.py
    yt_res = api.get_youtube_videos(limit=10)
    yt_posts = []
    yt_followers = 0
    if not yt_res.get("error"):
        yt_posts = yt_res.get("data", [])
        yt_followers = yt_res.get("subscriber_count", 0)

    # 4. Calculate metrics dynamically in-memory
    fb_reach = sum(p.get("post_reach", 0) for p in fb_posts)
    fb_impressions = sum(p.get("post_impressions", 0) for p in fb_posts)
    fb_engagement = sum(p.get("total_engagement", 0) for p in fb_posts)
    
    ig_reach = sum(p.get("reach", 0) for p in ig_posts)
    ig_impressions = sum(p.get("impressions", 0) for p in ig_posts)
    ig_engagement = sum(p.get("total_interactions", 0) for p in ig_posts)
    
    yt_reach = sum(p.get("view_count", 0) for p in yt_posts)
    yt_impressions = sum(p.get("view_count", 0) for p in yt_posts)
    yt_engagement = sum(p.get("like_count", 0) + p.get("comment_count", 0) for p in yt_posts)
    
    # Calculate recent metrics (last 1 day or 7 days)
    recent_days = 7 if insight_type == "weekly" else 1
    cutoff_date = datetime.now().date() - timedelta(days=recent_days)
    
    recent_fb_reach = 0
    recent_fb_eng = 0
    for p in fb_posts:
        try:
            date_str = p.get("created_time", "")[:10]
            p_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            if p_date >= cutoff_date:
                recent_fb_reach += p.get("post_reach", 0)
                recent_fb_eng += p.get("total_engagement", 0)
        except Exception:
            pass
            
    recent_ig_reach = 0
    recent_ig_eng = 0
    for p in ig_posts:
        try:
            date_str = p.get("created_time", "")[:10]
            p_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            if p_date >= cutoff_date:
                recent_ig_reach += p.get("reach", 0)
                recent_ig_eng += p.get("total_interactions", 0)
        except Exception:
            pass

    recent_yt_reach = 0
    recent_yt_eng = 0
    for p in yt_posts:
        try:
            date_str = p.get("created_time", "")[:10]
            p_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            if p_date >= cutoff_date:
                recent_yt_reach += p.get("view_count", 0)
                recent_yt_eng += p.get("like_count", 0) + p.get("comment_count", 0)
        except Exception:
            pass

    total_posts = len(fb_posts) + len(ig_posts) + len(yt_posts)
    total_reach = fb_reach + ig_reach + yt_reach
    total_engagement = fb_engagement + ig_engagement + yt_engagement
    total_followers = fb_followers + ig_followers + yt_followers
    
    recent_reach = recent_fb_reach + recent_ig_reach + recent_yt_reach
    recent_engagement = recent_fb_eng + recent_ig_eng + recent_yt_eng
    
    context = {
        "insight_type": insight_type,
        "total_posts": total_posts,
        "total_reach": total_reach,
        "total_engagement": total_engagement,
        "total_followers": total_followers,
        "recent_reach": recent_reach,
        "recent_engagement": recent_engagement,
        "facebook_stats": {
            "posts": len(fb_posts),
            "reach": fb_reach,
            "impressions": fb_impressions,
            "engagement": fb_engagement,
            "followers": fb_followers
        },
        "instagram_stats": {
            "posts": len(ig_posts),
            "reach": ig_reach,
            "impressions": ig_impressions,
            "engagement": ig_engagement,
            "followers": ig_followers
        },
        "youtube_stats": {
            "posts": len(yt_posts),
            "reach": yt_reach,
            "impressions": yt_impressions,
            "engagement": yt_engagement,
            "followers": yt_followers
        }
    }
    return context

def generate_insight(insight_type="daily"):
    if not API_KEY or not API_URL:
        print("Missing DO API Key or URL")
        return None
    
    context = fetch_dashboard_context(insight_type)
    
    system_prompt = (
        "You are an expert Social Media Analyst. "
        "Analyze the provided dashboard metrics and generate a concise, highly actionable "
        f"{insight_type.upper()} summary. Provide alerts for unusual drops or spikes, and suggest 2-3 strategies. "
        "Use engaging markdown (bolding, bullet points, emojis). Do not use introductory pleasantries."
    )
    
    user_prompt = f"Dashboard Data Snapshot:\n{json.dumps(context, indent=2)}\n\nPlease provide the {insight_type} insights."
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.4,
        "max_tokens": 1000
    }
    
    try:
        # Standardize URL
        url = API_URL.rstrip('/')
        if not url.endswith("/chat/completions"):
            url = f"{url}/chat/completions"
            
        print(f"Requesting DO AI: {url}")
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        
        save_insight(insight_type, content)
        return content
    except Exception as e:
        print(f"Failed to generate insight: {e}")
        try:
            print(resp.text)
        except: pass
        return None

def save_insight(insight_type, content):
    session = get_session()
    try:
        insight = AIInsight(
            insight_type=insight_type,
            content=content,
            timestamp=datetime.now()
        )
        session.add(insight)
        session.commit()
    except Exception as e:
        session.rollback()
        print(f"Error saving insight: {e}")
    finally:
        session.close()

def get_latest_insight(insight_type):
    session = get_session()
    try:
        insight = session.query(AIInsight).filter(AIInsight.insight_type == insight_type).order_by(AIInsight.timestamp.desc()).first()
        return insight
    finally:
        session.close()
