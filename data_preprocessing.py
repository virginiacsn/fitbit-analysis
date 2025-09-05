
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


def process_azm_data(azm_data):
    df_azm = pd.json_normalize(azm_data)
    df_azm = df_azm.rename(columns={
        "value.activeZoneMinutes": "active_zm",
        "value.fatBurnActiveZoneMinutes": "fat_burn_zm",
        "value.cardioActiveZoneMinutes": "cardio_zm"
    })
    cols = ["active_zm", "fat_burn_zm", "cardio_zm"]
    df_azm[cols] = df_azm[cols].fillna(0).astype(int)
    df_azm["activity_level"] = df_azm.apply(get_activity_level, axis=1)
    df_azm["activity_level"] = pd.Categorical(df_azm["activity_level"], categories=[
        "none", "light", "moderate", "high"], ordered=True)
    return df_azm

def sleep_into_timeseries(sleep):
    timeseries = []
    for date_entry in sleep:
        if date_entry["isMainSleep"]:
            for entry in date_entry["levels"]["data"]:
                timeseries.append({
                    "date": date_entry["dateOfSleep"],
                    "time": entry["dateTime"].split("T")[1][:-4],
                    "value": entry["level"]
                })
    return timeseries

def process_sleep_data(sleep_data):
    sleep_ts = sleep_into_timeseries(sleep_data)
    df_sleep_ts = pd.DataFrame(sleep_ts)
    last_rows = df_sleep_ts.groupby("date").tail(1).copy()
    last_rows["time"] = last_rows["time"].apply(
        lambda t: (datetime.strptime(t, "%H:%M:%S") + timedelta(minutes=5)).strftime("%H:%M:%S")
    )
    last_rows["value"] = "Wake"
    df_sleep_ts = pd.concat([df_sleep_ts, last_rows], ignore_index=True)
    df_sleep_ts.rename(columns={"value": "sleep_stage"}, inplace=True)
    df_sleep_ts['datetime'] = pd.to_datetime(df_sleep_ts['date'] + ' ' + df_sleep_ts['time'])
    df_sleep_ts.set_index('datetime', inplace=True)
    df_sleep_ts = df_sleep_ts.resample('5min').ffill().reset_index()
    df_sleep_ts.dropna(inplace=True)
    df_sleep_ts['date'] = df_sleep_ts['datetime'].dt.strftime('%Y-%m-%d')
    df_sleep_ts['time'] = df_sleep_ts['datetime'].dt.strftime("%H:%M:%S") 
    df_sleep_ts.drop(columns=['datetime'], inplace=True)
    return df_sleep_ts

def get_activity_level(row):
    values = np.array([row["active_zm"], row["fat_burn_zm"], row["cardio_zm"]])
    if values[0] == 0:
        return "none"
    elif (values[1] > 0) & (values[1] < 3) & (values[2] == 0):
        return "light"
    elif (values[1] >= 3) & (values[2] == 0):
        return "moderate"
    elif (values[1] >= 0) & (values[2] > 0):
        return "high"

def time_of_day(hour):
    if 6 <= hour < 12:
        return 'morning'
    elif 12 <= hour < 17:
        return 'afternoon'
    elif 17 <= hour < 22:
        return 'evening'
    else:
        return 'night'
    
def get_datetime_params(df):
    cols_to_move =  df.columns.tolist()[2:]

    df['datetime_dt'] = pd.to_datetime(df['date'] + ' ' + df['time'], format="%Y-%m-%d %H:%M:%S")
    df['time_dt'] = df['datetime_dt'].dt.time

    df['time_float'] = df['datetime_dt'].dt.hour + df['datetime_dt'].dt.minute / 60
    df['time_float'] = df['time_float'].round(2)

    df['time'] = df['time'].str[:-3]

    df['month'] = df['datetime_dt'].dt.month_name().str[:3]
    df['day_of_week'] = df['datetime_dt'].dt.day_name().str[:3]
    df['day_of_month'] = df['datetime_dt'].dt.day

    df['time_of_day'] = df['datetime_dt'].dt.hour.apply(time_of_day)

    df['sleep_night'] = df['datetime_dt'].apply(lambda x: x.date() if x.hour >= 18 else (x - pd.Timedelta(days=1)).date())

    cols = [c for c in df.columns if c not in cols_to_move] + cols_to_move
    df = df[cols]
    return df

def merge_dataframes(df_steps, df_hr, df_azm, df_sleep):
    df = pd.merge(df_steps, df_hr, on=["date", "time"], how="outer", suffixes=("_steps", "_hr"))
    df = pd.merge(df, df_azm, on=["date", "time"], how="outer")
    df = pd.merge(df, df_sleep, on=["date", "time"], how="left")
    df.rename(columns={"value_steps": "steps", "value_hr": "heart_rate"}, inplace=True)
    df["heart_rate"] = df["heart_rate"].interpolate(method="linear")
    return df
