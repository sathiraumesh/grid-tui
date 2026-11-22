"""How times read on screen, shared by the screens and widgets."""

from __future__ import annotations

from datetime import datetime, timedelta


def clock(t: datetime, now: datetime) -> str:
    """t as "15:04", with the day when it isn't now's day: "Mon 23 09:00"."""
    if t.date() == now.date():
        return t.strftime("%H:%M")
    return t.strftime("%a %d %H:%M")


def duration(d: timedelta) -> str:
    """d as "3h", "1h30m", "45m", or "2d4h" from a day on."""
    minutes = round(d.total_seconds() / 60)
    h, m = divmod(minutes, 60)
    if h >= 24:
        days, h = divmod(h, 24)
        return f"{days}d{h}h" if h else f"{days}d"
    if h and m:
        return f"{h}h{m}m"
    return f"{h}h" if h else f"{m}m"


def jobs(n: int) -> str:
    """ "1 job" or "3 jobs"."""
    return "1 job" if n == 1 else f"{n} jobs"
