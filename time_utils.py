from datetime import datetime, timezone, time as dtime

from config import LOCAL_TZ


def get_digest_type() -> str | None:
    """Return 'morning' at 07:xx, 'midday' at 12:xx Vilnius time, else None."""
    now = datetime.now(LOCAL_TZ)
    if now.hour == 7:
        return "morning"
    if now.hour == 12:
        return "midday"
    if now.hour == 18:
        return "evening"
    return None


def get_time_window_local(digest_type: str) -> tuple[datetime, datetime]:
    """
    Morning: today 00:00 -> now
    Midday:  today 07:00 -> now  (so it's 'only NEW since morning')
    Evening: today 18:00 -> now  (so it's 'only NEW since midday')
    """
    now = datetime.now(LOCAL_TZ)
    start_of_day = datetime.combine(now.date(), dtime(0, 0), tzinfo=LOCAL_TZ)
    if digest_type == "midday":
        start = datetime.combine(now.date(), dtime(7, 0), tzinfo=LOCAL_TZ)
    elif digest_type == "evening":
        start = datetime.combine(now.date(), dtime(17, 0), tzinfo=LOCAL_TZ)
    else:
        start = start_of_day
    return start, now


def titles_and_subject(date_str: str, digest_type: str) -> tuple[str, str, str]:
    """
    Returns (email_subject, html_title, header_title)
    """
    if digest_type == "morning":
        subject = f"[Ryto santrauka] LRT naujienos — {date_str}"
        header = f"LRT ryto naujienų santrauka — {date_str}"
        subtitle = "Svarbiausios šios dienos naujienos (nuo 00:00)."
    else:
        subject = f"[Vidurdienio atnaujinimas] LRT naujienos — {date_str}"
        header = f"LRT vidurdienio naujienų atnaujinimas — {date_str}"
        subtitle = "Naujos naujienos nuo 07:00 (ryto santraukos)."
    return subject, header, subtitle


def to_local_dt(struct_time_obj) -> datetime | None:
    """Convert feedparser struct_time (assumed UTC) to local datetime."""
    if struct_time_obj is None:
        return None
    dt_utc = datetime(*struct_time_obj[:6], tzinfo=timezone.utc)
    return dt_utc.astimezone(LOCAL_TZ)

