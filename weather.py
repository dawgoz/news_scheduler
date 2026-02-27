import requests

from config import INCLUDE_WEATHER


def get_vilnius_weather_summary() -> str | None:
    """
    Returns short LT text like: "Vilnius: dabar 2°C, vėjas 4 m/s, šiandien 0…4°C."
    Graceful failure: returns None if API fails.
    """
    if not INCLUDE_WEATHER:
        return None
    try:
        # Vilnius coords
        lat, lon = 54.6872, 25.2797
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            "&current=temperature_2m,wind_speed_10m"
            "&daily=temperature_2m_max,temperature_2m_min"
            "&timezone=Europe%2FVilnius"
        )
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        data = r.json()

        cur = data.get("current", {})
        daily = data.get("daily", {})
        t_now = cur.get("temperature_2m")
        w_now = cur.get("wind_speed_10m")
        tmin = (daily.get("temperature_2m_min") or [None])[0]
        tmax = (daily.get("temperature_2m_max") or [None])[0]

        parts: list[str] = []
        if t_now is not None:
            parts.append(f"dabar {t_now}°C")
        if w_now is not None:
            parts.append(f"vėjas {w_now} m/s")
        if tmin is not None and tmax is not None:
            parts.append(f"šiandien {tmin}…{tmax}°C")

        if not parts:
            return None

        return "Vilnius: " + ", ".join(parts) + "."
    except Exception:
        return None

