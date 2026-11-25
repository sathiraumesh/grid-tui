"""How numbers read on screen: sizes, speeds, flags and durations."""


def size(num_bytes: float) -> str:
    """A size in bytes, for a person: 96 GiB → '96 GiB', 2 TiB → '2 TiB'.

    0 or less is '', so an unknown size leaves its cell empty.
    """
    if num_bytes <= 0:
        return ''
    for unit, factor in (('TiB', 1024**4), ('GiB', 1024**3), ('MiB', 1024**2)):
        if num_bytes >= factor:
            return f'{num_bytes / factor:.3g} {unit}'
    if num_bytes >= 1024:
        return f'{num_bytes / 1024:.3g} KiB'
    return f'{num_bytes:g} B'


def number(value: float) -> str:
    """A number for a cell: '' for 0, so unknown values stay empty."""
    return f'{value:g}' if value else ''


def yes_no(flag: bool) -> str:
    """A flag for a person: 'yes' or 'no'."""
    return 'yes' if flag else 'no'


def duration(seconds: int) -> str:
    """A length of time, e.g. 7200 → '2 h', 5400 → '1 h 30 min'; 0 → ''."""
    if seconds <= 0:
        return ''
    hours, rest = divmod(int(seconds), 3600)
    minutes = rest // 60
    parts = []
    if hours:
        parts.append(f'{hours} h')
    if minutes:
        parts.append(f'{minutes} min')
    return ' '.join(parts) or f'{seconds} s'


def interval(milliseconds: float) -> str:
    """How often, for a person: 20 → '20 ms', 1000 → '1 s', 60000 → '1 min'."""
    if milliseconds <= 0:
        return ''
    if milliseconds < 1000:
        return f'{milliseconds:g} ms'
    seconds = milliseconds / 1000
    if seconds < 60:
        return f'{seconds:g} s'
    return f'{seconds / 60:g} min'
