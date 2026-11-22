import discord
from discord import app_commands
from discord.ext import commands

from utils import sharing, theme, users

# key in Torn's answer, icon, label
STATS = [
    ("strength", "💪", "Strength"),
    ("defense", "🛡️", "Defense"),
    ("speed", "💨", "Speed"),
    ("dexterity", "🎯", "Dexterity"),
]


class ContinueView(discord.ui.View):
    """The warning's buttons, shown only to the person who ran the command."""

    def __init__(self, cog, origin: discord.Interaction):
        super().__init__(timeout=120)
        self.cog = cog
        self.origin = origin  # the interaction that showed the warning, so we can tidy it afterwards

    @discord.ui.button(label="Continue", emoji="⚠️", style=discord.ButtonStyle.danger)
    async def continue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        await self.cog.show_stats(interaction)
        await self.origin.edit_original_response(view=None)  # remove the buttons from the warning

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        await interaction.response.edit_message(
            embed=theme.make_embed("Cancelled", "Your battle stats were not shown.", theme.MUTED),
            view=None,
        )

    async def on_timeout(self):
        try:
            await self.origin.edit_original_response(view=None)
        except discord.HTTPException:
            pass


class Stats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="stats", description="Show your battle stats")
    async def stats(self, interaction: discord.Interaction):
        # Battle stats are sensitive: if others can currently see your results, ask first
        ends_at = sharing.ends_at(interaction.user.id)
        if ends_at is not None:
            warning = theme.warning_embed(
                "Others can see your battle stats",
                f"Sharing is **on** (ends <t:{ends_at}:R>), so your battle stats will be posted "
                "where everyone in this channel can see them.\n\n"
                "Press **Continue** to show them anyway, or **Cancel**. "
                "You can also turn sharing off first with **/view_no**.",
            )
            await interaction.response.send_message(
                embed=warning, view=ContinueView(self, interaction), ephemeral=True
            )
            return

        await self.show_stats(interaction)

    async def show_stats(self, interaction: discord.Interaction):
        await sharing.defer_reply(interaction)

        data = await users.fetch_with_user_key(interaction, "battlestats")
        if data is None:
            return

        total = data.get("total", 0)
        embed = theme.make_embed(
            "⚔️ Your battle stats",
            f"📊 **Total: {theme.number(total)}**",
            theme.PRIMARY,
        )
        for key, icon, label in STATS:
            value = data.get(key, 0)
            embed.add_field(
                name=f"{icon} {label}",
                value=f"**{theme.number(value)}**\n`{theme.progress_bar(value, total)}` {theme.percent(value, total)}%",
            )

        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Stats(bot))
