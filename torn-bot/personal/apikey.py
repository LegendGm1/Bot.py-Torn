import discord
from discord import app_commands
from discord.ext import commands

from utils import storage, theme, torn_api


def make_tos_embed() -> discord.Embed:
    """Torn requires users to see how their key is used before they hand it over."""
    embed = theme.make_embed(
        "🔐 Before you save your API key",
        "Here is exactly what this bot does with your key:",
        theme.WARNING,
        footer="You can delete your key any time with /removekey",
    )
    embed.add_field(name="🗄️ Data storage", value="Your Torn ID and API key are stored in this bot's data file (data.json).", inline=False)
    embed.add_field(name="🤝 Data sharing", value="Nothing is shared with anyone.", inline=False)
    embed.add_field(name="🎯 Purpose of use", value="Showing you your own bars, cooldowns and battle stats, and checking your status in the background to send you the reminders you ask for.", inline=False)
    embed.add_field(name="🔑 Key storage & sharing", value="Stored as plain text on the bot's host. The bot owner can access it. Never shared.", inline=False)
    embed.add_field(name="🛡️ Key access level", value="Limited access (needed for battle stats).", inline=False)
    return embed


class KeyModal(discord.ui.Modal, title="Save your Torn API key"):
    key = discord.ui.TextInput(
        label="Torn API key",
        placeholder="Paste your key here",
        max_length=32,
    )

    async def on_submit(self, interaction: discord.Interaction):
        # API key messages are always private, whatever the sharing setting is
        await interaction.response.defer(ephemeral=True, thinking=True)
        api_key = self.key.value.strip()

        # Test the key and find out whose it is
        try:
            data = await torn_api.request("user/", "basic", key=api_key)
        except torn_api.TornAPIError as e:
            await interaction.followup.send(embed=theme.api_error_embed(e.code, f"That key didn't work: {e.message}"), ephemeral=True)
            return

        torn_id = data["player_id"]
        name = data.get("name", "Unknown")

        # If they verified earlier, the key must belong to that same Torn account
        verified_id = storage.get_verified(interaction.user.id)
        if verified_id and verified_id != torn_id:
            await interaction.followup.send(
                embed=theme.error_embed(
                    "Wrong account",
                    "That key belongs to a different Torn account than the one you verified with.",
                ),
                ephemeral=True,
            )
            return

        storage.save_key(interaction.user.id, torn_id, api_key)
        embed = theme.success_embed("Key saved", f"Saved for **{name}** [{torn_id}].")
        embed.add_field(name="Next", value="Try **/bars**, **/cooldowns** or **/stats**.")
        await interaction.followup.send(embed=embed, ephemeral=True)


class ConsentView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)

    @discord.ui.button(label="I understand, enter my key", emoji="🔑", style=discord.ButtonStyle.primary)
    async def agree(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(KeyModal())


class ApiKey(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="setkey", description="Save your Torn API key")
    async def setkey(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            embed=make_tos_embed(), view=ConsentView(), ephemeral=True
        )

    @app_commands.command(name="removekey", description="Delete your saved Torn API key")
    async def removekey(self, interaction: discord.Interaction):
        if storage.delete_key(interaction.user.id):
            embed = theme.success_embed("Key deleted", "Your API key has been removed from the bot, and so have any reminders that needed it.")
        else:
            embed = theme.warning_embed("Nothing to delete", "You don't have a saved key.")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(ApiKey(bot))
