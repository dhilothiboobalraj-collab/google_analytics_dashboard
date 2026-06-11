"""Scheduler for automated data collection."""
import schedule
import time
from datetime import datetime
from data_fetcher import main as fetch_data


def scheduled_job():
    """Job to run at scheduled intervals."""
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Running scheduled data fetch...")
    try:
        fetch_data()
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Scheduled fetch completed successfully.\n")
    except Exception as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error during scheduled fetch: {e}\n")


def start_scheduler(run_time="01:00"):
    """Start the scheduler."""
    # Schedule the job to run every day at the specified time
    schedule.every().day.at(run_time).do(scheduled_job)

    print(f"Scheduler started. Data will be fetched daily at {run_time}")
    print("Press Ctrl+C to stop the scheduler.\n")

    # Keep the scheduler running
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every 60 seconds


def start_scheduler_interval(run_minutes: int = 5):
    """Start a scheduler that runs every `run_minutes` minutes."""
    schedule.every(run_minutes).minutes.do(scheduled_job)

    print(f"Scheduler started. Data will be fetched every {run_minutes} minutes")
    print("Press Ctrl+C to stop the scheduler.\n")

    while True:
        schedule.run_pending()
        time.sleep(10)


if __name__ == "__main__":
    try:
        # Default: run every 5 minutes for automatic updates
        start_scheduler_interval(run_minutes=5)
    except KeyboardInterrupt:
        print("\n\nScheduler stopped by user.")
