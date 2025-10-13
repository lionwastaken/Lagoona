import discord
from discord.ext import commands
from discord import Embed
import random

class PingResponses(commands.Cog):
    """Handles responses when the bot or its roles are mentioned."""

    def __init__(self, bot):
        self.bot = bot
        # Responses Lagoona can choose from when pinged
        self.ping_messages = [
            "Hi there! How can I assist the Stargame Studio team today? Run `/help` to see my commands.",
            "Lagoona at your service! Let me know what you need.",
            "You pinged the massive Community Manager! Ready for a command or a quick chat.",
            "I heard that! Use `/help` for a full list of my features."
        ]
        
        # Responses for role pings
        self.role_ping_messages = [
            "I see a key role was pinged! If this was an announcement, I've got it logged. Need help?",
            "Role mentioned! Just ensuring the correct attention is given.",
            "Acknowledging the role mention. Running `/help` shows what I can do for the team."
        ]

    @commands.Cog.listener()
    async def on_message(self, message):
        # Ignore messages from bots or outside a guild
        if message.author.bot or not message.guild:
            return

        # Check for direct bot mention (e.g., @Lagoona)
        if self.bot.user in message.mentions:
            response = random.choice(self.ping_messages)
            embed = Embed(
                description=response,
                color=discord.Color.teal()
            )
            # Send the response in the same channel, mentioning the user
            await message.channel.send(f"{message.author.mention}", embed=embed)
            return # Don't check for role pings if the bot was directly pinged

        # Check for any of the bot's owned roles being mentioned
        bot_member = message.guild.get_member(self.bot.user.id)
        if bot_member:
            for role in bot_member.roles:
                if role.mention in message.content:
                    response = random.choice(self.role_ping_messages)
                    embed = Embed(
                        description=response,
                        color=discord.Color.light_grey()
                    )
                    # Send a subtle acknowledgement
                    await message.channel.send(embed=embed, delete_after=10) # Delete after 10s to keep chat clean
                    return

# This setup function is required to load the Cog in the main bot file.
async def setup(bot):
    await bot.add_cog(PingResponses(bot))
