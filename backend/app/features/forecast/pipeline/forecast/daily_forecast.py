import pandas as pd
from prophet import Prophet
from statsmodels.tsa.arima.model import ARIMA


# Load Dataset
df = pd.read_csv("dataset/ParkingRecord_Preprocessed.csv")
df['TIME_SCAN'] = pd.to_datetime(df['TIME_SCAN'])

# Daily Aggregation
daily_df = df.groupby(['date','member_category','vehicle_type']).size().reset_index(name='count')
daily_df['date'] = pd.to_datetime(daily_df['date'])

# Total vehicles per day (for ARIMA)
daily_total = df.groupby('date').size()

# Prophet Forecast
# Aggregate total vehicles per day
prophet_df = daily_total.reset_index().rename(columns={'date':'ds', 0:'y'})
prophet_model = Prophet(daily_seasonality=True, weekly_seasonality=True)
prophet_model.fit(prophet_df)

future = prophet_model.make_future_dataframe(periods=30)  # forecast for the next 30 days
forecast = prophet_model.predict(future)

# Save Prophet results
forecast[['ds','yhat','yhat_lower','yhat_upper']].to_csv("forecast/daily_forecast_prophet.csv", index=False)

# ARIMA Forecast
arima_model = ARIMA(daily_total, order=(5,1,0))
arima_fit = arima_model.fit()
forecast_arima = arima_fit.forecast(30)

# Save ARIMA results
forecast_arima.to_csv("forecast/daily_forecast_arima.csv")

# Forecast per Location
# Historical proportion assumptions of location EDA
location_prop = {
    "P1W": 0.15, "P1E":0.15,
    "P2W":0.15, "P2E":0.10,
    "P3W":0.25, "P3E":0.20
}

# Assumed location capacity (total 300 slots)
capacity_per_location = {
    "P1W": 36, "P1E":36, "P2W":36, "P2E":24, "P3W":25, "P3E":20
}

# Allocate Prophet forecasts to locations
forecast_location = forecast[['ds','yhat']].copy()
for loc, prop in location_prop.items():
    forecast_location[loc+'_predicted'] = forecast_location['yhat'] * prop
    forecast_location[loc+'_available'] = capacity_per_location[loc] - forecast_location[loc+'_predicted']
    forecast_location[loc+'_status'] = forecast_location[loc+'_available'].apply(
        lambda x: 'Full' if x<=0 else 'Warning' if x<5 else 'Normal'
    )

forecast_location.to_csv("forecast/daily_forecast_location.csv", index=False)

print("Daily forecast completed, including per location. CSV file ready for dashboard.")