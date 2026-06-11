"""Database configuration and initialization for Power BI integration."""
from sqlalchemy import create_engine, Column, String, Float, DateTime, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# SQLite database for development
engine = create_engine(
    "sqlite:///social_media.db",
    connect_args={"check_same_thread": False}
)

Base = declarative_base()
Session = sessionmaker(bind=engine)


class MetricData(Base):
    """Unified metrics table for Power BI (normalized schema)."""
    __tablename__ = "metrics"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String(10), nullable=False)  # YYYY-MM-DD format
    time = Column(String(8), nullable=True)    # HH:MM:SS format
    timestamp = Column(DateTime, nullable=False, default=datetime.now)  # Combined datetime
    metric = Column(String(100), nullable=False)  # e.g., "impressions", "reach", "engagement"
    source = Column(String(50), nullable=False)  # e.g., "facebook", "instagram"
    category = Column(String(100), nullable=True)  # e.g., "post_engagement", "page_insights"
    value = Column(Float, nullable=False)  # The actual numeric value
    unit = Column(String(50), nullable=True)  # e.g., "count", "percentage", "rate"
    
    def __repr__(self):
        return f"<MetricData(date={self.date}, metric={self.metric}, value={self.value})>"


class FacebookPost(Base):
    """Facebook posts table."""
    __tablename__ = "facebook_posts"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    post_id = Column(String(100), unique=True, nullable=False)
    permalink_url = Column(String(500), nullable=True)
    created_time = Column(String(50), nullable=True)
    date = Column(String(10), nullable=False)
    time = Column(String(8), nullable=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.now)
    message = Column(String(500), nullable=True)
    reactions = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    shares = Column(Integer, default=0)
    total_engagement = Column(Integer, default=0)
    engagement_rate = Column(Float, default=0.0)
    post_reach = Column(Integer, default=0)
    post_impressions = Column(Integer, default=0)
    post_clicks = Column(Integer, default=0)
    fan_count = Column(Integer, default=0)
    stats_error = Column(String(500), nullable=True)
    insights_error = Column(String(500), nullable=True)


class InstagramPost(Base):
    """Instagram posts table."""
    __tablename__ = "instagram_posts"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    media_id = Column(String(100), unique=True, nullable=False)
    date = Column(String(10), nullable=False)
    time = Column(String(8), nullable=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.now)
    caption = Column(String(500), nullable=True)
    like_count = Column(Integer, default=0)
    comments_count = Column(Integer, default=0)
    media_type = Column(String(50), nullable=True)
    media_product_type = Column(String(50), nullable=True)
    permalink = Column(String(500), nullable=True)
    impressions = Column(Integer, default=0)
    reach = Column(Integer, default=0)
    saved = Column(Integer, default=0)
    shares = Column(Integer, default=0)
    video_views = Column(Integer, default=0)
    plays = Column(Integer, default=0)
    total_interactions = Column(Integer, default=0)
    engagement_rate = Column(Float, default=0.0)


class YouTubeVideo(Base):
    """YouTube video table."""
    __tablename__ = "youtube_videos"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    video_id = Column(String(100), unique=True, nullable=False)
    date = Column(String(10), nullable=False)
    time = Column(String(8), nullable=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.now)
    title = Column(String(500), nullable=True)
    description = Column(String(5000), nullable=True)
    view_count = Column(Integer, default=0)
    like_count = Column(Integer, default=0)
    comment_count = Column(Integer, default=0)
    engagement_rate = Column(Float, default=0.0)
    thumbnail_url = Column(String(500), nullable=True)
    permalink = Column(String(500), nullable=True)


class DailySummary(Base):
    """Daily aggregated metrics for dashboards."""
    __tablename__ = "daily_summary"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String(10), nullable=False)
    platform = Column(String(50), nullable=False)
    reach = Column(Integer, default=0)
    impressions = Column(Integer, default=0)
    engagement = Column(Integer, default=0)
    followers = Column(Integer, default=0)
    followers_growth = Column(Float, default=0.0)


class FollowersHistory(Base):
    __tablename__ = "followers_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String(10), nullable=False)
    platform = Column(String(50), nullable=False)
    followers = Column(Integer, default=0)
    growth_rate = Column(Float, default=0.0)


class BestPostingTime(Base):
    __tablename__ = "best_posting_time"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hour = Column(Integer, nullable=False)
    avg_engagement = Column(Float, default=0.0)


class AlertsLog(Base):
    __tablename__ = "alerts_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(String(50), nullable=False)
    alert_type = Column(String(100), nullable=True)
    message = Column(String(1000), nullable=False)
    details = Column(String(2000), nullable=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.now)

    def __repr__(self):
        return f"<AlertsLog(platform={self.platform}, message={self.message})>"


class TopPost(Base):
    __tablename__ = "top_posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    post_id = Column(String(100), nullable=False)
    platform = Column(String(50), nullable=False)
    date = Column(String(10), nullable=True)
    time = Column(String(8), nullable=True)
    caption = Column(String(500), nullable=True)
    likes = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    shares = Column(Integer, default=0)
    engagement = Column(Integer, default=0)


class AIInsight(Base):
    __tablename__ = "ai_insights"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.now)
    insight_type = Column(String(50), nullable=False)  # 'daily', 'weekly', 'alert'
    content = Column(String(5000), nullable=False)


def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(engine)

    # Lightweight migration: ensure new columns exist in existing tables (SQLite doesn't alter columns via create_all)
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    with engine.connect() as conn:
        # Add created_time to facebook_posts if missing
        if inspector.has_table("facebook_posts"):
            cols = [c["name"] for c in inspector.get_columns("facebook_posts")]
            if "created_time" not in cols:
                try:
                    conn.execute(text("ALTER TABLE facebook_posts ADD COLUMN created_time TEXT"))
                    print("Migrated: added 'created_time' column to facebook_posts")
                except Exception:
                    pass

        # Add engagement_rate to instagram_posts if missing
        if inspector.has_table("instagram_posts"):
            cols = [c["name"] for c in inspector.get_columns("instagram_posts")]
            if "engagement_rate" not in cols:
                try:
                    conn.execute(text("ALTER TABLE instagram_posts ADD COLUMN engagement_rate FLOAT DEFAULT 0.0"))
                    print("Migrated: added 'engagement_rate' column to instagram_posts")
                except Exception:
                    pass

        # Add followers_growth to daily_summary if missing
        if inspector.has_table("daily_summary"):
            cols = [c["name"] for c in inspector.get_columns("daily_summary")]
            if "followers_growth" not in cols:
                try:
                    conn.execute(text("ALTER TABLE daily_summary ADD COLUMN followers_growth FLOAT DEFAULT 0.0"))
                    print("Migrated: added 'followers_growth' column to daily_summary")
                except Exception:
                    pass

        # Add growth_rate to followers_history if missing
        if inspector.has_table("followers_history"):
            cols = [c["name"] for c in inspector.get_columns("followers_history")]
            if "growth_rate" not in cols:
                try:
                    conn.execute(text("ALTER TABLE followers_history ADD COLUMN growth_rate FLOAT DEFAULT 0.0"))
                    print("Migrated: added 'growth_rate' column to followers_history")
                except Exception:
                    pass

    print("Database initialized successfully with Power BI schema.")


def get_session():
    """Get a new database session."""
    return Session()
