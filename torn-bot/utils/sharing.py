"""
Who is currently letting others see their personal command results.

By default every personal command answers privately. When someone runs /view_yes they are
"sharing" for 5 minutes: during that time their results are posted where others can see them.
This lives in memory only, so a bot restart makes everybody private again (the safe default).
"""
import time

SHARE_SECONDS = 300  # 5 minutes

_until = {}  # discord_id -> unix time when sharing ends


def start(user_id: int) -> int:
    """Turn sharing on (or restart the timer). Returns the unix time it ends."""
    end = int(time.time()) + SHARE_SECONDS
    _until[user_id] = end
    return end


def is_active(user_id: int) -> bool:
    end = _until.get(user_id)
    if end is None:
        return False
    if time.time() >= end:
        del _until[user_id]  # the 5 minutes are over
        return False
    return True


def stop(user_id: int) -> bool:
    """Turn sharing off. Returns True if it was on."""
    was_active = is_active(user_id)
    _until.pop(user_id, None)
    return was_active


def ends_at(user_id: int):
    """Unix time sharing ends, or None if it is off."""
    return _until.get(user_id) if is_active(user_id) else None


def is_private(user_id: int) -> bool:
    return not is_active(user_id)


async def defer_reply(interaction):
    """
    Acknowledge a command and decide who will see the answer: private, unless the user is sharing.

    thinking=True matters: without it, a button click would ignore ephemeral and
    the answer would be posted publicly.
    """
    await interaction.response.defer(ephemeral=is_private(interaction.user.id), thinking=True)
