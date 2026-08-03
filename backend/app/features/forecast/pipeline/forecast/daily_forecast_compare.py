import pandas as pd
from prophet import Prophet
from statsmodels.tsa.arima.model import ARIMA
import matplotlib.pyplot as plt
from sklearn.metrics import mean_absolute_error, mean_squared_error
import numpy as np


# Load Dataset
df = pd.read_csv("dataset/ParkingRecord_Preprocessed.csv")
df['TIME_SCAN'] = pd.to_datetime(df['TIME_SCAN'])

# Total vehicles per day (for forecast)
daily_total = df.groupby('date').size()
daily_total.index = pd.to_datetime(daily_total.index)

# Prophet Forecast
prophet_df = daily_total.reset_index().rename(columns={'date':'ds', 0:'y'})
prophet_model = Prophet(daily_seasonality=True, weekly_seasonality=True)
prophet_model.fit(prophet_df)

future = prophet_model.make_future_dataframe(periods=30)
forecast_prophet = prophet_model.predict(future)

# ARIMA Forecast
# Create ARIMA with a date index so that the warning disappears
daily_total_arima = daily_total.copy()
daily_total_arima.index.freq = 'D'

arima_model = ARIMA(daily_total_arima, order=(5,1,0))
arima_fit = arima_model.fit()
forecast_arima = arima_fit.forecast(30)

# Compare Models
# Use only the same period for errors
actual = daily_total[-30:]  # take the last 30 days as the "ground truth" of the simulation
pred_prophet = forecast_prophet['yhat'][-30:]
pred_arima = forecast_arima[-30:]

mae_prophet = mean_absolute_error(actual, pred_prophet)
mae_arima = mean_absolute_error(actual, pred_arima)

rmse_prophet = np.sqrt(mean_squared_error(actual, pred_prophet))
rmse_arima = np.sqrt(mean_squared_error(actual, pred_arima))

print("=== Daily Forecast Model Comparison ===")
print(f"Prophet MAE: {mae_prophet:.2f}, RMSE: {rmse_prophet:.2f}")
print(f"ARIMA   MAE: {mae_arima:.2f}, RMSE: {rmse_arima:.2f}")

# Plot actual vs predicted
plt.figure(figsize=(12,5))
plt.plot(actual.index, actual.values, label='Actual')
plt.plot(pred_prophet.index, pred_prophet.values, label='Prophet Forecast')
plt.plot(pred_arima.index, pred_arima.values, label='ARIMA Forecast')
plt.title("Daily Forecast: Actual vs Prophet vs ARIMA")
plt.xlabel("Date")
plt.ylabel("Jumlah Kendaraan")
plt.legend()
plt.show()

# Forecast per Lokasi (Prophet)
location_prop = {
    "P1W": 0.15, "P1E":0.15,
    "P2W":0.15, "P2E":0.10,
    "P3W":0.25, "P3E":0.20
}
capacity_per_location = {
    "P1W": 36, "P1E":36, "P2W":36, "P2E":24, "P3W":25, "P3E":20
}

forecast_location = forecast_prophet[['ds','yhat']].copy()
for loc, prop in location_prop.items():
    forecast_location[loc+'_predicted'] = forecast_location['yhat'] * prop
    forecast_location[loc+'_available'] = forecast_location[loc+'_predicted'].apply(lambda x: max(capacity_per_location[loc]-x,0))
    forecast_location[loc+'_status'] = forecast_location[loc+'_available'].apply(
        lambda x: 'Full' if x==0 else 'Warning' if x<5 else 'Normal'
    )

forecast_location.to_csv("forecast/daily_forecast_location_compare.csv", index=False)

print("Daily forecast per location complete. CSV ready for dashboard.")