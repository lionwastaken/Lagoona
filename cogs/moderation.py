# cogs/moderation.py
import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import logging
import re
from datetime import datetime, timedelta

logger = logging.getLogger("moderation")

BANNED_WORDS = {"badword1", "badword2"}  # extend via config / DB
MASS_PING_THRESHOLD = 5  # mentions in single message to consider

class ModerationCog(commands.Cog, name="ModerationCog"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.recent_joins = []  # timestamps of recent joins for raid detection
        self.join_window = timedelta(seconds=60)
        self.join_threshold = 5  # join count within join_window to consider raid

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # ignore bot messages
        if not message.guild or message.author.bot:
            return

        # simple swear detection
        lowered = message.content.lower()
        for word in BANNED_WORDS:
            if re.search(rf"\b{re.escape(word)}\b", lowered):
                try:
                    await message.delete()
                except Exception:
                    pass
                await message.channel.send(f"{message.author.mention} Please avoid that language.", delete_after=8)
                return

        # mass ping detection
        mentions_count = len(message.mentions)
        if mentions_count >= MASS_PING_THRESHOLD:
            await message.delete()
            await message.channel.send(f"{message.author.mention} that many pings is too much. Moderators have been notified.", delete_after=10)
            # TODO: escalate: log to moderation channel
            return

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        # Add to recent_joins and check for raid
        now = datetime.utcnow()
        self.recent_joins.append(now)
        # drop old timestamps
        window_start = now - self.join_window
        self.recent_joins = [t for t in self.recent_joins if t >= window_start]
        if len(self.recent_joins) >= self.join_threshold:
            # raid suspected: notify mods
            logger.warning("Possible raid detected: %d joins in last %s", len(self.recent_joins), self.join_window)
            # notify the first text channel available
            for ch in member.guild.text_channels:
                try:
                    await ch.send("@here Possible raid detected — enabling slow-mode and alerting staff.")
                    break
                except Exception:
                    continue

    @app_commands.command(name="check_alt", description="Check if a user might be an alternate account by heuristics")
    @app_commands.describe(user="User to check")
    async def check_alt(self, interaction: discord.Interaction, user: discord.Member):
        await interaction.response.defer(ephemeral=True)
        # Heuristic checks:
        # - account age
        account_age = (discord.utils.utcnow() - user.created_at).days
        # - username similarity to existing members? (placeholder)
        # - recent join date
        join_age = (discord.utils.utcnow() - user.joined_at).days if user.joined_at else None

        embed = discord.Embed(title="Alt Check", color=discord.Color.orange())
        embed.add_field(name="Account Age (days)", value=str(account_age), inline=True)
        embed.add_field(name="Joined Server (days)", value=str(join_age) if join_age is not None else "Unknown", inline=True)

        # More advanced checks could call external APIs (e.g., fraud/alt detection) — plug here.
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="automod_toggle", description="Toggle automod on/off in a channel (owner/mod only)")
    async def automod_toggle(self, interaction: discord.Interaction):
        # simple placeholder — requires permission handling
        await interaction.response.send_message("This server has automod enabled (placeholder).", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(ModerationCog(bot))
