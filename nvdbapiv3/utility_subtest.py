# -*- coding: utf-8 -*-
"""
Created on Mon May 19 11:52:21 2025

@author: havfyh
"""

import pandas as pd
import requests

def fetch_weather(lat, lon, altitude=0):
    url = f"https://api.met.no/weatherapi/locationforecast/2.0/compact?lat={lat}&lon={lon}&altitude={altitude}"
    
    headers = {
        "User-Agent": "sedfh" 
    }

    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()
    
    # Flatten time series
    timeseries = data['properties']['timeseries']
    records = []
    for item in timeseries:
        time = item['time']
        details = item['data']['instant']['details']
        details['time'] = time
        records.append(details)
    
    df = pd.DataFrame(records)
    with open(r"C:\python\nvdbapi-V3-master\nvdbapiv3\weather.txt", "w") as file:
        file.write(str(df))
    return df



fetch_weather(60, 10)