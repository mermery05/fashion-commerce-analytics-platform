from unittest.mock import MagicMock, patch

from src.weather import fetch_daily_weather


def test_fetch_daily_weather_parses_response():
    fake = MagicMock(status_code=200)
    fake.json.return_value = {
        "daily": {
            "time": ["2022-01-01"],
            "temperature_2m_mean": [27.5],
            "precipitation_sum": [3.2],
        }
    }
    with patch("src.weather.requests.get", return_value=fake):
        out = fetch_daily_weather(-6.2, 106.8, "2022-01-01", "2022-01-01")
    assert out == [{"date": "2022-01-01", "temp_mean_c": 27.5, "precip_mm": 3.2}]
