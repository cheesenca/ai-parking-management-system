# import_forecast_to_db.py
import pandas as pd
from sqlalchemy import create_engine

# KONFIGURASI DATABASE
db_user = 'postgres'
db_password = 'kalvinbk'
db_host = 'localhost'
db_port = '5432'
db_name = 'capstone_parking_db'

engine = create_engine(f'postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}')

# IMPORT CSV KE TABEL

# DAILY
df_daily = pd.read_csv('forecast/daily_forecast_location_realistic.csv')
df_daily.to_sql('daily_forecast', engine, if_exists='replace', index=False)
print("Daily forecast successfully imported!")

# WEEKLY
df_weekly = pd.read_csv('forecast/weekly_forecast_location_var.csv')
df_weekly.to_sql('weekly_forecast', engine, if_exists='replace', index=False)
print("Weekly forecast successfully imported!")

# MONTHLY
df_monthly = pd.read_csv('forecast/monthly_forecast_location_var.csv')
df_monthly.to_sql('monthly_forecast', engine, if_exists='replace', index=False)
print("Monthly forecast successfully imported!")