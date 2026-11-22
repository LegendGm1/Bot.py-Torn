import os
import time

import discord
from discord import app_commands
from discord.ext import commands

from personal.flying import read_japan_xanax
from utils import sharing, storage, theme, torn_api

# Torn IDs allowed to use superuser commands. Change them in config.txt:
# SUPERUSER_TORN_IDS=4000192,1234567
SUPERUSER_TORN_IDS = {
    int(x)
    for x in os.getenv("SUPERUSER_TORN_IDS", "4000192").replace(" ", "").split(",")
    if x
}

PERSONAL_COMMANDS = ["persenel", "view_yes", "view_no", "reminder", "ping", "verify", "check", "setkey", "removekey", "profile", "bars", "cooldowns", "stats"]

PASS, FAIL, SKIP = "✅", "❌", "⏭️"

# Fields each command reads from Torn's answer: field -> required sub-fields (or None)
PROFILE_FIELDS = {
    "name": None, "player_id": None, "level": None, "rank": None, "faction": None,
    "status": ["state", "description"],
    "last_action": ["relative"],
    "life": ["current", "maximum"],
}
BAR = ["current", "maximum", "fulltime"]
BARS_FIELDS = {"energy": BAR, "nerve": BAR, "happy": BAR, "life": BAR}
COOLDOWN_FIELDS = {"cooldowns": ["drug", "medical", "booster"]}
STATUS_FIELDS = {"status": ["state", "until"]}  # what the hospital/jail reminder reads
TRAVEL_FIELDS = {"travel": ["destination", "timestamp", "time_left"]}  # what the landing reminder reads
STATS_FIELDS = {"strength": None, "defense": None, "speed": None, "dexterity": None, "total": None}


def is_superuser():
    """Only people who verified with /verify AND whose Torn ID is in SUPERUSER_TORN_IDS."""
    async def predicate(interaction: discord.Interaction) -> bool:
        return storage.get_verified(interaction.user.id) in SUPERUSER_TORN_IDS
    return app_commands.check(predicate)


def find_missing(data: dict, fields: dict) -> list:
    missing = []
    for field, children in fields.items():
        if field not in data:
            missing.append(field)
            continue
        for child in children or []:
            if not isinstance(data[field], dict) or child not in data[field]:
                missing.append(f"{field}.{child}")
    return missing


# ---------- the individual tests: each returns (status, detail) ----------

async def test_loaded(bot):
    missing = [name for name in PERSONAL_COMMANDS if bot.tree.get_command(name) is None]
    if missing:
        return FAIL, "not loaded: " + ", ".join(missing)
    return PASS, f"all {len(PERSONAL_COMMANDS)} commands are loaded"


async def test_storage():
    storage._save()  # raises if data.json can't be written
    return PASS, "data.json can be written"


async def test_ping(bot):
    return PASS, f"latency {round(bot.latency * 1000)} ms"


async def test_link_by_discord_id(discord_id):
    link = await torn_api.get_discord_link(discord_id)
    if link is None:
        return FAIL, "Torn has no link for your Discord ID"
    torn_id, found_discord_id = link
    if found_discord_id != discord_id:
        return FAIL, "Torn returned a different Discord ID"
    return PASS, f"Discord ID -> Torn ID {torn_id}"


async def test_link_by_torn_id(torn_id, discord_id):
    link = await torn_api.get_discord_link(torn_id)
    if link is None:
        return FAIL, "Torn has no Discord link for this Torn ID"
    if link[1] != discord_id:
        return FAIL, "Torn ID is linked to a different Discord account"
    return PASS, "Torn ID -> Discord ID matches"


async def test_selection(path, selections, fields, key=None):
    try:
        data = await torn_api.request(path, selections, key=key)
    except torn_api.TornAPIError as e:
        return FAIL, f"Torn error {e.code}: {e.message}"
    missing = find_missing(data, fields)
    if missing:
        return FAIL, "missing fields: " + ", ".join(missing)
    return PASS, "all expected fields present"


async def test_sharing():
    test_id = 0  # a made-up user, so your real sharing setting is never touched
    sharing.start(test_id)
    if not sharing.is_active(test_id):
        return FAIL, "sharing did not turn on"
    sharing.stop(test_id)
    if sharing.is_active(test_id):
        return FAIL, "sharing did not turn off"
    return PASS, f"on and off both work ({sharing.SHARE_SECONDS // 60} minute timer)"


async def test_reminder_storage():
    test_id = 0  # a made-up user, so real reminders are never touched
    storage.add_reminder({"discord_id": test_id, "kind": "energy", "due": 4102444800, "next_check": 4102444800})
    found = storage.delete_user_reminders(test_id)
    if found != 1:
        return FAIL, f"expected to store and remove 1 reminder, got {found}"
    return PASS, "reminders can be stored and removed"


async def test_yata(bot):
    flying = bot.get_cog("Flying")
    if flying is None:
        return FAIL, "the Flying feature isn't loaded"
    info = read_japan_xanax(await flying.fetch_stock())
    if info is None:
        return FAIL, "YATA answered, but it has no Japan data"
    quantity, _, update = info
    age = max(0, int(time.time()) - update)
    return PASS, f"Japan Xanax: {quantity} in stock, last reported {age} s ago"


async def skipped(reason):
    return SKIP, reason


# ---------- the command ----------

class TestAll(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="testall", description="Superuser: test all the personal commands at once")
    @is_superuser()
    async def testall(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        discord_id = interaction.user.id
        torn_id = storage.get_verified(discord_id)  # the superuser check guarantees this exists
        key = storage.get_key(discord_id)

        results = []

        async def run(name, test):
            started = time.perf_counter()
            try:
                status, detail = await test
            except Exception as e:  # a crash inside a test is a failed test, not a crashed bot
                status, detail = FAIL, f"{type(e).__name__}: {e}"
            ms = round((time.perf_counter() - started) * 1000)
            results.append((status, name, detail, ms))

        no_key = "no API key saved, run /setkey first"

        await run("commands loaded", test_loaded(self.bot))
        await run("storage", test_storage())
        await run("/ping", test_ping(self.bot))
        await run("reminders: storage", test_reminder_storage())
        await run("reminders: travel fields (landing)", test_selection("user/", "travel", TRAVEL_FIELDS, key=key) if key else skipped(no_key))
        await run("reminders: status fields (hospital/jail)", test_selection("user/", "basic", STATUS_FIELDS, key=key) if key else skipped(no_key))
        await run("flying: YATA stock feed (Japan Xanax)", test_yata(self.bot))
        await run("/view_yes + /view_no", test_sharing())
        await run("/verify + /check (by Discord ID)", test_link_by_discord_id(discord_id))
        await run("/verify torn_id option", test_link_by_torn_id(torn_id, discord_id))
        await run("/profile", test_selection(f"user/{torn_id}", "profile", PROFILE_FIELDS))
        await run("/setkey", test_selection("user/", "basic", {"player_id": None, "name": None}, key=key) if key else skipped(no_key))
        await run("/bars", test_selection("user/", "bars", BARS_FIELDS, key=key) if key else skipped(no_key))
        await run("/cooldowns", test_selection("user/", "cooldowns", COOLDOWN_FIELDS, key=key) if key else skipped(no_key))
        await run("/stats", test_selection("user/", "battlestats", STATS_FIELDS, key=key) if key else skipped(no_key))
        await run("/removekey", skipped("not run, it would delete your key"))

        passed = sum(1 for r in results if r[0] == PASS)
        failed = sum(1 for r in results if r[0] == FAIL)
        skipped_count = sum(1 for r in results if r[0] == SKIP)

        lines = [f"{status} **{name}**\n└ {detail} · `{ms} ms`" for status, name, detail, ms in results]
        embed = theme.make_embed(
            "🧪 Personal commands test",
            "\n\n".join(lines),
            theme.ERROR if failed else theme.SUCCESS,
            footer=f"✅ {passed} passed • ❌ {failed} failed • ⏭️ {skipped_count} skipped",
        )
        await interaction.followup.send(embed=embed)

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            embed = theme.error_embed(
                "Superusers only",
                "This command is only for superusers.\nIf that's you, run **/verify** first so the bot knows your Torn ID.",
            )
        else:
            embed = theme.error_embed("Something went wrong", str(error))
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(TestAll(bot))
