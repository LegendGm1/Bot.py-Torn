"""Private messages, and the notice people get when their saved key stops working."""
import discord

from utils import storage, theme


async def send_dm(bot, discord_id: int, embed: discord.Embed):
    try:
        user = bot.get_user(discord_id) or await bot.fetch_user(discord_id)
        await user.send(embed=embed)
    except discord.HTTPException as e:  # includes Forbidden (their DMs are closed)
        print(f"Could not DM {discord_id}: {e}")


async def drop_bad_key(bot, discord_id: int, then: str):
    """Their key is invalid: delete it (which also removes their reminders) and tell them.

    `then` finishes the sentence "Use /setkey to save a new key, then ...".
    """
    storage.delete_key(discord_id)
    await send_dm(bot, discord_id, theme.error_embed(
        "Reminders cancelled",
        "Your saved API key is no longer valid, so I removed it and your reminders.\n"
        f"Use **/setkey** to save a new key, then {then}",
    ))
