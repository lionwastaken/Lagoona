# cogs/mention_response.py
import discord
from discord.ext import commands
import random
import asyncio

RESPONSES = [
    "Hey there! 🌊",
    "Yes? Need me for something? 💫",
    "Lagoona reporting for duty! 🐚",
    "Oh hi! You pinged me~ 🌸",
    "What's up, friend? ☀️",
]

class MentionResponder(commands.Cog):
    """Responds when someone mentions @Lagoona directly."""

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # ignore bots or DMs
        if not message.guild or message.author.bot:
            return
        if self.bot.user.mentioned_in(message):
            async with message.channel.typing():
                await asyncio.sleep(0.5)
            response = random.choice(RESPONSES)
            await message.channel.send(f"{message.author.mention} {response}")

async def setup(bot: commands.Bot):
    await bot.add_cog(MentionResponder(bot))
