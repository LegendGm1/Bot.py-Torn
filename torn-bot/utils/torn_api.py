import os
import time

import aiohttp

BASE_URL = "https://api.torn.com"

# Torn asks developers to delete keys that are invalid, disabled or paused
BAD_KEY_CODES = {2, 13, 18}


class TornAPIError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


async def request(path: str, selections: str, key: str | None = None, fresh: bool = False) -> dict:
    """
    Call the Torn API and return the JSON as a dict.

    path       e.g. "user/12345" (someone else) or "user/" (the owner of the key)
    selections e.g. "profile" or "bars,cooldowns"
    key        a player's own key; if None, the bot's key from config.txt is used
    fresh      True skips Torn's 30-second cache (use it only when brand-new data really matters)

    Raises TornAPIError if Torn answers with an error.
    """
    params = {"selections": selections, "key": key or os.getenv("TORN_API_KEY")}
    if fresh:
        params["timestamp"] = int(time.time())  # a unique request, so the cache is not used

    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BASE_URL}/{path}", params=params) as resp:
            data = await resp.json(content_type=None)

    if "error" in data:
        error = data["error"]
        raise TornAPIError(error.get("code"), error.get("error"))

    return data


async def get_discord_link(lookup_id: int):
    """
    Ask Torn who is linked to this ID in its official Discord verification.

    lookup_id can be a Torn ID or a Discord ID.
    Returns (torn_id, discord_id) if the account is linked, otherwise None.
    """
    try:
        data = await request(f"user/{lookup_id}", "discord")
    except TornAPIError as e:
        if e.code == 6:  # incorrect ID, nobody found
            return None
        raise

    info = data.get("discord", {})
    discord_id = info.get("discordID")
    torn_id = info.get("userID")

    if not discord_id or not torn_id:  # empty = never verified with Torn
        return None

    return int(torn_id), int(discord_id)
