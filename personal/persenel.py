import discord
from discord import app_commands
from discord.ext import commands

from utils import theme

# (icon, name, command it runs, short description). The number of each row is its position
# here, and the buttons are numbered the same way, so the text and the buttons always match.
MENU = [
    ("👤", "Profile", "profile", "Your public Torn profile"),
    ("📊", "Bars", "bars", "Energy, nerve, happy and life"),
    ("⏳", "Cooldowns", "cooldowns", "Drug, medical and booster cooldowns"),
    ("⚔️", "Battle stats", "stats", "Your battle stats"),
    ("✅", "Verify", "verify", "Link your Discord account to Torn"),
    ("🔑", "Save API key", "setkey", "Needed for Bars, Cooldowns and Battle stats"),
    ("🗑️", "Remove API key", "removekey", "Delete your saved key"),
    ("🏓", "Ping", "ping", "Check that the bot is alive"),
    ("👀", "Share my results", "view_yes", "Let others see your results for 5 minutes"),
    ("🙈", "Stop sharing", "view_no", "Make your results private again"),
]

KEYCAPS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]


class MenuButton(discord.ui.Button):
    def __init__(self, number: int, icon: str, command_name: str):
        super().__init__(
            label=str(number),
            emoji=icon,
            style=discord.ButtonStyle.primary,
            custom_id=f"persenel:{number}",  # fixed id so the button keeps working after a restart
        )
        self.command_name = command_name

    async def callback(self, interaction: discord.Interaction):
        command = interaction.client.tree.get_command(self.command_name)
        if command is None:
            await interaction.response.send_message(
                embed=theme.warning_embed("Not available", "That command isn't available right now."),
                ephemeral=True,
            )
            return
        # Run the real command code for the person who clicked.
        # The command itself decides if the answer is private or shared.
        await command.callback(command.binding, interaction)


class MenuView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # never expires
        for number, (icon, _, command_name, _) in enumerate(MENU, start=1):
            self.add_item(MenuButton(number, icon, command_name))


def make_menu_embed() -> discord.Embed:
    lines = []
    for number, (icon, name, _, description) in enumerate(MENU, start=1):
        keycap = KEYCAPS[number - 1] if number <= len(KEYCAPS) else f"**{number}.**"
        lines.append(f"{keycap} {icon} **{name}**\n└ {description}")

    return theme.make_embed(
        "📋 Personal menu",
        "\n\n".join(lines) + "\n\n👇 **Click a number below to use that command.**",
        theme.PRIMARY,
        footer="Answers are private unless you turned on sharing with /view_yes",
    )


class Persenel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(MenuView())  # keeps old menu messages clickable after a restart

    @app_commands.command(name="persenel", description="Show a menu of the personal commands")
    async def persenel(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=make_menu_embed(), view=MenuView(), ephemeral=True)


async def setup(bot):
    await bot.add_cog(Persenel(bot))
