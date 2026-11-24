from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils import sharing, theme, torn_api, users
from utils.format import profile_url

# status state -> (icon, embed color)
STATE_STYLE = {
    "Okay": ("🟢", theme.SUCCESS),
    "Hospital": ("🏥", theme.ERROR),
    "Jail": ("🔒", theme.MUTED),
    "Traveling": ("✈️", theme.INFO),
    "Abroad": ("🌍", theme.INFO),
}


class Profile(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="profile", description="Look up a Torn player's public profile")
    @app_commands.describe(
        torn_id="Torn ID to look up",
        member="Discord member to look up (they must be verified with Torn)",
    )
    async def profile(
        self,
        interaction: discord.Interaction,
        torn_id: Optional[int] = None,
        member: Optional[discord.User] = None,
    ):
        await sharing.defer_reply(interaction)

        try:
            # No Torn ID given: find it from the member, or from the person running the command
            if torn_id is None:
                target = member or interaction.user
                torn_id = await users.resolve_torn_id(target.id)
                if torn_id is None:
                    await interaction.followup.send(
                        embed=theme.error_embed(
                            "No Torn account found",
                            f"I can't find a Torn account for {target.mention}.\n"
                            "They need to verify in the official Torn Discord server, "
                            "or you can use the **torn_id** option.",
                        )
                    )
                    return

            data = await torn_api.request(f"user/{torn_id}", "profile")
        except torn_api.TornAPIError as e:
            await interaction.followup.send(embed=theme.api_error_embed(e.code, e.message))
            return

        status = data.get("status", {})
        faction = data.get("faction", {})
        life = data.get("life", {})
        last_action = data.get("last_action", {})

        icon, color = STATE_STYLE.get(status.get("state"), ("⚪", theme.PRIMARY))

        faction_name = faction.get("faction_name")
        faction_text = f"{faction_name} ({faction.get('position', 'Member')})" if faction_name else "None"

        embed = theme.make_embed(
            f"👤 {data.get('name')} [{data.get('player_id')}]",
            f"{icon} **{status.get('description', 'Unknown')}**",
            color,
            url=profile_url(data.get("player_id")),
        )
        embed.add_field(name="🏆 Level", value=str(data.get("level", "?")))
        embed.add_field(name="🎖️ Rank", value=str(data.get("rank", "?")))
        embed.add_field(name="🏴 Faction", value=faction_text)
        embed.add_field(
            name="❤️ Life",
            value=f"`{theme.progress_bar(life.get('current'), life.get('maximum'))}`\n"
                  f"**{life.get('current', '?')}/{life.get('maximum', '?')}**",
        )
        embed.add_field(name="🕒 Last action", value=last_action.get("relative", "?"))

        image = data.get("profile_image")
        if isinstance(image, str) and image.startswith("http"):
            embed.set_thumbnail(url=image)

        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Profile(bot))
