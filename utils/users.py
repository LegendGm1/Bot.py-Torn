import discord

from utils import storage, theme, torn_api


async def resolve_torn_id(discord_id: int):
    """Find the Torn ID for a Discord user: our saved data first, then Torn's official link."""
    torn_id = storage.get_verified(discord_id)
    if torn_id:
        return torn_id

    link = await torn_api.get_discord_link(discord_id)
    if link and link[1] == discord_id:
        storage.save_verified(discord_id, link[0])
        return link[0]

    return None


async def fetch_with_user_key(interaction: discord.Interaction, selections: str):
    """
    Call the Torn API using the saved key of the person who ran the command.

    The interaction must already be deferred (interaction.response.defer()).
    Returns the data, or None after telling the user what went wrong.
    """
    key = storage.get_key(interaction.user.id)
    if not key:
        await interaction.followup.send(
            embed=theme.warning_embed(
                "No API key saved",
                "Use **/setkey** to save your Torn API key first, then try again.",
            )
        )
        return None

    try:
        return await torn_api.request("user/", selections, key=key)
    except torn_api.TornAPIError as e:
        if e.code in torn_api.BAD_KEY_CODES:
            storage.delete_key(interaction.user.id)
            await interaction.followup.send(
                embed=theme.error_embed(
                    "API key removed",
                    "Your saved key is no longer valid, so I deleted it.\nUse **/setkey** to save a new one.",
                )
            )
        else:
            await interaction.followup.send(embed=theme.api_error_embed(e.code, e.message))
        return None
