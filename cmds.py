import discord
from discord import app_commands, Embed
from discord.ext import commands

class HelpCommand(commands.Cog):
    """Contains the comprehensive help command."""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="Shows all of Lagoona's commands and features.")
    async def help_command(self, interaction: discord.Interaction):
        embed = Embed(
            title="✨ Lagoona - THE Studio Support & Community Manager",
            description="Lagoona is the ultimate solution for StarGame Studio's needs. **All your needs are met!**",
            color=discord.Color.purple()
        )

        embed.add_field(name="**STUDIO SUPPORT & COMMUNICATION**", 
                        value="`/ticket` - Opens a new support ticket for staff assistance.\n"
                              "`/setwelcomegoodbye [type] [message] [channel]` - Configures automatic join/leave messages.\n"
                              "`/dailyposts [role] [channel] [time_ast]` - Schedules a daily reminder post.\n"
                              "**Ping/Role Response:** Responds when `@Lagoona` or any of her roles are mentioned.", 
                        inline=False)
        
        embed.add_field(name="**COMMUNITY MANAGEMENT & MODERATION**", 
                        value="`/mod takenote [mod|server] [enable|disable] [channel]` - Toggles **Mod** and **Server** logs.\n"
                              "`/automod [enable|disable]` - Toggles Lagoona's strict Automod (SG/Discord/Roblox rules).\n"
                              "`/bypass [add|remove] [user]` - Manages the Automod whitelist.\n"
                              "`/completeSGApplication [start|setquestions]` - Manages the Studio Application process (10 questions).\n"
                              "**Passive Mod:** XP/Leveling, Weekly Top 10 Leaderboards, **Invite Tracker**.", 
                        inline=False)
        
        # Highlight the founder command specifically for visibility
        founder_user = self.bot.get_user(self.bot.FOUNDER_OWNER_ID)
        founder_name = founder_user.name if founder_user else "LionelClementOfficial"
        embed.add_field(name=f"**FOUNDER TOOL ({founder_name})**", 
                        value="`/schedule [guild_id] [channel_id] [title] [content] [time_ast]` - Schedule a one-time announcement to any server at a specific **AST time**.", 
                        inline=False)
        
        embed.set_footer(text=f"Requested by User ID: {interaction.user.id}. Every command is visible here!")
        embed.set_image(url=self.bot.get_random_banner_url())
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(HelpCommand(bot))
