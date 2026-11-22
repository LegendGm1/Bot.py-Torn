"""
Flying: get a DM when Xanax is restocked in Japan while you are landed there.

Torn's own API has no abroad shop stock. The numbers come from YATA, a community site whose
export (https://yata.yt/api/v1/travel/export/) needs no key and is filled by players' scripts.
One shared check runs for everybody; your own saved key is only used, right when a restock
happens, to see whether you are landed in Japan.
"""
import asyncio
import time

import aiohttp
import discord
from discord.ext import commands, tasks

from utils import storage, theme, torn_api, users

YATA_URL = "https://yata.yt/api/v1/travel/export/"  # exactly this URL: YATA caches it, extra parameters break that
JAPAN = "jap"
XANAX_ID = 206

POLL_SECONDS = 2          # how often we look at YATA (one shared check for everybody)
MAX_WAIT_SECONDS = 60     # when YATA fails we back off, up to this long between tries
RESTOCK_MIN_JUMP = 50     # a rise of at least this much counts as a restock...
ALERT_COOLDOWN = 300      # ...but never alert twice within this many seconds
FAR_FUTURE = 4102444800   # reminders with this "next check" are never picked up by the reminder loop

HEADERS = {"User-Agent": "Torn Discord bot (personal project)"}


def read_japan_xanax(data):
    """Returns (quantity, price, last_report_time) for Xanax in Japan, or None if YATA has no Japan data."""
    country = (data.get("stocks") or {}).get(JAPAN) if isinstance(data, dict) else None
    if not country:
        return None

    update = int(country.get("update") or 0)
    for item in country.get("stocks") or []:
        if str(item.get("id")) == str(XANAX_ID) or str(item.get("name", "")).lower() == "xanax":
            return int(item.get("quantity") or 0), int(item.get("cost") or 0), update

    return 0, 0, update  # YATA leaves out items that are sold out


def is_restock(previous: int, current: int) -> bool:
    return current > 0 and (previous == 0 or current >= previous + RESTOCK_MIN_JUMP)


def is_in_japan(basic: dict) -> bool:
    status = basic.get("status", {})
    return status.get("state") == "Abroad" and "japan" in (status.get("description") or "").lower()


class Flying(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session = None
        self.baseline = None   # (quantity, report time) of the last YATA report we looked at
        self.last_alert = 0
        self.failures = 0

    async def cog_load(self):
        self.session = aiohttp.ClientSession(headers=HEADERS, timeout=aiohttp.ClientTimeout(total=10))
        self.poll.start()

    async def cog_unload(self):
        self.poll.cancel()
        if self.session:
            await self.session.close()

    # ------------------------------------------------------------------
    # Watching YATA
    # ------------------------------------------------------------------

    async def fetch_stock(self) -> dict:
        async with self.session.get(YATA_URL) as resp:
            if resp.status != 200:
                raise RuntimeError(f"YATA answered HTTP {resp.status}")
            return await resp.json(content_type=None)

    @tasks.loop(seconds=POLL_SECONDS)
    async def poll(self):
        if not storage.reminders_of_kind("flying"):
            self.baseline = None  # nobody is watching, so leave YATA alone
            return

        try:
            info = read_japan_xanax(await self.fetch_stock())
        except Exception as e:
            self.failures += 1
            wait = min(MAX_WAIT_SECONDS, POLL_SECONDS * 2 ** self.failures)
            print(f"YATA check failed ({type(e).__name__}: {e}); trying again in {wait}s")
            self.poll.change_interval(seconds=wait)
            return

        if self.failures:
            self.failures = 0
            self.poll.change_interval(seconds=POLL_SECONDS)

        if info is None:
            return
        quantity, price, update = info

        if self.baseline is None:
            self.baseline = (quantity, update)  # first look: remember it, don't alert
            return

        previous_quantity, previous_update = self.baseline
        if update <= previous_update:
            return  # nobody has reported anything new since last time

        self.baseline = (quantity, update)
        if is_restock(previous_quantity, quantity) and time.time() - self.last_alert >= ALERT_COOLDOWN:
            self.last_alert = time.time()
            await self.alert(quantity, price, update)

    @poll.before_loop
    async def before_poll(self):
        await self.bot.wait_until_ready()

    # ------------------------------------------------------------------
    # Telling people
    # ------------------------------------------------------------------

    async def alert(self, quantity: int, price: int, update: int):
        embed = theme.success_embed(
            "💊 Xanax restocked in Japan!",
            f"**{theme.number(quantity)}** in stock at **${theme.number(price)}** each.",
            footer="Stock data comes from YATA, reported by players",
        )
        embed.add_field(name="🕒 Reported", value=f"<t:{update}:R>")
        embed.add_field(name="🛒 Shop", value="[Open Torn](https://www.torn.com/index.php)")

        subscribers = storage.reminders_of_kind("flying")
        await asyncio.gather(*(self.notify(r, embed) for r in subscribers), return_exceptions=True)

    async def notify(self, reminder: dict, embed: discord.Embed):
        """Message one person, but only if they are landed in Japan right now."""
        discord_id = reminder["discord_id"]
        key = storage.get_key(discord_id)
        if key is None:
            storage.remove_reminder(reminder)
            return

        note = None
        try:
            basic = await torn_api.request("user/", "basic", key=key, fresh=True)
            if not is_in_japan(basic):
                return  # restock happened, but they are not landed in Japan
        except torn_api.TornAPIError as e:
            if e.code in torn_api.BAD_KEY_CODES:
                storage.delete_key(discord_id)  # also removes their reminders
                await self.dm(discord_id, theme.error_embed(
                    "Reminders cancelled",
                    "Your saved API key is no longer valid, so I removed it and your reminders.\n"
                    "Use **/setkey** to save a new key, then set them again.",
                ))
                return
            note = "I couldn't check where you are, so I'm telling you just in case."
        except Exception:
            note = "I couldn't check where you are, so I'm telling you just in case."

        if note:
            embed = embed.copy()
            embed.set_footer(text=note)
        await self.dm(discord_id, embed)

    async def dm(self, discord_id: int, embed: discord.Embed):
        try:
            user = self.bot.get_user(discord_id) or await self.bot.fetch_user(discord_id)
            await user.send(embed=embed)
        except discord.HTTPException as e:  # includes Forbidden (their DMs are closed)
            print(f"Could not DM {discord_id}: {e}")

    # ------------------------------------------------------------------
    # Turning it on (called by /reminder with the "Flying" purpose)
    # ------------------------------------------------------------------

    async def enable(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)

        data = await users.fetch_with_user_key(interaction, "basic")  # also proves their key works
        if data is None:
            return

        lines = ["✈️💊 I'll message you when Xanax is **restocked in Japan** while you are landed there."]
        if is_in_japan(data):
            lines.append("🇯🇵 You're in Japan right now.")
        else:
            lines.append("📍 You're not in Japan yet. I'll only message you once you've landed there.")

        try:
            info = read_japan_xanax(await self.fetch_stock())
        except Exception:
            info = None
        if info:
            quantity, _, update = info
            lines.append(f"📦 YATA shows **{theme.number(quantity)}** Xanax in Japan right now (reported <t:{update}:R>).")
            if self.baseline is None:
                self.baseline = (quantity, update)
        else:
            lines.append("📦 I couldn't read YATA's Japan stock just now, but I'll keep trying.")
        lines.append("ℹ️ Stock comes from YATA, so it's only as fresh as the reports players send it.")

        reminder = {
            "discord_id": interaction.user.id,
            "kind": "flying",
            "due": 0,
            "next_check": FAR_FUTURE,  # the reminder loop never touches this one
            "fails": 0,
        }
        reminders = self.bot.get_cog("Reminders")
        await reminders.confirm_and_store(interaction, [reminder], lines)


async def setup(bot):
    await bot.add_cog(Flying(bot))
