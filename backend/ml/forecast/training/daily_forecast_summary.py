import pandas as pd

# Load CSV hasil forecast realistic
df = pd.read_csv("forecast/daily_forecast_location_compare_realistic.csv")

# List kolom lokasi
location_columns = ['P1W_available','P1E_available','P2W_available','P2E_available','P3W_available','P3E_available']

# Hitung total slot tersisa per hari
df['total_available'] = df[location_columns].sum(axis=1)

# Tentukan status keseluruhan
def overall_status(available):
    if available == 0:
        return "Full"
    elif available <= 15:  # threshold bisa disesuaikan
        return "Warning"
    else:
        return "Normal"

df['overall_status'] = df['total_available'].apply(overall_status)

# Ringkasan
summary = df[['ds','yhat','total_available','overall_status']]
summary.rename(columns={'ds':'Tanggal','yhat':'Total_Kendaraan','total_available':'Total_Slot_Tersisa','overall_status':'Status'}, inplace=True)

# Tampilkan 10 baris pertama
print("=== Daily Forecast Summary ===")
print(summary.head(10))

# Simpan ringkasan ke CSV baru
summary.to_csv("forecast/daily_forecast_summary.csv", index=False)
print("\nSummary CSV saved as forecast/daily_forecast_summary.csv")