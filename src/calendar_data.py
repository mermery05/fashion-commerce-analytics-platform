import holidays


def holiday_rows(country: str, start_year: int, end_year: int) -> list[dict]:
    h = holidays.country_holidays(country, years=range(start_year, end_year + 1))
    return [
        {"date": d.isoformat(), "holiday_name": name} for d, name in sorted(h.items())
    ]
