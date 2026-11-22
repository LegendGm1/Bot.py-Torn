import discord
from discord import app_commands
from discord.ext import commands

from utils import sharing, theme


class ViewCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="view_yes", description="Let others see your personal command results for 5 minutes")
    async def view_yes(self, interaction: discord.Interaction):
        was_active = sharing.is_active(interaction.user.id)
        ends_at = sharing.start(interaction.user.id)

        embed = theme.make_embed(
            "🔄 Sharing timer reset" if was_active else "👀 Sharing is ON",
            f"For the next **{sharing.SHARE_SECONDS // 60} minutes**, the results of your personal commands "
            "(like /profile, /bars and /cooldowns) are posted in the channel where you use them, "
            "so other players can see them.",
            theme.WARNING,
        )
        embed.add_field(name="⏱️ Ends", value=f"<t:{ends_at}:R>")
        embed.add_field(name="🔑 API key", value="Never shown, in any case")
        embed.add_field(name="⚔️ Battle stats", value="You get a warning first")
        embed.add_field(name="🛑 Stop early", value="Use **/view_no**")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="view_no", description="Stop sharing: make your results private again")
    async def view_no(self, interaction: discord.Interaction):
        if sharing.stop(interaction.user.id):
            embed = theme.success_embed("Sharing is OFF", "Your personal commands are private again.")
        else:
            embed = theme.make_embed("ℹ️ Sharing wasn't on", "Your personal commands are already private.", theme.INFO)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(ViewCommands(bot))
