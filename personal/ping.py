import discord
from discord import app_commands
from discord.ext import commands

from utils import sharing, theme


class Ping(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ping", description="Check if the bot is alive")
    async def ping(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)

        if latency < 150:
            color, quality = theme.SUCCESS, "Excellent"
        elif latency < 400:
            color, quality = theme.WARNING, "Okay"
        else:
            color, quality = theme.ERROR, "Slow"

        embed = theme.make_embed("🏓 Pong!", color=color)
        embed.add_field(name="Latency", value=f"**{latency} ms**")
        embed.add_field(name="Connection", value=f"`{theme.progress_bar(500 - latency, 500)}` {quality}")
        await interaction.response.send_message(embed=embed, ephemeral=sharing.is_private(interaction.user.id))


async def setup(bot):
    await bot.add_cog(Ping(bot))
