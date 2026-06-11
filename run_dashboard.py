import os
import sys
from dotenv import load_dotenv

# Ensure the project root is in the Python path
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))

# Load .env so that USER_ACCESS_TOKEN and other secrets are available
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from social_media import get_page_token, export_dashboard_csv

def main():
    # Obtain Facebook Page token using the user access token from environment or .env
    page_token, error = get_page_token()
    if error:
        print(f"Failed to get page token: {error}")
        return
    # Use the same USER_ACCESS_TOKEN for Instagram (the function expects user token)
    user_token = os.getenv("USER_ACCESS_TOKEN")
    if not user_token:
        print("USER_ACCESS_TOKEN is not set. Ensure it is defined in the environment or .env file.")
        return
    # Export all dashboards to CSV files under the output directory
    export_dashboard_csv(page_token, user_token)

if __name__ == "__main__":
    main()
