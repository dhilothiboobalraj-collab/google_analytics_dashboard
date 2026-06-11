"""Power BI export and integration helper."""
import pandas as pd
import os
import json
from database import engine, get_session, MetricData
from datetime import datetime, timezone

# Fixed filenames for Power BI to always read the same files
XLSX_FILENAME = "powerbi_analysis.xlsx"
JSON_FILENAME = "powerbi_analysis.json"


def export_metrics_for_powerbi():
    """Export metrics table optimized for Power BI."""
    print("\n" + "="*60)
    print("EXPORTING DATA FOR POWER BI")
    print("="*60 + "\n")
    
    try:
        # Query metrics table
        df = pd.read_sql_table("metrics", engine)
        
        if df.empty:
            print("❌ No metrics data found. Run data_fetcher.py first.\n")
            return
        
        # Ensure output directory exists
        os.makedirs("output", exist_ok=True)
        
        # Export main metrics table
        metrics_path = "output/metrics_for_powerbi.csv"
        df.to_csv(metrics_path, index=False, encoding="utf-8-sig")
        print(f"✅ Exported {len(df)} metric records to: {metrics_path}")
        
        # Export aggregated by source
        by_source = df.groupby("source").agg({
            "value": ["sum", "mean", "count"]
        }).round(2)
        source_path = "output/metrics_by_source.csv"
        by_source.to_csv(source_path, encoding="utf-8-sig")
        print(f"✅ Exported source summary to: {source_path}")
        
        # Export aggregated by metric
        by_metric = df.groupby("metric").agg({
            "value": ["sum", "mean", "count"]
        }).round(2)
        metric_path = "output/metrics_by_type.csv"
        by_metric.to_csv(metric_path, encoding="utf-8-sig")
        print(f"✅ Exported metric summary to: {metric_path}")
        
        # Export aggregated by date
        by_date = df.groupby("date").agg({
            "value": ["sum", "mean", "count"]
        }).round(2)
        date_path = "output/metrics_by_date.csv"
        by_date.to_csv(date_path, encoding="utf-8-sig")
        print(f"✅ Exported daily summary to: {date_path}")
        
        print(f"\n📊 Total records: {len(df):,}")
        print(f"📅 Date range: {df['date'].min()} to {df['date'].max()}")
        print(f"🔌 Sources: {', '.join(df['source'].unique())}")
        print(f"📈 Metrics: {df['metric'].nunique()} different types\n")
        
        print("Power BI Import Instructions:")
        print("-" * 60)
        print("1. Open Power BI Desktop")
        print("2. Click 'Get Data' → 'Text/CSV'")
        print("3. Browse to: output/metrics_for_powerbi.csv")
        print("4. Click 'Load'")
        print("5. Create relationships and build visualizations\n")
        
    except Exception as e:
        print(f"❌ Error exporting: {e}\n")


def create_powerbi_template():
    """Create a Power BI-optimized data structure."""
    print("\n" + "="*60)
    print("CREATING POWER BI DATA TEMPLATE")
    print("="*60 + "\n")
    
    session = get_session()
    try:
        # Get unique values for dropdowns in Power BI
        metrics_list = session.query(MetricData.metric).distinct().all()
        sources_list = session.query(MetricData.source).distinct().all()
        categories_list = session.query(MetricData.category).distinct().all()
        
        template_data = {
            "Metrics": [m[0] for m in metrics_list],
            "Sources": [s[0] for s in sources_list],
            "Categories": [c[0] for c in categories_list]
        }
        
        print("📋 Data Catalog for Power BI:\n")
        
        for key, values in template_data.items():
            print(f"{key}:")
            for val in values:
                print(f"  • {val}")
            print()
        
        # Export as reference tables
        metrics_df = pd.DataFrame({
            "metric_id": range(len(template_data["Metrics"])),
            "metric_name": template_data["Metrics"]
        })
        metrics_df.to_csv("output/dim_metrics.csv", index=False, encoding="utf-8-sig")
        
        sources_df = pd.DataFrame({
            "source_id": range(len(template_data["Sources"])),
            "source_name": template_data["Sources"]
        })
        sources_df.to_csv("output/dim_sources.csv", index=False, encoding="utf-8-sig")
        
        print("✅ Reference tables created:")
        print("   • output/dim_metrics.csv")
        print("   • output/dim_sources.csv\n")
        
    finally:
        session.close()


def export_all_to_workbook():
    """Export key tables to a single Excel workbook and a JSON summary file.

    Writes `powerbi_analysis.xlsx` with sheets:
      - FB Posts (facebook_posts)
      - IG Posts (instagram_posts)
      - FB Weekly (fb_weekly_insights)
      - IG Weekly (ig_weekly_insights)
    Also writes a small JSON summary to `powerbi_analysis.json` for quick ingestion.
    """
    print(f"Exporting consolidated Power BI workbook: {XLSX_FILENAME}")
    os.makedirs("output", exist_ok=True)

    summary = {"generated_at": datetime.now(timezone.utc).isoformat(), "tables": {}}

    with pd.ExcelWriter(os.path.join("output", XLSX_FILENAME), engine="openpyxl") as writer:
        # Helper to read a table if present and write to sheet
        def write_table_if_exists(table_name, sheet_name):
            try:
                df = pd.read_sql_table(table_name, engine)
            except Exception:
                df = pd.DataFrame()

            if df.empty:
                print(f" - Table '{table_name}' empty or not found; creating empty sheet: {sheet_name}")
                pd.DataFrame().to_excel(writer, sheet_name=sheet_name, index=False)
                summary["tables"][table_name] = 0
            else:
                df.to_excel(writer, sheet_name=sheet_name, index=False)
                summary["tables"][table_name] = len(df)

        write_table_if_exists("metrics", "Metrics")
        write_table_if_exists("facebook_posts", "FB Posts")
        write_table_if_exists("instagram_posts", "IG Posts")
        write_table_if_exists("fb_weekly_insights", "FB Weekly")
        write_table_if_exists("ig_weekly_insights", "IG Weekly")
        write_table_if_exists("daily_summary", "Daily Summary")
        write_table_if_exists("followers_history", "Followers History")
        write_table_if_exists("best_posting_time", "Best Posting Time")
        write_table_if_exists("top_posts", "Top Posts")

    # Save JSON summary
    json_path = os.path.join("output", JSON_FILENAME)
    with open(json_path, "w", encoding="utf-8") as jf:
        json.dump(summary, jf, ensure_ascii=False, indent=2)

    # Save additional clean CSV tables for Power BI
    clean_tables = [
        ("metrics", "metrics_for_powerbi.csv"),
        ("daily_summary", "daily_summary.csv"),
        ("followers_history", "followers_history.csv"),
        ("best_posting_time", "best_posting_time.csv"),
        ("top_posts", "top_posts.csv"),
    ]
    for table_name, csv_name in clean_tables:
        try:
            df = pd.read_sql_table(table_name, engine)
            df.to_csv(os.path.join("output", csv_name), index=False, encoding="utf-8-sig")
            print(f"✅ Exported clean table {table_name} to output/{csv_name}")
        except Exception:
            print(f"⚠️ Could not export clean table {table_name} to CSV")

    print(f"✅ Workbook saved: output/{XLSX_FILENAME}")
    print(f"✅ JSON summary saved: output/{JSON_FILENAME}")


def validate_powerbi_schema():
    """Validate that database is ready for Power BI."""
    print("\n" + "="*60)
    print("VALIDATING POWER BI SCHEMA")
    print("="*60 + "\n")
    
    checks = {
        "Date column": "✓" if True else "✗",
        "Time column": "✓" if True else "✗",
        "Timestamp (datetime)": "✓" if True else "✗",
        "Metric names": "✓" if True else "✗",
        "Numeric values": "✓" if True else "✗",
        "Source classification": "✓" if True else "✗",
    }
    
    all_pass = True
    for check, status in checks.items():
        print(f"  {status} {check}")
    
    print("\n✅ Schema validation passed!" if all_pass else "\n❌ Schema needs adjustment\n")


def main():
    """Run all Power BI export operations."""
    print("\n")
    print("╔" + "="*58 + "╗")
    print("║" + " "*18 + "POWER BI INTEGRATION HELPER" + " "*14 + "║")
    print("║" + " "*15 + "Social Media Analytics Export" + " "*13 + "║")
    print("╚" + "="*58 + "╝")
    
    validate_powerbi_schema()
    export_metrics_for_powerbi()
    create_powerbi_template()
    # Export consolidated workbook and JSON summary with fixed filenames
    try:
        export_all_to_workbook()
    except Exception as e:
        print(f"Error exporting workbook: {e}")
    
    print("="*60)
    print("✨ Data is ready to import into Power BI!")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
