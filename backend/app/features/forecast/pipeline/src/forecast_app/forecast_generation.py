import os

import pandas as pd
import numpy as np
from prophet import Prophet
from statsmodels.tsa.arima.model import ARIMA


def get_root_path():
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def generate_forecasts(start_date='2026-06-01', end_date='2026-12-31', dataset_path=None, forecast_folder=None):
    root_path = get_root_path()

    if dataset_path is None:
        dataset_path = os.path.join(root_path, 'dataset', 'ParkingRecord_Preprocessed.csv')

    if not os.path.exists(dataset_path):
        raise FileNotFoundError(f"File CSV historis tidak ditemukan: {dataset_path}")

    df_raw = pd.read_csv(dataset_path)
    df_raw['date'] = pd.to_datetime(df_raw['date'])
    df = df_raw.groupby('date').size().reset_index(name='total_vehicles')
    df.rename(columns={'date': 'ds', 'total_vehicles': 'y'}, inplace=True)

    forecast_days = (pd.to_datetime(end_date) - pd.to_datetime(start_date)).days + 1

    prophet_model = Prophet(yearly_seasonality=True, weekly_seasonality=True)
    prophet_model.fit(df)

    future = prophet_model.make_future_dataframe(periods=forecast_days)
    future = future[future['ds'] >= start_date]
    prophet_forecast = prophet_model.predict(future)[['ds', 'yhat']].rename(columns={'yhat': 'prophet_yhat'})

    y_series = df['y'].values
    arima_model = ARIMA(y_series, order=(5, 1, 0))
    arima_fit = arima_model.fit()
    arima_values = arima_fit.forecast(steps=forecast_days)
    arima_dates = pd.date_range(start=start_date, periods=forecast_days)
    arima_forecast = pd.DataFrame({'ds': arima_dates, 'arima_yhat': arima_values})

    combined = pd.merge(prophet_forecast, arima_forecast, on='ds')
    last_observed = df['y'].iloc[-1]
    combined['best_model'] = np.where(
        abs(combined['prophet_yhat'] - last_observed) < abs(combined['arima_yhat'] - last_observed),
        'Prophet',
        'ARIMA',
    )
    combined['yhat_best'] = np.where(
        combined['best_model'] == 'Prophet',
        combined['prophet_yhat'],
        combined['arima_yhat'],
    )

    MAX_SLOT = 300

    def generate_slots(row):
        slots = {}
        for key in ['P1W', 'P1E', 'P2W', 'P2E', 'P3W', 'P3E']:
            predicted = row['yhat_best'] * np.random.uniform(0.15, 0.35)
            available = max(0, int(MAX_SLOT - predicted))
            if available == 0:
                status = 'Full'
            elif available < MAX_SLOT * 0.2:
                status = 'Warning'
            else:
                status = 'Normal'
            slots[f'{key}_predicted'] = round(predicted, 2)
            slots[f'{key}_available'] = available
            slots[f'{key}_status'] = status
        slots['total_vehicles'] = round(row['yhat_best'], 2)
        return pd.Series(slots)

    forecast_df = combined.join(combined.apply(generate_slots, axis=1))

    forecast_folder = forecast_folder or os.path.join(root_path, 'forecast')
    os.makedirs(forecast_folder, exist_ok=True)

    daily_path = os.path.join(forecast_folder, 'daily_forecast.csv')
    forecast_df.to_csv(daily_path, index=False)

    forecast_df['year'] = forecast_df['ds'].dt.year
    forecast_df['week'] = forecast_df['ds'].dt.isocalendar().week
    weekly_df = forecast_df.groupby(['year', 'week']).sum(numeric_only=True).reset_index()
    weekly_df[['P1W_status', 'P1E_status', 'P2W_status', 'P2E_status', 'P3W_status', 'P3E_status']] = 'Normal'
    weekly_path = os.path.join(forecast_folder, 'weekly_forecast.csv')
    weekly_df.to_csv(weekly_path, index=False)

    forecast_df['month'] = forecast_df['ds'].dt.month
    monthly_df = forecast_df.groupby(['year', 'month']).sum(numeric_only=True).reset_index()
    monthly_df[['P1W_status', 'P1E_status', 'P2W_status', 'P2E_status', 'P3W_status', 'P3E_status']] = 'Normal'
    monthly_path = os.path.join(forecast_folder, 'monthly_forecast.csv')
    monthly_df.to_csv(monthly_path, index=False)

    print("Daily forecast saved to:", daily_path)
    print("Weekly forecast saved to:", weekly_path)
    print("Monthly forecast saved to:", monthly_path)
    print("Forecasting complete! Daily, Weekly, Monthly ready.")

    return forecast_df, weekly_df, monthly_df


if __name__ == '__main__':
    generate_forecasts()
