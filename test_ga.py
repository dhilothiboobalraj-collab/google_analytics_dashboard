import os
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import RunReportRequest
from google.oauth2 import service_account

PROPERTY_ID = os.getenv("GA4_PROPERTY_ID", "")
if not PROPERTY_ID:
    raise SystemExit("GA4_PROPERTY_ID is not set. Add it to the environment or .env file.")

credentials = service_account.Credentials.from_service_account_file(
    "credentials/ga-service-account.json"
)

client = BetaAnalyticsDataClient(credentials=credentials)

request = RunReportRequest(
    property=f"properties/{PROPERTY_ID}",
    dimensions=[{"name": "date"}],
    metrics=[{"name": "activeUsers"}],
    date_ranges=[{"start_date": "7daysAgo", "end_date": "today"}],
)

response = client.run_report(request)

for row in response.rows:
    print(row.dimension_values[0].value, row.metric_values[0].value)
