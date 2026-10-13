import pandas as pd
from prophet import Prophet
from statsmodels.tsa.arima.model import ARIMA
import matplotlib.pyplot as plt
from sklearn.metrics import mean_absolute_error, mean_squared_error
import numpy as np

# Load Dataset
df = pd.read_csv("dataset/ParkingRecord_Preprocessed.csv")
df['TIME_SCAN'] = pd.to_datetime(df['TIME_SCAN'])

# Total kendaraan per hari
daily_total = df.groupby('date').size()
daily_total.index = pd.to_datetime(daily_total.index)

# Resample daily for ARIMA
daily_total_arima = daily_total.resample('D').sum()  # isi tanggal hilang = 0

# Prophet Forecast
prophet_df = daily_total.reset_index().rename(columns={'date':'ds', 0:'y'})
prophet_model = Prophet(daily_seasonality=True, weekly_seasonality=True)
prophet_model.fit(prophet_df)

future = prophet_model.make_future_dataframe(periods=30)
forecast_prophet = prophet_model.predict(future)

# ARIMA Forecast
arima_model = ARIMA(daily_total_arima, order=(5,1,0))
arima_fit = arima_model.fit()
forecast_arima = arima_fit.forecast(30)

# Comparing Model
actual = daily_total_arima[-30:]
pred_prophet = forecast_prophet['yhat'][-30:]
pred_arima = forecast_arima[-30:]

mae_prophet = mean_absolute_error(actual, pred_prophet)
mae_arima = mean_absolute_error(actual, pred_arima)
rmse_prophet = np.sqrt(mean_squared_error(actual, pred_prophet))
rmse_arima = np.sqrt(mean_squared_error(actual, pred_arima))

print("=== Daily Forecast Model Comparison ===")
print(f"Prophet MAE: {mae_prophet:.2f}, RMSE: {rmse_prophet:.2f}")
print(f"ARIMA   MAE: {mae_arima:.2f}, RMSE: {rmse_arima:.2f}")

plt.figure(figsize=(12,5))
plt.plot(actual.index, actual.values, label='Actual')
plt.plot(pred_prophet.index, pred_prophet.values, label='Prophet Forecast')
plt.plot(pred_arima.index, pred_arima.values, label='ARIMA Forecast')
plt.title("Daily Forecast: Actual vs Prophet vs ARIMA")
plt.xlabel("Date")
plt.ylabel("Jumlah Kendaraan")
plt.legend()
plt.show()

# Forecast per Location (Proportional of total 300 slots)
location_prop = {
    "P1W": 0.15, "P1E": 0.15,
    "P2W": 0.15, "P2E": 0.10,
    "P3W": 0.25, "P3E": 0.20
}

# Capacity per location = proportion of total 300 slots
total_slots = 300
capacity_per_location = {loc: total_slots*prop for loc, prop in location_prop.items()}

forecast_location = forecast_prophet[['ds','yhat']].copy()
for loc, prop in location_prop.items():
    # predicted vehicles per location = total forecast * proportion
    forecast_location[loc+'_predicted'] = forecast_location['yhat'] * prop
    # available = capacity - predicted, minimum 0
    forecast_location[loc+'_available'] = forecast_location[loc+'_predicted'].apply(lambda x: max(capacity_per_location[loc]-x,0))
    # status
    forecast_location[loc+'_status'] = forecast_location[loc+'_available'].apply(
        lambda x: 'Full' if x==0 else 'Warning' if x<5 else 'Normal'
    )

forecast_location.to_csv("forecast/daily_forecast_location_compare_realistic.csv", index=False)
print("Daily forecast per location completed (realistic). CSV ready for dashboard.")