import time
import requests

URL = "https://archive-api.open-meteo.com/v1/archive"


def fetch_daily_weather(
    lat: float, lon: float, start: str, end: str, retries: int = 5
) -> list[dict]:
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start,
        "end_date": end,
        "daily": "temperature_2m_mean,precipitation_sum",
        "timezone": "UTC",
    }
    wait = 30
    for _ in range(retries):
        r = requests.get(URL, params=params, timeout=60)
        if r.status_code == 200:
            d = r.json()["daily"]
            return [
                {"date": t, "temp_mean_c": tm, "precip_mm": p}
                for t, tm, p in zip(
                    d["time"], d["temperature_2m_mean"], d["precipitation_sum"]
                )
            ]
        if r.status_code == 429:  # rate limited: wait longer each time
            time.sleep(wait)
            wait = min(wait * 2, 300)
            continue
        r.raise_for_status()
    raise RuntimeError(
        "Open-Meteo is still rate-limiting after retries; try again later"
    )
