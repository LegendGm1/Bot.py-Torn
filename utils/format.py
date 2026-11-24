def format_duration(seconds, zero_text="Ready") -> str:
    """Turn seconds into text like '1d 3h 20m'."""
    seconds = int(seconds or 0)
    if seconds <= 0:
        return zero_text

    days, rest = divmod(seconds, 86400)
    hours, rest = divmod(rest, 3600)
    minutes, secs = divmod(rest, 60)

    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if not parts:
        parts.append(f"{secs}s")
    return " ".join(parts)


def profile_url(torn_id) -> str:
    return f"https://www.torn.com/profiles.php?XID={torn_id}"
