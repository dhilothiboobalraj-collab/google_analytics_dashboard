"""Database initialization script for Power BI integration."""
from database import init_db, engine, get_session, MetricData
from sqlalchemy import inspect, text
import sys


def print_schema():
    """Print database schema information."""
    print("\n" + "="*60)
    print("DATABASE SCHEMA FOR POWER BI")
    print("="*60 + "\n")
    
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    if not tables:
        print("No tables found. Initializing database...")
        init_db()
        tables = inspector.get_table_names()
    
    for table_name in tables:
        print(f"\n📊 Table: {table_name}")
        print("-" * 60)
        columns = inspector.get_columns(table_name)
        
        for col in columns:
            col_type = str(col['type'])
            nullable = "✓ Nullable" if col['nullable'] else "✗ Required"
            print(f"  • {col['name']:<20} {col_type:<15} {nullable}")


def check_metrics_table():
    """Verify metrics table exists with proper schema."""
    print("\n" + "="*60)
    print("POWER BI METRICS TABLE VERIFICATION")
    print("="*60 + "\n")
    
    inspector = inspect(engine)
    
    if "metrics" not in inspector.get_table_names():
        print("❌ Metrics table not found. Creating now...")
        init_db()
    else:
        print("✅ Metrics table exists\n")
    
    columns = inspector.get_columns("metrics")
    print("Required columns for Power BI:")
    print("-" * 60)
    
    required_cols = {
        "date": "Date in YYYY-MM-DD format",
        "time": "Time in HH:MM:SS format",
        "timestamp": "Combined datetime for Power BI",
        "metric": "Metric name (e.g., impressions, reach)",
        "source": "Data source (facebook, instagram)",
        "category": "Category (page_insights, post_engagement, etc.)",
        "value": "Numeric value",
        "unit": "Unit of measurement"
    }
    
    col_names = [col['name'] for col in columns]
    
    for req_col, description in required_cols.items():
        status = "✓" if req_col in col_names else "✗"
        print(f"  {status} {req_col:<15} - {description}")


def count_records():
    """Count records in each table."""
    print("\n" + "="*60)
    print("DATA RECORD COUNT")
    print("="*60 + "\n")
    
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    session = get_session()
    try:
        for table_name in tables:
            result = session.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
            count = result.scalar()
            print(f"  📈 {table_name:<25} {count:>10,} records")
    finally:
        session.close()


def display_sample_metrics():
    """Display sample data from metrics table."""
    print("\n" + "="*60)
    print("SAMPLE METRICS DATA (Power BI Ready)")
    print("="*60 + "\n")
    
    session = get_session()
    try:
        metrics = session.query(MetricData).limit(5).all()
        
        if not metrics:
            print("  No metrics data yet. Run data_fetcher.py to populate.\n")
        else:
            print(f"{'Date':<12} {'Time':<10} {'Metric':<20} {'Source':<12} {'Value':<10}")
            print("-" * 70)
            
            for m in metrics:
                date_str = m.date or "N/A"
                time_str = m.time or "N/A"
                metric_str = (m.metric or "N/A")[:20]
                source_str = (m.source or "N/A")[:12]
                value_str = str(m.value)[:10]
                
                print(f"{date_str:<12} {time_str:<10} {metric_str:<20} {source_str:<12} {value_str:<10}")
            
            print()
    finally:
        session.close()


def export_to_csv():
    """Export metrics table to CSV for Power BI."""
    import pandas as pd
    
    print("\n" + "="*60)
    print("EXPORTING TO CSV FOR POWER BI")
    print("="*60 + "\n")
    
    try:
        df = pd.read_sql_table("metrics", engine)
        
        if df.empty:
            print("  No data to export\n")
        else:
            csv_path = "output/metrics_for_powerbi.csv"
            df.to_csv(csv_path, index=False)
            print(f"  ✅ Exported {len(df)} records to {csv_path}\n")
            print("  Ready to import in Power BI Desktop!")
            print("  → Open Power BI → Get Data → CSV → Select file\n")
    except Exception as e:
        print(f"  ❌ Error exporting: {e}\n")


def main():
    """Run all database checks and display info."""
    print("\n")
    print("╔" + "="*58 + "╗")
    print("║" + " "*15 + "SOCIAL MEDIA ANALYTICS DATABASE" + " "*12 + "║")
    print("║" + " "*20 + "Power BI Preparation" + " "*18 + "║")
    print("╚" + "="*58 + "╝")
    
    # Initialize database
    init_db()
    
    # Check schema
    print_schema()
    check_metrics_table()
    count_records()
    display_sample_metrics()
    export_to_csv()
    
    print("="*60)
    print("✨ Database is ready for Power BI integration!")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
