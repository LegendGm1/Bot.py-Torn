import importlib.util
import subprocess
import sys
from pathlib import Path

# Libraries are installed into the "libs" folder next to main.py
BASE_DIR = Path(__file__).resolve().parent
LIBS_DIR = BASE_DIR / "libs"
sys.path.insert(0, str(LIBS_DIR))

# module name (what you import) -> package name (what pip installs)
REQUIREMENTS = {
    "discord": "discord.py",
}


def ensure_dependencies():
    missing = [
        package
        for module, package in REQUIREMENTS.items()
        if importlib.util.find_spec(module) is None
    ]
    if missing:
        print(f"Installing missing packages: {', '.join(missing)}")
        subprocess.check_call(
            [
                sys.executable, "-m", "pip", "install",
                "--target", str(LIBS_DIR),
                "--no-cache-dir",
                "--disable-pip-version-check",
                *missing,
            ]
        )
        importlib.invalidate_caches()  # so Python notices the freshly installed packages


ensure_dependencies()  # must run BEFORE the imports below

import os

import discord
from discord.ext import commands

from utils import storage

# Read config.txt (lines like NAME=value) into environment variables
for line in (BASE_DIR / "config.txt").read_text(encoding="utf-8-sig").splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    name, value = line.split("=", 1)
    os.environ[name.strip()] = value.strip().strip("\"'")

TOKEN = os.getenv("DISCORD_TOKEN")

COMMAND_FOLDERS = ["faction", "personal", "superuser"]


class TornBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.default())

    async def setup_hook(self):
        storage.init()  # loads data.json if it exists
        # Load every .py file inside each command folder as an extension
        for folder in COMMAND_FOLDERS:
            for file in Path(folder).glob("*.py"):
                if file.name.startswith("_"):
                    continue
                await self.load_extension(f"{folder}.{file.stem}")
                print(f"Loaded {folder}/{file.name}")
        await self.tree.sync()  # registers slash commands with Discord

    async def on_ready(self):
        print(f"Logged in as {self.user}")


bot = TornBot()
bot.run(TOKEN)
