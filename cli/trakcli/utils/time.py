def get_hours_minutes_from_seconds(seconds: int) -> tuple[int, int]:
    m, _ = divmod(seconds, 60)
    h, m = divmod(m, 60)

    return h, m
