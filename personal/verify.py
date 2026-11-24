from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils import sharing, storage, theme, torn_api
from utils.format import profile_url


class Verify(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="verify",
        description="Verify yourself using Torn's official Discord verification",
    )
    @app_commands.describe(torn_id="Your Torn ID (optional)")
    async def verify(self, interaction: discord.Interaction, torn_id: Optional[int] = None):
        await sharing.defer_reply(interaction)

        # With a Torn ID we look that account up, otherwise we look up the caller's Discord ID
        lookup_id = torn_id if torn_id else interaction.user.id

        try:
            link = await torn_api.get_discord_link(lookup_id)
        except torn_api.TornAPIError as e:
            await interaction.followup.send(embed=theme.api_error_embed(e.code, e.message))
            return

        if link is None:
            await interaction.followup.send(
                embed=theme.error_embed(
                    "Not verified",
                    "Torn has no Discord link for you yet.\n\n"
                    "**How to fix it**\n"
                    "1️⃣ Join the official Torn Discord server\n"
                    "2️⃣ Verify your account there\n"
                    "3️⃣ Run **/verify** again",
                )
            )
            return

        found_torn_id, found_discord_id = link

        if found_discord_id != interaction.user.id:
            await interaction.followup.send(
                embed=theme.error_embed(
                    "Wrong account",
                    "That Torn account is linked to a different Discord account.",
                )
            )
            return

        storage.save_verified(interaction.user.id, found_torn_id)

        embed = theme.success_embed(
            "Verified",
            f"You are officially linked to **[Torn ID {found_torn_id}]({profile_url(found_torn_id)})**.",
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.add_field(name="💬 Discord", value=interaction.user.mention)
        embed.add_field(name="🆔 Torn ID", value=str(found_torn_id))
        await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="check",
        description="Check if a member is verified with Torn",
    )
    @app_commands.describe(member="The member to check")
    async def check(self, interaction: discord.Interaction, member: discord.User):
        await sharing.defer_reply(interaction)

        try:
            link = await torn_api.get_discord_link(member.id)
        except torn_api.TornAPIError as e:
            await interaction.followup.send(embed=theme.api_error_embed(e.code, e.message))
            return

        if link is None:
            embed = theme.error_embed("Not verified", f"{member.mention} is not verified with Torn.")
        else:
            found_torn_id, _ = link
            embed = theme.success_embed(
                "Verified",
                f"{member.mention} is linked to **[Torn ID {found_torn_id}]({profile_url(found_torn_id)})**.",
            )
            embed.add_field(name="🆔 Torn ID", value=str(found_torn_id))

        embed.set_thumbnail(url=member.display_avatar.url)
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Verify(bot))
