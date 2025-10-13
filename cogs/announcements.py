# cogs/announcements.py
import discord
from discord.ext import commands, tasks
from discord import app_commands
import logging
from utils.image_store import ImageStore
import os
from datetime import time, timedelta

logger = logging.getLogger("announcements")

class AnnouncementsCog(commands.Cog, name="AnnouncementsCog"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # set base url if you want to use static serving through webserver
        base_url = os.environ.get("STATIC_BASE_URL")  # e.g. https://<render-domain>/static/banners
        self.image_store = bot.image_store if hasattr(bot, "image_store") else ImageStore(static_dir="static/banners", base_url=base_url)
        self.daily_post_loop.change_interval(seconds=60*60*24)  # default daily interval, can override

    # Example slash command to create a one-off announcement
    @app_commands.command(name="announcement", description="Create an announcement (owner/mod only).")
    @app_commands.describe(channel="Channel to post announcement", title="Title", message="Message text")
    async def announcement(self, interaction: discord.Interaction, channel: discord.TextChannel, title: str, message: str):
        # permission: only let owner or users with manage_guild send announcements
        if not await self._is_owner_or_mod(interaction.user):
            await interaction.response.send_message("You do not have permission to make announcements.", ephemeral=True)
            return

        await interaction.response.defer()
        embed = discord.Embed(title=title, description=message, color=discord.Color.blurple())
        chosen = self.image_store.pick_attachment()
        if chosen:
            file, filename = chosen
            embed.set_image(url=f"attachment://{filename}")
            await channel.send(embed=embed, file=file)
            await interaction.followup.send("Announcement sent with attachment.", ephemeral=True)
        else:
            # fallback to static url if available
            url = self.image_store.pick_url()
            if url:
                embed.set_image(url=url)
            await channel.send(embed=embed)
            await interaction.followup.send("Announcement sent.", ephemeral=True)

    @app_commands.command(name="postannouncement", description="Connect socials and post announcement to selected channel (owner only).")
    async def postannouncement(self, interaction: discord.Interaction, channel: discord.TextChannel, title: str, message: str):
        if not await self._is_owner_or_mod(interaction.user):
            await interaction.response.send_message("You do not have permission.", ephemeral=True)
            return
        # For multi-platform posting, you'd call external APIs here (Twitter/X, Mastodon, Facebook).
        await interaction.response.defer()
        # Post to channel
        embed = discord.Embed(title=title, description=message, color=discord.Color.gold())
        chosen = self.image_store.pick_attachment()
        if chosen:
            file, filename = chosen
            embed.set_image(url=f"attachment://{filename}")
            await channel.send(embed=embed, file=file)
        else:
            url = self.image_store.pick_url()
            if url:
                embed.set_image(url=url)
            await channel.send(embed=embed)
        await interaction.followup.send("Posted announcement and (placeholder) posted to connected socials.", ephemeral=True)

    async def _is_owner_or_mod(self, user: discord.abc.Snowflake):
        owner_id = os.environ.get("OWNER_ID")
        if owner_id and str(user.id) == str(owner_id):
            return True
        # Basic: check manage_guild permission if Member
        if isinstance(user, discord.Member):
            return user.guild_permissions.manage_guild
        return False

    # Example daily post loop — replace with your content pipeline
    @tasks.loop(hours=24.0)
    async def daily_post_loop(self):
        # Post a daily message to a configured channel id if present
        channel_id = os.environ.get("DAILY_POST_CHANNEL_ID")
        if not channel_id:
            logger.debug("DAILY_POST_CHANNEL_ID not configured.")
            return
        channel = self.bot.get_channel(int(channel_id))
        if not channel:
            logger.warning("Daily post channel not found.")
            return
        embed = discord.Embed(title="Daily Update", description="Here's a daily post from Lagoona!", color=discord.Color.green())
        chosen = self.image_store.pick_attachment()
        if chosen:
            file, filename = chosen
            embed.set_image(url=f"attachment://{filename}")
            await channel.send(embed=embed, file=file)
        else:
            url = self.image_store.pick_url()
            if url:
                embed.set_image(url=url)
            await channel.send(embed=embed)

    @daily_post_loop.before_loop
    async def before_daily(self):
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    await bot.add_cog(AnnouncementsCog(bot))
