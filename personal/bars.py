import discord
from discord import app_commands
from discord.ext import commands

from utils import sharing, theme, users
from utils.format import format_duration

# key in Torn's answer, icon, label
BARS = [
    ("energy", "⚡", "Energy"),
    ("nerve", "🔥", "Nerve"),
    ("happy", "😊", "Happy"),
    ("life", "❤️", "Life"),
]

COOLDOWNS = [
    ("drug", "💊", "Drug"),
    ("medical", "🩹", "Medical"),
    ("booster", "🚀", "Booster"),
]


class Bars(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="bars", description="Show your energy, nerve, happy and life bars")
    async def bars(self, interaction: discord.Interaction):
        await sharing.defer_reply(interaction)

        data = await users.fetch_with_user_key(interaction, "bars")
        if data is None:
            return

        embed = theme.make_embed("📊 Your bars", color=theme.PRIMARY)

        for key, icon, label in BARS:
            bar = data.get(key, {})
            current, maximum = bar.get("current"), bar.get("maximum")
            seconds = int(bar.get("fulltime") or 0)
            fill = "✅ Full" if seconds <= 0 else f"⏳ Full in {format_duration(seconds)}"
            embed.add_field(
                name=f"{icon} {label}",
                value=f"`{theme.progress_bar(current, maximum)}` **{theme.percent(current, maximum)}%**\n"
                      f"{current}/{maximum} · {fill}",
                inline=False,
            )

        chain = data.get("chain", {})
        if chain.get("current"):
            maximum = chain.get("maximum")
            embed.add_field(
                name="⛓️ Chain",
                value=f"`{theme.progress_bar(chain['current'], maximum)}`\n"
                      f"{chain['current']}/{maximum} · ⏱️ {format_duration(chain.get('timeout'), zero_text='No timer')}",
                inline=False,
            )

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="cooldowns", description="Show your drug, medical and booster cooldowns")
    async def cooldowns(self, interaction: discord.Interaction):
        await sharing.defer_reply(interaction)

        data = await users.fetch_with_user_key(interaction, "cooldowns")
        if data is None:
            return

        cooldowns = data.get("cooldowns", {})
        lines = []
        all_ready = True
        for key, icon, label in COOLDOWNS:
            seconds = int(cooldowns.get(key) or 0)
            if seconds <= 0:
                lines.append(f"{icon} **{label}**\n└ 🟢 Ready")
            else:
                all_ready = False
                lines.append(f"{icon} **{label}**\n└ 🔴 {format_duration(seconds)} left")

        embed = theme.make_embed(
            "⏳ Your cooldowns",
            "\n\n".join(lines),
            theme.SUCCESS if all_ready else theme.WARNING,
        )
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Bars(bot))
