def get_hours_minutes_from_seconds(seconds: int) -> tuple[int, int]:
    """Transforms seconds into a hours and minutes tuple."""

    m, _ = divmod(seconds, 60)
    h, m = divmod(m, 60)

    return h, m
