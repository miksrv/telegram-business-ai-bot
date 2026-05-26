from datetime import datetime, time as dt_time, timezone, timedelta


def is_within_business_hours(
    hours_start: str | None,
    hours_end: str | None,
    tz_offset_minutes: int,
) -> bool:
    if not hours_start or not hours_end:
        return True  # no hours configured = always within business hours

    tz = timezone(timedelta(minutes=tz_offset_minutes))
    now = datetime.now(tz).time().replace(second=0, microsecond=0)

    try:
        sh, sm = hours_start.split(":")
        eh, em = hours_end.split(":")
        start = dt_time(int(sh), int(sm))
        end = dt_time(int(eh), int(em))
    except (ValueError, AttributeError):
        return True

    if start <= end:
        return start <= now <= end
    # Overnight span (e.g., 22:00 – 06:00)
    return now >= start or now <= end
