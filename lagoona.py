import discord
from discord import app_commands, Embed
from discord.ext import commands
from datetime import datetime, timedelta
import pytz
import asyncio

class ModerationFeatures(commands.Cog):
    """Handles moderation commands, logging, and scheduled announcements."""

    def __init__(self, bot):
        self.bot = bot
        self.check_scheduled_announcements.start()

    def cog_unload(self):
        self.check_scheduled_announcements.cancel()

    # Group for Manager/Moderator commands
    mod_group = app_commands.Group(name="mod", description="Moderation and Logging commands.")

    @mod_group.command(name="takenote", description="Enable or disable logs for moderation, server changes, and more.")
    @app_commands.describe(log_type="What type of logs to toggle (mod or server).", action="Enable or Disable logs.", channel="The channel to report logs to.")
    @app_commands.checks.has_permissions(administrator=True)
    async def takenote(self, interaction: discord.Interaction, log_type: str, action: str, channel: discord.TextChannel = None):
        guild_id = interaction.guild_id
        action = action.lower()
        log_type = log_type.lower()
        is_enable = action == 'enable'

        if log_type not in ['mod', 'server']:
            return await interaction.response.send_message("Invalid log type. Choose 'mod' (moderation) or 'server' (joins, invites, config changes).", ephemeral=True)

        if is_enable and not channel and guild_id not in self.bot.log_channels:
            return await interaction.response.send_message("You must specify a channel when enabling logging for the first time.", ephemeral=True)

        if channel:
            self.bot.log_channels[guild_id] = channel.id

        if log_type == 'mod':
            self.bot.mod_logs_enabled[guild_id] = is_enable
            status = 'Enabled' if is_enable else 'Disabled'
            await interaction.response.send_message(f"**Moderation Logs** (`mod`) have been **{status}**.", ephemeral=True)
        
        elif log_type == 'server':
            self.bot.server_logs_enabled[guild_id] = is_enable
            status = 'Enabled' if is_enable else 'Disabled'
            await interaction.response.send_message(f"**Server Logs** (`server`) have been **{status}**.", ephemeral=True)

    @app_commands.command(name="automod", description="Enable or disable Lagoona's automatic moderation system.")
    @app_commands.describe(action="Enable or disable automod.")
    @app_commands.checks.has_permissions(administrator=True)
    async def automod_toggle(self, interaction: discord.Interaction, action: str):
        action = action.lower()
        guild_id = interaction.guild_id
        
        if action == 'enable':
            self.bot.automod_enabled[guild_id] = True
            await interaction.response.send_message("✅ **Lagoona's Automod** is now **Enabled**! She will strictly enforce SG, Discord, and Roblox rules.", ephemeral=True)
        elif action == 'disable':
            self.bot.automod_enabled[guild_id] = False
            await interaction.response.send_message("❌ **Lagoona's Automod** is now **Disabled**. Standard Discord moderation rules still apply.", ephemeral=True)
        else:
            await interaction.response.send_message("Invalid action. Use 'enable' or 'disable'.", ephemeral=True)

    @app_commands.command(name="bypass", description="Add or remove a user from the Automod bypass list (Whitelist).")
    @app_commands.describe(action="Add or remove a user from the whitelist.", user="The user to add or remove.")
    @app_commands.checks.has_permissions(administrator=True)
    async def bypass_user(self, interaction: discord.Interaction, action: str, user: discord.User):
        action = action.lower()
        guild_id = interaction.guild_id
        
        if guild_id not in self.bot.bypass_users:
            self.bot.bypass_users[guild_id] = []

        bypass_list = self.bot.bypass_users[guild_id]
        user_id = user.id
        
        if action == 'add':
            if user_id not in bypass_list:
                bypass_list.append(user_id)
                await interaction.response.send_message(f"✅ **{user.name}** has been added to the Automod bypass list. They will not be checked by Lagoona's Automod.", ephemeral=True)
            else:
                await interaction.response.send_message(f"**{user.name}** is already in the bypass list.", ephemeral=True)
                
        elif action == 'remove':
            if user_id in bypass_list:
                bypass_list.remove(user_id)
                await interaction.response.send_message(f"✅ **{user.name}** has been removed from the Automod bypass list and is now subject to all checks.", ephemeral=True)
            else:
                await interaction.response.send_message(f"**{user.name}** was not found in the bypass list.", ephemeral=True)
        else:
            await interaction.response.send_message("Invalid action. Use 'add' or 'remove'.", ephemeral=True)

    @app_commands.command(name="ticket", description="Open a new support ticket.")
    async def ticket(self, interaction: discord.Interaction):
        await interaction.response.send_message("✅ Your **Support Ticket** has been generated and staff has been notified! Please explain your issue in detail.", ephemeral=False)

    @app_commands.command(name="schedule", description="[Founder Only] Schedule an announcement to a server at a specific time in AST.")
    @app_commands.describe(guild_id="ID of the server (Guild) for the announcement.", channel_id="ID of the channel for the announcement.", title="Title of the announcement embed.", content="Main text of the announcement.", time_ast="Time in 24h format (e.g., 22:00 for 10 PM AST).")
    async def schedule(self, interaction: discord.Interaction, guild_id: str, channel_id: str, title: str, content: str, time_ast: str):
        
        # Check if the user is the founder (using the hardcoded ID from the main bot)
        if not interaction.user.id == self.bot.FOUNDER_OWNER_ID:
             return await interaction.response.send_message("🛑 **Access Denied.** This command is exclusively for the Founder.", ephemeral=True)

        try:
            guild = self.bot.get_guild(int(guild_id))
            channel = self.bot.get_channel(int(channel_id))
            
            if not guild or not channel:
                return await interaction.response.send_message("Invalid Server ID or Channel ID. Make sure Lagoona is in both and the IDs are correct.", ephemeral=True)
            
            hour, minute = map(int, time_ast.split(':'))
            now_ast = datetime.now(self.bot.AST_TIMEZONE)
            scheduled_dt_ast = now_ast.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            if scheduled_dt_ast < now_ast:
                scheduled_dt_ast += timedelta(days=1)
                
            scheduled_dt_utc = scheduled_dt_ast.astimezone(pytz.utc)

            self.bot.scheduled_announcements.append({
                'user_id': interaction.user.id,
                'guild_id': guild.id,
                'channel_id': channel.id,
                'title': title,
                'content': content,
                'schedule_time': scheduled_dt_utc.isoformat()
            })
            
            await interaction.response.send_message(
                f"✅ Announcement scheduled for **{scheduled_dt_ast.strftime('%I:%M %p AST')}** in Server: `{guild.name}` ({channel.mention}).",
                ephemeral=True
            )

        except Exception as e:
            await interaction.response.send_message(f"❌ Error scheduling announcement. Check the time format (HH:MM 24h) and IDs. Error: {e}", ephemeral=True)

    # --- Background Task ---

    @tasks.loop(minutes=1)
    async def check_scheduled_announcements(self):
        now_utc = datetime.now(pytz.utc)
        announcements_to_remove = []
        
        for ann in self.bot.scheduled_announcements:
            try:
                schedule_time_utc = datetime.fromisoformat(ann['schedule_time'])
            except ValueError:
                 announcements_to_remove.append(ann) 
                 continue
            
            if schedule_time_utc <= now_utc:
                channel = self.bot.get_channel(ann['channel_id'])
                if channel:
                    try:
                        embed = Embed(
                            title=ann['title'],
                            description=ann['content'],
                            color=discord.Color.blue()
                        )
                        embed.set_footer(text="Stargame Studio Scheduled Announcement")
                        embed.set_image(url=self.bot.get_random_banner_url())
                        
                        await channel.send(embed=embed)
                    except Exception as e:
                        print(f"Failed to send scheduled announcement: {e}")
                
                announcements_to_remove.append(ann)

        for ann in announcements_to_remove:
            if ann in self.bot.scheduled_announcements:
                self.bot.scheduled_announcements.remove(ann)

async def setup(bot):
    await bot.add_cog(ModerationFeatures(bot))
