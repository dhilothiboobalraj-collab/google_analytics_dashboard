import pandas as pd

# Simulate what the dashboard does
data = {
    "date": ["2026-06-02", "2026-06-01", "2026-06-01"],
    "time": ["07:28:04", "12:18:30", "06:45:12"],
}
df = pd.DataFrame(data)

# This is what the dashboard does:
df["datetime_utc"] = pd.to_datetime(
    df["date"].astype(str) + " " + df["time"].astype(str),
    format="%Y-%m-%d %H:%M:%S",
    errors="coerce",
)
df["datetime_utc"] = df["datetime_utc"].dt.tz_localize("UTC")
df["datetime_ist"] = df["datetime_utc"].dt.tz_convert("Asia/Kolkata")
df["time_ist"] = df["datetime_ist"].dt.strftime("%H:%M")

print("Original UTC time -> IST time:")
for _, row in df.iterrows():
    print(f"  {row['time']} UTC  ->  {row['time_ist']} IST")
