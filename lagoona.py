# lagoona.py
import os
import asyncio
import logging
import threading
from discord.ext import commands, tasks
import discord

from utils.webserver import start_webserver
from utils.interaction_helpers import safe_respond
from utils.image_store import ImageStore

LOGLEVEL = os.environ.get("LOGLEVEL", "INFO")
logging.basicConfig(level=LOGLEVEL)
logger = logging.getLogger("lagoona")

# Bot intents (tune as needed)
intents = discord.Intents.default()
intents.members = True
intents.message_content = True  # required for some moderation features

BOT_PREFIX = "!"
OWNER_ID = int(os.environ.get("OWNER_ID", 0)) if os.environ.get("OWNER_ID") else None

class LagoonaBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=BOT_PREFIX,
            intents=intents,
            application_id=int(os.environ.get("CLIENT_ID")) if os.environ.get("CLIENT_ID") else None,
        )
        self.image_store = ImageStore(static_dir="static/banners")
        self.ready_event = asyncio.Event()

    async def setup_hook(self):
        # Load cogs
        await self.load_extension("cogs.moderation")
        await self.load_extension("cogs.announcements")
        await self.load_extension("cogs.tickets")
        await self.load_extension("cogs.voice_commands")
        await self.load_extension("cogs.mention_response")
        # Sync application commands (global). For faster dev, consider guild-specific sync.
        try:
            await self.tree.sync()
            logger.info("Slash commands synced.")
        except Exception as e:
            logger.exception("Failed to sync slash commands: %s", e)

    async def on_ready(self):
        logger.info(f"Logged in as {self.user} (id: {self.user.id})")
        self.ready_event.set()

def start_background_webserver():
    # Runs aiohttp web server in thread
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"Starting webserver on port {port} (threaded).")
    start_webserver(port=port)

def main():
    # Start webserver on separate thread so it doesn't block asyncio loop
    web_thread = threading.Thread(target=start_background_webserver, daemon=True)
    web_thread.start()

    bot = LagoonaBot()

    # Optional: schedule background tasks once bot is ready
    async def start_tasks():
        await bot.wait_until_ready()
        # Example: start a background loop inside the announcements cog
        try:
            cog = bot.get_cog("AnnouncementsCog")
            if cog and hasattr(cog, "daily_post_loop"):
                cog.daily_post_loop.start()
        except Exception as e:
            logger.exception("Failed to start cog loops: %s", e)

    bot.loop.create_task(start_tasks())

    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        logger.error("DISCORD_TOKEN not set in environment.")
        return

    bot.run(token)

if __name__ == "__main__":
    main()
