import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'capstone_parking.settings')
sys.path.insert(0, os.getcwd())
django.setup()

from django.db import connection

print("=" * 70)
print("KOLOM DI TABEL DATABASE")
print("=" * 70)

with connection.cursor() as c:
    # Check daily_forecast columns
    c.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name='daily_forecast' 
        ORDER BY ordinal_position
    """)
    print("\ndaily_forecast columns:")
    for name, dtype in c.fetchall():
        print(f"  {name:30} {dtype}")
    
    # Check weekly_forecast columns
    c.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name='weekly_forecast' 
        ORDER BY ordinal_position
    """)
    print("\nweekly_forecast columns:")
    for name, dtype in c.fetchall():
        print(f"  {name:30} {dtype}")
    
    # Check monthly_forecast columns
    c.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name='monthly_forecast' 
        ORDER BY ordinal_position
    """)
    print("\nmonthly_forecast columns:")
    for name, dtype in c.fetchall():
        print(f"  {name:30} {dtype}")
