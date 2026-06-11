import json
import os
from pathlib import Path

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parent


def load_env_value(key, default=""):
    value = os.getenv(key)
    if value:
        return value

    env_path = ROOT_DIR / ".env"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8-sig") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                env_key, env_value = line.split("=", 1)
                if env_key.strip().lstrip("\ufeff") == key:
                    return env_value.strip().strip('"').strip("'")

    return default


def normalize_property_id(property_id: str) -> str:
    value = str(property_id or "").strip()
    return value.replace("properties/", "").strip()


def get_google_auth_status():
    oauth_client_path = Path(load_env_value("GOOGLE_OAUTH_CREDENTIALS", str(ROOT_DIR / "client_secret.json"))).expanduser()
    service_account_path = Path(load_env_value("GOOGLE_APPLICATION_CREDENTIALS", str(ROOT_DIR / "service_account.json"))).expanduser()
    oauth_token_path = Path(load_env_value("GOOGLE_OAUTH_TOKEN", str(ROOT_DIR / "token.json"))).expanduser()
    return {
        "oauth_path": oauth_client_path if oauth_client_path.exists() else None,
        "service_path": service_account_path if service_account_path.exists() else None,
        "oauth_token_path": oauth_token_path if oauth_token_path.exists() else None,
    }


def build_report_request(property_id: str, days: int = 30):
    """Build a GA4 report request for a small, useful analytics summary."""
    try:
        from google.analytics.data_v1beta import BetaAnalyticsDataClient
        from google.analytics.data_v1beta.types import RunReportRequest
    except Exception as exc:  # pragma: no cover - runtime dependency path
        raise RuntimeError("google-analytics-data is not installed") from exc

    normalized_property = normalize_property_id(property_id)
    property_name = f"properties/{normalized_property}"

    return RunReportRequest(
        property=property_name,
        dimensions=[{"name": "date"}],
        metrics=[
            {"name": "activeUsers"},
            {"name": "sessions"},
            {"name": "screenPageViews"},
            {"name": "newUsers"},
        ],
        date_ranges=[{"start_date": f"{days}daysAgo", "end_date": "today"}],
        order_bys=[{"desc": True, "metric": {"metric_name": "activeUsers"}}],
    )


def build_traffic_request(property_id: str, days: int = 30):
    """Build a GA4 channel-group request for traffic source analysis."""
    try:
        from google.analytics.data_v1beta import BetaAnalyticsDataClient
        from google.analytics.data_v1beta.types import RunReportRequest
    except Exception as exc:  # pragma: no cover - runtime dependency path
        raise RuntimeError("google-analytics-data is not installed") from exc

    normalized_property = normalize_property_id(property_id)
    property_name = f"properties/{normalized_property}"

    return RunReportRequest(
        property=property_name,
        dimensions=[{"name": "sessionDefaultChannelGroup"}],
        metrics=[{"name": "sessions"}, {"name": "activeUsers"}, {"name": "screenPageViews"}],
        date_ranges=[{"start_date": f"{days}daysAgo", "end_date": "today"}],
        order_bys=[{"desc": True, "metric": {"metric_name": "sessions"}}],
    )


def load_oauth_credentials():
    """Create Google OAuth credentials for the signed-in user account."""
    try:
        import json

        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
    except Exception as exc:  # pragma: no cover - runtime dependency path
        raise RuntimeError("Google OAuth libraries are not installed") from exc

    scopes = ["https://www.googleapis.com/auth/analytics.readonly"]
    client_config_path = load_env_value("GOOGLE_OAUTH_CREDENTIALS", str(ROOT_DIR / "client_secret.json"))
    token_path = load_env_value("GOOGLE_OAUTH_TOKEN", str(ROOT_DIR / "token.json"))

    if not client_config_path:
        raise FileNotFoundError("GOOGLE_OAUTH_CREDENTIALS is not set")

    client_config_file = Path(client_config_path).expanduser()
    if not client_config_file.exists():
        raise FileNotFoundError(f"OAuth client credentials file not found: {client_config_file}")

    token_file = Path(token_path).expanduser()
    credentials = None
    if token_file.exists():
        credentials = Credentials.from_authorized_user_file(str(token_file), scopes)

    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            with open(client_config_file, "r", encoding="utf-8") as handle:
                client_config = json.load(handle)

            flow = InstalledAppFlow.from_client_config(client_config, scopes=scopes)
            credentials = flow.run_local_server(port=0, open_browser=True)

            token_file.parent.mkdir(parents=True, exist_ok=True)
            with open(token_file, "w", encoding="utf-8") as handle:
                handle.write(credentials.to_json())

    return credentials


def load_client():
    """Create a GA4 client using OAuth first, then fall back to the service account."""
    try:
        from google.analytics.data_v1beta import BetaAnalyticsDataClient
    except Exception as exc:  # pragma: no cover - runtime dependency path
        raise RuntimeError("google-analytics-data is not installed") from exc

    oauth_client_file = load_env_value("GOOGLE_OAUTH_CREDENTIALS", str(ROOT_DIR / "client_secret.json"))
    oauth_token_file = load_env_value("GOOGLE_OAUTH_TOKEN", str(ROOT_DIR / "token.json"))

    oauth_client = Path(oauth_client_file).expanduser() if oauth_client_file else None
    oauth_token = Path(oauth_token_file).expanduser() if oauth_token_file else None

    credentials_path = load_env_value("GOOGLE_APPLICATION_CREDENTIALS", str(ROOT_DIR / "service_account.json"))
    service_account_file = Path(credentials_path).expanduser() if credentials_path else None

    # If service account credentials are configured and OAuth has not yet completed,
    # prefer service account so the dashboard can load without triggering the unverified OAuth consent flow.
    if service_account_file and service_account_file.exists() and (not oauth_token or not oauth_token.exists()):
        return BetaAnalyticsDataClient.from_service_account_file(str(service_account_file))

    if oauth_client and oauth_client.exists():
        try:
            credentials = load_oauth_credentials()
            return BetaAnalyticsDataClient(credentials=credentials)
        except Exception:
            pass

    if service_account_file and service_account_file.exists():
        return BetaAnalyticsDataClient.from_service_account_file(str(service_account_file))

    raise RuntimeError("GOOGLE_APPLICATION_CREDENTIALS is not set and no OAuth credentials are available")


def fetch_ga4_summary(property_id=None, days: int = 30):
    """Fetch GA4 summary metrics and return them as a friendly dictionary."""
    property_id = normalize_property_id(property_id or load_env_value("GA4_PROPERTY_ID", ""))
    if not property_id:
        return {"error": "GA4_PROPERTY_ID is missing. Set it in .env to the Google Analytics property ID."}

    try:
        client = load_client()
        request = build_report_request(property_id, days=days)
        response = client.run_report(request)

        rows = []
        for row in response.rows:
            date_value = row.dimension_values[0].value if row.dimension_values else ""
            metrics = {metric.name: int(metric_value.value) for metric, metric_value in zip(request.metrics, row.metric_values)}
            rows.append({"date": date_value, **metrics})

        df = pd.DataFrame(rows)
        if df.empty:
            return {"error": None, "rows": [], "total_active_users": 0, "total_sessions": 0, "total_page_views": 0, "total_new_users": 0, "trend": pd.DataFrame()}

        summary = {
            "error": None,
            "property_id": property_id,
            "total_active_users": int(df["activeUsers"].sum()),
            "total_sessions": int(df["sessions"].sum()),
            "total_page_views": int(df["screenPageViews"].sum()),
            "total_new_users": int(df["newUsers"].sum()),
            "rows": rows,
            "trend": df.sort_values("date"),
        }
        return summary
    except Exception as exc:
        return {"error": str(exc), "rows": [], "total_active_users": 0, "total_sessions": 0, "total_page_views": 0, "total_new_users": 0, "trend": pd.DataFrame()}


def fetch_ga4_channels(property_id=None, days: int = 30):
    """Fetch channel-group breakdown for attractive traffic analysis visuals."""
    property_id = normalize_property_id(property_id or load_env_value("GA4_PROPERTY_ID", ""))
    if not property_id:
        return {"error": "GA4_PROPERTY_ID is missing. Set it in .env to the Google Analytics property ID."}

    try:
        client = load_client()
        request = build_traffic_request(property_id, days=days)
        response = client.run_report(request)

        rows = []
        for row in response.rows:
            channel = row.dimension_values[0].value if row.dimension_values else "(direct)"
            metrics = {metric.name: int(metric_value.value) for metric, metric_value in zip(request.metrics, row.metric_values)}
            rows.append({"channel": channel, **metrics})

        df = pd.DataFrame(rows)
        return {"error": None, "rows": rows, "channels": df}
    except Exception as exc:
        return {"error": str(exc), "rows": [], "channels": pd.DataFrame()}
