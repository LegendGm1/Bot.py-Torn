"""One place for how every bot message looks: colors, icons and small helpers."""
import discord

PRIMARY = discord.Color.from_rgb(88, 101, 242)   # blurple
SUCCESS = discord.Color.from_rgb(46, 204, 113)   # green
ERROR = discord.Color.from_rgb(231, 76, 60)      # red
WARNING = discord.Color.from_rgb(241, 196, 15)   # yellow
INFO = discord.Color.from_rgb(52, 152, 219)      # blue
MUTED = discord.Color.from_rgb(127, 140, 141)    # grey

FOOTER_TEXT = "Torn Bot"


def make_embed(title, description=None, color=PRIMARY, *, url=None, footer=None) -> discord.Embed:
    """The base for every message: same footer, same timestamp, same look."""
    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        url=url,
        timestamp=discord.utils.utcnow(),
    )
    embed.set_footer(text=footer or FOOTER_TEXT)
    return embed


def success_embed(title, description=None, **kwargs) -> discord.Embed:
    return make_embed(f"✅ {title}", description, SUCCESS, **kwargs)


def error_embed(title, description=None, **kwargs) -> discord.Embed:
    return make_embed(f"❌ {title}", description, ERROR, **kwargs)


def warning_embed(title, description=None, **kwargs) -> discord.Embed:
    return make_embed(f"⚠️ {title}", description, WARNING, **kwargs)


def api_error_embed(code, message) -> discord.Embed:
    return error_embed(
        "Torn API error",
        message or "Something went wrong talking to Torn.",
        footer=f"{FOOTER_TEXT} • error code {code}",
    )


def ratio(current, maximum) -> float:
    """current / maximum as a number from 0 to 1 (0 if it can't be worked out)."""
    try:
        return max(0.0, min(1.0, float(current) / float(maximum)))
    except (TypeError, ValueError, ZeroDivisionError):
        return 0.0


def progress_bar(current, maximum, length=10) -> str:
    filled = round(ratio(current, maximum) * length)
    return "▰" * filled + "▱" * (length - filled)


def percent(current, maximum) -> int:
    return round(ratio(current, maximum) * 100)


def number(value) -> str:
    """1234567 -> '1,234,567' (leaves anything else alone)."""
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return str(value)
