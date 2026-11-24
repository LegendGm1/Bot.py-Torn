import asyncio
import time

import discord
from discord import app_commands
from discord.ext import commands, tasks

from utils import notify, storage, theme, torn_api, users

TICK_SECONDS = 5        # how often the bot looks for reminders that are due
POLL_SECONDS = 60       # hospital/jail: how often to check if someone released you early
RETRY_SECONDS = 60      # wait this long after a failed Torn check
MAX_FAILURES = 10       # give up after this many failed checks in a row

BARS = {"energy": ("⚡", "Energy"), "nerve": ("🔥", "Nerve")}

# What shows up in the "purpose" dropdown of /reminder
PURPOSES = [
    app_commands.Choice(name="⚡ Energy is full", value="energy"),
    app_commands.Choice(name="🔥 Nerve is full", value="nerve"),
    app_commands.Choice(name="⚡🔥 Energy and nerve are full", value="both"),
    app_commands.Choice(name="✈️ I'm about to land", value="landing"),
    app_commands.Choice(name="🏥 Hospital or jail time is over", value="release"),
    app_commands.Choice(name="✈️ Flying: Xanax restock in Japan", value="flying"),
    app_commands.Choice(name="📋 Show my reminders", value="list"),
    app_commands.Choice(name="🛑 Cancel all my reminders", value="cancel_all"),
]


def now() -> int:
    return int(time.time())


def kinds_for(purpose: str) -> list:
    """The reminder kinds behind a purpose ("both" means energy and nerve)."""
    return ["energy", "nerve"] if purpose == "both" else [purpose]


def make_reminder(discord_id: int, kind: str, due: int, **extra) -> dict:
    reminder = {"discord_id": discord_id, "kind": kind, "due": due, "next_check": due, "fails": 0}
    reminder.update(extra)
    return reminder


class Reminders(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ------------------------------------------------------------------
    # The background loop
    # ------------------------------------------------------------------

    async def cog_load(self):
        self.check_reminders.start()

    async def cog_unload(self):
        self.check_reminders.cancel()

    @tasks.loop(seconds=TICK_SECONDS)
    async def check_reminders(self):
        due = storage.due_reminders(now())
        if due:
            # Everything that is due runs at the same time, so one slow Torn answer doesn't hold up the rest
            await asyncio.gather(*(self.run_one(reminder) for reminder in due))

    async def run_one(self, reminder: dict):
        try:
            await self.process(reminder)
        except Exception as e:  # one broken reminder must never stop the loop
            print(f"Reminder error ({reminder.get('kind')}): {type(e).__name__}: {e}")
            reminder["next_check"] = now() + RETRY_SECONDS

    @check_reminders.before_loop
    async def before_check_reminders(self):
        await self.bot.wait_until_ready()

    async def process(self, reminder: dict):
        if storage.get_key(reminder["discord_id"]) is None:
            storage.remove_reminder(reminder)  # the key is gone, so the reminder can't work
            return

        kind = reminder["kind"]
        if kind in BARS:
            await self.process_bar(reminder)
        elif kind == "landing":
            await self.process_landing(reminder)
        elif kind == "release":
            await self.process_release(reminder)
        else:
            storage.remove_reminder(reminder)

    # ---------- energy / nerve ----------

    async def process_bar(self, r: dict):
        data = await self.fetch(r, "bars")
        if data is None:
            return

        kind = r["kind"]
        icon, label = BARS[kind]
        info = data.get(kind, {})
        seconds = int(info.get("fulltime") or 0)

        if seconds <= 0:
            await self.notify(r, theme.success_embed(
                f"{icon} {label} is full!",
                f"Your {label.lower()} is at **{info.get('current', '?')}/{info.get('maximum', '?')}**. Time to use it!",
            ))
        else:
            # You used some in the meantime, so wait for the new full time
            r["due"] = now() + seconds
            r["next_check"] = r["due"]
            storage.save()

    # ---------- landing ----------

    async def process_landing(self, r: dict):
        until = r["until"]
        label = r.get("label", "your flight")
        if now() >= until:
            embed = theme.success_embed("✈️ You've landed!", f"{label} has arrived.")
        else:
            embed = theme.make_embed("✈️ About to land!", f"{label} lands <t:{until}:R>.", theme.INFO)
        await self.notify(r, embed)

    # ---------- hospital / jail ----------

    async def process_release(self, r: dict):
        data = await self.fetch(r, "basic")
        if data is None:
            return

        status = data.get("status", {})
        state = status.get("state")
        until = int(status.get("until") or 0)

        if state in ("Hospital", "Jail"):
            # Still inside: check again soon, in case someone revives, busts or bails you out
            r["state"] = state
            r["due"] = until
            wait = POLL_SECONDS
            if until > now():
                wait = min(wait, until - now() + 1)
            r["next_check"] = now() + max(wait, 2)
            storage.save()
            return

        was_jail = r.get("state") == "Jail"
        early = r.get("due", 0) - now() > 30  # out well before the timer said
        if was_jail:
            title = "🔒 You're out of jail!"
            text = ("You were released early, someone probably **busted** or **bailed** you out."
                    if early else "Your jail time is over.")
        else:
            title = "🏥 You're out of the hospital!"
            text = ("You were released early, someone probably **revived** you."
                    if early else "Your hospital time is over.")
        await self.notify(r, theme.success_embed(title, text))

    # ---------- helpers for the loop ----------

    async def fetch(self, r: dict, selections: str):
        """Ask Torn using the person's key. Returns the data, or None if the reminder was rescheduled or dropped."""
        key = storage.get_key(r["discord_id"])
        try:
            data = await torn_api.request("user/", selections, key=key)
        except torn_api.TornAPIError as e:
            if e.code in torn_api.BAD_KEY_CODES:
                await notify.drop_bad_key(self.bot, r["discord_id"], "set your reminders again.")
                return None
            await self.failed(r, f"Torn error {e.code}: {e.message}")
            return None
        except Exception as e:  # network trouble and so on
            await self.failed(r, f"{type(e).__name__}")
            return None

        r["fails"] = 0
        return data

    async def failed(self, r: dict, why: str):
        r["fails"] = r.get("fails", 0) + 1
        if r["fails"] >= MAX_FAILURES:
            if storage.remove_reminder(r):
                await notify.send_dm(self.bot, r["discord_id"], theme.error_embed(
                    "Reminder cancelled",
                    f"I couldn't reach Torn {MAX_FAILURES} times in a row ({why}), so I cancelled it. Please set it again.",
                ))
        else:
            r["next_check"] = now() + RETRY_SECONDS
            storage.save()

    async def notify(self, r: dict, embed: discord.Embed):
        # Remove first: if it was cancelled while we were busy, remove_reminder says so and we stay quiet
        if storage.remove_reminder(r):
            await notify.send_dm(self.bot, r["discord_id"], embed)

    # ------------------------------------------------------------------
    # The commands
    # ------------------------------------------------------------------

    async def confirm_and_store(self, interaction: discord.Interaction, reminders: list, lines: list):
        """In a server, first make sure we can really DM this person, then save the reminders."""
        embed = theme.success_embed(
            "Reminder set",
            "\n".join(lines),
            footer="Cancel any time with /reminder",
        )

        if interaction.guild is not None:
            try:
                await interaction.user.send(embed=embed)
            except discord.HTTPException:
                await interaction.followup.send(
                    embed=theme.error_embed(
                        "I can't DM you",
                        "Reminders are sent as private messages, but your DMs are closed to me.\n\n"
                        "Open the server menu, go to **Privacy Settings**, turn on "
                        "**Direct Messages**, then run the command again.",
                    ),
                    ephemeral=True,
                )
                return
            embed.set_footer(text="I also sent this to your DMs • Cancel any time with /reminder")

        for reminder in reminders:
            storage.add_reminder(reminder)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(
        name="reminder",
        description="Set a private DM reminder: energy/nerve full, about to land, or hospital/jail over",
    )
    @app_commands.describe(
        purpose="What should I remind you about?",
        seconds_before="Landing only: how many seconds before landing I message you (default 60)",
        cancel="Cancel this reminder instead of setting it",
    )
    @app_commands.choices(purpose=PURPOSES)
    async def reminder(
        self,
        interaction: discord.Interaction,
        purpose: app_commands.Choice[str],
        seconds_before: app_commands.Range[int, 0, 600] = 60,
        cancel: bool = False,
    ):
        value = purpose.value

        if value == "list":
            await self.show_list(interaction)
        elif value == "cancel_all":
            await self.cancel(interaction, None)
        elif cancel:
            await self.cancel(interaction, value)
        elif value in ("energy", "nerve", "both"):
            await self.set_bars(interaction, value)
        elif value == "landing":
            await self.set_landing(interaction, seconds_before)
        elif value == "flying":
            await self.set_flying(interaction)
        else:
            await self.set_release(interaction)

    # ---------- setting reminders ----------

    async def set_bars(self, interaction: discord.Interaction, bar: str):
        # Reminders are always private, whatever the sharing setting is
        await interaction.response.defer(ephemeral=True, thinking=True)

        data = await users.fetch_with_user_key(interaction, "bars")
        if data is None:
            return

        reminders, lines = [], []
        for kind in kinds_for(bar):
            icon, label = BARS[kind]
            seconds = int(data.get(kind, {}).get("fulltime") or 0)
            if seconds <= 0:
                lines.append(f"{icon} **{label}** is already full, so no reminder is needed.")
                continue
            due = now() + seconds
            reminders.append(make_reminder(interaction.user.id, kind, due))
            lines.append(f"{icon} **{label}** will be full <t:{due}:R>.")

        if not reminders:
            await interaction.followup.send(
                embed=theme.make_embed("ℹ️ Already full", "\n".join(lines), theme.INFO), ephemeral=True
            )
            return

        await self.confirm_and_store(interaction, reminders, lines)

    async def set_landing(self, interaction: discord.Interaction, seconds_before: int):
        await interaction.response.defer(ephemeral=True, thinking=True)

        # Torn has a separate "travel" selection that holds the landing time
        data = await users.fetch_with_user_key(interaction, "travel")
        if data is None:
            return

        travel = data.get("travel", {})
        arrival = int(travel.get("timestamp") or 0)
        time_left = int(travel.get("time_left") or 0)
        if arrival <= now() and time_left > 0:
            arrival = now() + time_left  # no usable timestamp, so work it out from the time left

        if arrival <= now():
            await interaction.followup.send(
                embed=theme.make_embed("ℹ️ Not traveling", "You aren't on a flight right now.", theme.INFO),
                ephemeral=True,
            )
            return

        destination = travel.get("destination") or "somewhere"
        label = "Your flight back to Torn" if destination == "Torn" else f"Your flight to {destination}"
        due = max(arrival - seconds_before, now() + 1)
        reminder = make_reminder(interaction.user.id, "landing", due, until=arrival, label=label)
        line = f"✈️ **{label}** lands <t:{arrival}:R>. I'll message you about {seconds_before} seconds before."
        await self.confirm_and_store(interaction, [reminder], [line])

    async def set_flying(self, interaction: discord.Interaction):
        # The feature itself lives in personal/flying.py
        flying = self.bot.get_cog("Flying")
        if flying is None:
            await interaction.response.send_message(
                embed=theme.warning_embed("Not available", "The flying feature isn't loaded on this bot."),
                ephemeral=True,
            )
            return
        await flying.enable(interaction)

    async def set_release(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)

        data = await users.fetch_with_user_key(interaction, "basic")
        if data is None:
            return

        status = data.get("status", {})
        state = status.get("state")
        until = int(status.get("until") or 0)
        if state not in ("Hospital", "Jail"):
            await interaction.followup.send(
                embed=theme.make_embed("ℹ️ You're free", "You aren't in the hospital or jail right now.", theme.INFO),
                ephemeral=True,
            )
            return

        icon = "🏥" if state == "Hospital" else "🔒"
        wait = min(POLL_SECONDS, max(until - now() + 1, 2))
        reminder = make_reminder(interaction.user.id, "release", until, state=state)
        reminder["next_check"] = now() + wait
        line = (
            f"{icon} You're in the **{state.lower()}** until <t:{until}:R>.\n"
            "I check every minute, so you'll hear right away if someone revives, busts or bails you out."
        )
        await self.confirm_and_store(interaction, [reminder], [line])

    # ---------- cancelling and listing ----------

    async def cancel(self, interaction: discord.Interaction, which):
        """which: None for everything, or "energy", "nerve", "both", "landing", "release"."""
        if which is None:
            count = storage.delete_user_reminders(interaction.user.id)
        else:
            count = sum(storage.delete_user_reminders(interaction.user.id, kind) for kind in kinds_for(which))

        if count:
            embed = theme.success_embed(
                "Reminders cancelled", f"Cancelled **{count}** reminder{'s' if count != 1 else ''}."
            )
        else:
            embed = theme.make_embed("ℹ️ Nothing to cancel", "You have no matching reminders.", theme.INFO)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def show_list(self, interaction: discord.Interaction):
        mine = storage.reminders_of(interaction.user.id)
        if not mine:
            embed = theme.make_embed(
                "ℹ️ No reminders",
                "You have no active reminders. Set one with **/reminder**.",
                theme.INFO,
            )
        else:
            lines = []
            for r in mine:
                kind = r["kind"]
                if kind in BARS:
                    icon, label = BARS[kind]
                    lines.append(f"{icon} **{label} full**: <t:{r['due']}:R>")
                elif kind == "landing":
                    lines.append(f"✈️ **Landing**: {r.get('label', 'your flight')} lands <t:{r['until']}:R>")
                elif kind == "flying":
                    lines.append("✈️ **Flying**: watching for a Xanax restock in Japan (I message you if you are landed there)")
                elif kind == "release":
                    icon = "🏥" if r.get("state") == "Hospital" else "🔒"
                    lines.append(f"{icon} **{r.get('state', 'Hospital/jail')} over**: <t:{r['due']}:R>")
            embed = theme.make_embed("⏰ Your reminders", "\n".join(lines), theme.PRIMARY,
                                     footer="Cancel with /reminder (turn on the cancel option)")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Reminders(bot))
