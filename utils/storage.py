import json
import os
from datetime import datetime, timezone

DATA_FILE = "data.json"

# Everything lives in this dict while the bot runs; every change is also saved to data.json
_data = {"verified_users": {}, "api_keys": {}, "reminders": []}


def _now():
    return datetime.now(timezone.utc).isoformat()


def save():
    """Save everything. Also used after changing a stored item in place (for example a reminder's timer)."""
    # Write to a temp file first, then swap it in, so a crash can't leave half a file
    tmp_file = DATA_FILE + ".tmp"
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(_data, f, indent=2)
    os.replace(tmp_file, DATA_FILE)


_save = save  # the short name the rest of this file (and /testall) uses


def init():
    """Load data.json if it exists (it is created on the first save)."""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, encoding="utf-8") as f:
            loaded = json.load(f)
        _data["verified_users"] = loaded.get("verified_users", {})
        _data["api_keys"] = loaded.get("api_keys", {})
        _data["reminders"] = loaded.get("reminders", [])


# ---------- verified users ----------
# JSON object keys must be text, so Discord IDs are stored as str(discord_id)

def save_verified(discord_id: int, torn_id: int):
    _data["verified_users"][str(discord_id)] = {"torn_id": torn_id, "verified_at": _now()}
    _save()


def get_verified(discord_id: int):
    entry = _data["verified_users"].get(str(discord_id))
    return entry["torn_id"] if entry else None


# ---------- API keys ----------

def save_key(discord_id: int, torn_id: int, api_key: str):
    _data["api_keys"][str(discord_id)] = {
        "torn_id": torn_id,
        "api_key": api_key,
        "saved_at": _now(),
    }
    _save()


def get_key(discord_id: int):
    entry = _data["api_keys"].get(str(discord_id))
    return entry["api_key"] if entry else None


def delete_key(discord_id: int) -> bool:
    """Delete a saved key. Reminders need the key to work, so they are removed as well."""
    removed = _data["api_keys"].pop(str(discord_id), None)
    cancelled = _drop_reminders(discord_id)
    if removed is not None or cancelled:
        _save()
    return removed is not None


# ---------- reminders ----------
# A reminder is a small dict: {"discord_id", "kind", "due", "next_check", ...extra details}

def _drop_reminders(discord_id: int, kind=None) -> int:
    before = len(_data["reminders"])
    _data["reminders"] = [
        r for r in _data["reminders"]
        if not (r["discord_id"] == discord_id and (kind is None or r["kind"] == kind))
    ]
    return before - len(_data["reminders"])


def add_reminder(reminder: dict):
    """Add a reminder, replacing an older one of the same kind for the same person."""
    _drop_reminders(reminder["discord_id"], reminder["kind"])
    _data["reminders"].append(reminder)
    _save()


def reminders_of(discord_id: int) -> list:
    return [r for r in _data["reminders"] if r["discord_id"] == discord_id]


def reminders_of_kind(kind: str) -> list:
    return [r for r in _data["reminders"] if r["kind"] == kind]


def due_reminders(current_time: int) -> list:
    return [r for r in _data["reminders"] if r["next_check"] <= current_time]


def remove_reminder(reminder: dict) -> bool:
    """Remove one specific reminder. Returns False if it was already gone (for example cancelled)."""
    for i, r in enumerate(_data["reminders"]):
        if r is reminder:
            del _data["reminders"][i]
            _save()
            return True
    return False


def delete_user_reminders(discord_id: int, kind=None) -> int:
    """Cancel a person's reminders (all of them, or just one kind). Returns how many were removed."""
    count = _drop_reminders(discord_id, kind)
    if count:
        _save()
    return count
