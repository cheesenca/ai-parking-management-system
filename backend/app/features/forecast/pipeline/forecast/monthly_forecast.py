import pandas as pd

# Nama CSV daily terakhir
daily_csv = 'forecast/daily_forecast_location_realistic.csv'

# Baca CSV
df = pd.read_csv(daily_csv, parse_dates=['ds'])

# Tambahkan kolom year dan month
df['year'] = df['ds'].dt.year
df['month'] = df['ds'].dt.month

# Daftar lokasi parkir
locations = ['P1W', 'P1E', 'P2W', 'P2E', 'P3W', 'P3E']

monthly_forecast = []

# Agregasi per bulan
for (y, m), group in df.groupby(['year', 'month']):
    row = {'year': y, 'month': m}
    total_vehicles = 0
    for loc in locations:
        predicted = group[f'{loc}_predicted'].sum()  # Total kendaraan per bulan
        available = group[f'{loc}_available'].min()  # Ambil minimum agar status bisa variatif
        # Tentukan status
        if available <= 0:
            status = 'Full'
        elif available < 0.2 * group[f'{loc}_predicted'].max():  # kurang dari 20% prediksi tertinggi
            status = 'Warning'
        else:
            status = 'Normal'
        row[f'{loc}_predicted'] = predicted
        row[f'{loc}_available'] = available
        row[f'{loc}_status'] = status
        total_vehicles += predicted
    row['total_vehicles'] = total_vehicles
    monthly_forecast.append(row)

# Simpan CSV monthly
df_monthly = pd.DataFrame(monthly_forecast)
df_monthly.to_csv('forecast/monthly_forecast_location_var.csv', index=False)

print("Monthly forecast success. CSV saved as forecast/monthly_forecast_location_var.csv")