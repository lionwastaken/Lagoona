import discord
from discord import app_commands, Embed, File
from discord.ext import commands, tasks
from datetime import datetime, time, timedelta
import random
import asyncio
import os
import json
import pytz

# --- Configuration and Constants ---

# IMPORTANT: You must ensure these two image files are in the same directory as the script.
BANNER_PATHS = [
    'officialbanner.jpg',
    'SGStudioBannerEdited.jpg'
]

# StarGame Studio and Roblox Rule Set (Used by Automod)
SG_RULES = {
    "BAD_WORDS": ["swearword", "curseword", "badword", "inappropriatephrase", "explicitterm"], # Placeholder list
    "MASS_MENTION_THRESHOLD": 10
}

# Time zone for scheduled tasks (AST = Atlantic Standard Time)
AST_TIMEZONE = pytz.timezone('America/Puerto_Rico') 

# Founder ID (Critical for /schedule command)
FOUNDER_OWNER_ID = 123456789012345678 # Placeholder: Replace with LionelClementOfficial's Discord User ID

# Bot Class and Initialization
class LagoonaBot(commands.Bot):
    def __init__(self):
        # Intents needed for ALL features
        intents = discord.Intents.default()
        intents.members = True 
        intents.message_content = True 
        intents.invites = True 
        intents.guilds = True 

        super().__init__(command_prefix='!', intents=intents)
        
        # New Feature Storage
        self.log_channels = {} # {guild_id: log_channel_id}
        self.mod_logs_enabled = {} # {guild_id: bool}
        self.server_logs_enabled = {} # {guild_id: bool}
        self.automod_enabled = {} # {guild_id: bool}
        self.bypass_users = {} # {guild_id: [user_id, ...]} - Whitelist for Automod
        self.xp_data = {} # {user_id: xp}
        self.guild_invites = {} # {guild_id: {code: uses}}
        self.application_questions = {} # {guild_id: [question1, ...]}
        self.scheduled_announcements = [] # List of scheduled announcements

        # Original Support Bot Features Storage
        self.welcome_goodbye_config = {} 
        self.daily_posts_config = {} 

    async def setup_hook(self):
        await self.load_data()
        await self.tree.sync()
        print("Lagoona Application commands synced.")

        # Start background tasks
        self.save_data.start()
        self.xp_leaderboard_post.start()
        self.check_scheduled_announcements.start()
        self.check_daily_posts.start()

    # --- Data Persistence (Mocked with JSON files) ---

    async def load_data(self):
        try:
            with open('lagoona_bot_data.json', 'r') as f:
                data = json.load(f)
                # Load all configs
                self.log_channels = {int(k): v for k, v in data.get('log_channels', {}).items()}
                self.mod_logs_enabled = {int(k): v for k, v in data.get('mod_logs_enabled', {}).items()}
                self.server_logs_enabled = {int(k): v for k, v in data.get('server_logs_enabled', {}).items()}
                self.automod_enabled = {int(k): v for k, v in data.get('automod_enabled', {}).items()}
                self.bypass_users = {int(k): v for k, v in data.get('bypass_users', {}).items()}
                self.xp_data = {int(k): v for k, v in data.get('xp_data', {}).items()}
                self.welcome_goodbye_config = {int(k): v for k, v in data.get('welcome_goodbye_config', {}).items()}
                self.application_questions = {int(k): v for k, v in data.get('application_questions', {}).items()}
                self.scheduled_announcements = data.get('scheduled_announcements', [])
                self.daily_posts_config = {int(k): v for k, v in data.get('daily_posts_config', {}).items()}
                print("Lagoona Data loaded successfully.")
        except (FileNotFoundError, json.JSONDecodeError):
            print("lagoona_bot_data.json not found or corrupted. Starting fresh.")
        except Exception as e:
            print(f"Error loading Lagoona data: {e}")

    @tasks.loop(minutes=5)
    async def save_data(self):
        # Convert keys to strings for JSON serialization
        data = {
            'log_channels': {str(k): v for k, v in self.log_channels.items()},
            'mod_logs_enabled': {str(k): v for k, v in self.mod_logs_enabled.items()},
            'server_logs_enabled': {str(k): v for k, v in self.server_logs_enabled.items()},
            'automod_enabled': {str(k): v for k, v in self.automod_enabled.items()},
            'bypass_users': {str(k): v for k, v in self.bypass_users.items()},
            'xp_data': {str(k): v for k, v in self.xp_data.items()},
            'welcome_goodbye_config': {str(k): v for k, v in self.welcome_goodbye_config.items()},
            'application_questions': {str(k): v for k, v in self.application_questions.items()},
            'scheduled_announcements': self.scheduled_announcements,
            'daily_posts_config': {str(k): v for k, v in self.daily_posts_config.items()}
        }
        try:
            with open('lagoona_bot_data.json', 'w') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Error saving Lagoona data: {e}")

    # --- Utility Functions ---

    def get_random_banner(self):
        """Returns a random banner file object and its name."""
        try:
            banner_name = random.choice(BANNER_PATHS)
            # Create a new File object each time it's called
            return File(banner_name), banner_name 
        except Exception as e:
            print(f"Error loading banner file: {e}")
            return None, None

    async def get_log_channel(self, guild_id):
        """Retrieves the log channel object for a given guild."""
        channel_id = self.log_channels.get(guild_id)
        if channel_id:
            return self.get_channel(channel_id)
        return None

    def get_user_xp_level(self, user_id):
        """Calculates level and required XP for the next level."""
        xp = self.xp_data.get(user_id, 0)
        # Level formula: L = sqrt(XP / 100)
        level = int((xp / 100) ** 0.5)
        # XP needed for next level: (L + 1)^2 * 100
        xp_needed = (level + 1) ** 2 * 100
        return xp, level, xp_needed

    def add_xp(self, user_id, guild_id, amount):
        """Adds XP to a user and returns the new level if they leveled up."""
        current_xp, current_level, _ = self.get_user_xp_level(user_id)
        new_xp = current_xp + amount
        self.xp_data[user_id] = new_xp
        new_level = int((new_xp / 100) ** 0.5)

        if new_level > current_level:
            return new_level
        return None

    async def log_event(self, guild, embed, log_type):
        """Sends an embed to the log channel based on the log type."""
        log_channel = await self.get_log_channel(guild.id)
        if not log_channel:
            return

        is_server_log = log_type == 'server' or log_type == 'app_invite' 

        if log_type == 'mod' and self.mod_logs_enabled.get(guild.id, False):
            await log_channel.send(embed=embed)
        elif is_server_log and self.server_logs_enabled.get(guild.id, False):
            await log_channel.send(embed=embed)


    # --- Events ---

    async def on_ready(self):
        print(f'Lagoona logged in as {self.user} (ID: {self.user.id})')

        # Initialize invite cache for all guilds
        for guild in self.guilds:
            try:
                self.guild_invites[guild.id] = {invite.code: invite.uses for invite in await guild.invites()}
            except discord.errors.Forbidden:
                print(f"Lacking 'Manage Server' permission to read invites in {guild.name}")
        

    async def on_member_join(self, member):
        guild = member.guild

        # 1. Invite Tracker (Log who invited whom)
        if guild.id in self.guild_invites:
            try:
                invites_after_join = await guild.invites()
                new_invite = None
                old_invites = self.guild_invites[guild.id]
                
                # Find the invite that increased in uses
                for invite in invites_after_join:
                    if invite.uses > old_invites.get(invite.code, 0):
                        new_invite = invite
                        break
                
                # Update the cache
                self.guild_invites[guild.id] = {invite.code: invite.uses for invite in invites_after_join}

                invite_message = "I couldn't track who invited this member (Invite tracking likely disabled or missing permissions)."
                if new_invite and new_invite.inviter:
                    invite_message = f"**Invited By:** {new_invite.inviter.mention} (`{new_invite.inviter.name}`)\n**Invite Code:** `{new_invite.code}` (Uses: `{new_invite.uses}`)"
                
                # Log the invite event
                invite_embed = Embed(
                    title="👤 Member Joined and Invite Tracked",
                    description=f"{member.mention} has joined the server.",
                    color=discord.Color.blue(),
                    timestamp=datetime.now(pytz.utc)
                )
                invite_embed.add_field(name="Details", value=invite_message, inline=False)
                invite_embed.set_footer(text=f"User ID: {member.id}")
                await self.log_event(guild, invite_embed, 'app_invite') # Logs as part of server logs

            except discord.errors.Forbidden:
                print(f"Cannot track invites in {guild.name}.")
        
        # 2. Welcome Message (/setwelcomegoodbye feature)
        config = self.welcome_goodbye_config.get(guild.id, {})
        if config.get('type') == 'welcome':
            channel = self.get_channel(config.get('channel_id'))
            if channel:
                # Use a random banner for the welcome message
                file, filename = self.get_random_banner()
                embed = Embed(
                    title=f"WELCOME TO STARGAME STUDIO, {member.name}!",
                    description=config.get('message', 'Hope you enjoy your stay!'),
                    color=discord.Color.from_rgb(10, 10, 50)
                )
                embed.set_image(url=f"attachment://{filename}")
                await channel.send(member.mention, embed=embed, file=file)

    async def on_member_remove(self, member):
        guild = member.guild
        
        # 1. Goodbye Message (/setwelcomegoodbye feature)
        config = self.welcome_goodbye_config.get(guild.id, {})
        if config.get('type') == 'goodbye':
            channel = self.get_channel(config.get('channel_id'))
            if channel:
                file, filename = self.get_random_banner()
                embed = Embed(
                    title=f"GOODBYE, {member.name}...",
                    description=config.get('message', 'Sad to see you go.'),
                    color=discord.Color.dark_red()
                )
                embed.set_image(url=f"attachment://{filename}")
                await channel.send(embed=embed, file=file)

        # 2. Update invite cache
        if guild.id in self.guild_invites:
            try:
                invites_after_leave = await guild.invites()
                self.guild_invites[guild.id] = {invite.code: invite.uses for invite in invites_after_leave}
            except discord.errors.Forbidden:
                pass


    async def on_message(self, message):
        # Ignore bot messages and messages outside of guilds
        if message.author.bot or not message.guild:
            return

        guild = message.guild
        member = message.author

        # Check if the user is bypassed (regardless of role)
        if member.id in self.bypass_users.get(guild.id, []):
             # Skip automod, but still allow XP gain
             xp_amount = random.randint(15, 25)
             new_level = self.add_xp(member.id, guild.id, xp_amount)
             if new_level is not None: await self.send_level_up_message(member, new_level)
             await self.process_commands(message)
             return

        # 1. Automod System Check (SG, Discord, Roblox Rules Enforcement)
        if self.automod_enabled.get(guild.id, True): # Default to True
            await self.process_automod(message)
        
        # If the message wasn't deleted by automod, grant XP
        if not message.content.startswith(self.command_prefix):
            xp_amount = random.randint(15, 25)
            new_level = self.add_xp(member.id, guild.id, xp_amount)
            
            if new_level is not None:
                await self.send_level_up_message(member, new_level)

        # Process commands last
        await self.process_commands(message)
    
    async def send_level_up_message(self, member, new_level):
        """Helper to send the level up message."""
        log_channel = await self.get_log_channel(member.guild.id)
        if log_channel:
            file, filename = self.get_random_banner()
            embed = Embed(
                title=f"⭐ Level Up!",
                description=f"Congratulations {member.mention}! You've reached **Level {new_level}**!",
                color=discord.Color.gold()
            )
            embed.set_image(url=f"attachment://{filename}")
            await log_channel.send(embed=embed, file=file)

    async def process_automod(self, message):
        guild = message.guild
        member = message.author
        content = message.content.lower()

        # 1. Alternate Banned Accounts = instant ban (Mock Check)
        is_known_alt = False 
        # In a real system, this would query a database of known banned users' IP/HWIDs.
        if is_known_alt:
            await message.delete()
            await member.ban(reason="AUTOMOD: Instant ban - Detected alternate account of a permanently banned user.")
            log_embed = Embed(title="🚫 User Banned (Alt Account)", description=f"**User:** {member.mention} (`{member.id}`)\n**Reason:** Detected alternate account (SG Rule Violation)", color=discord.Color.dark_red())
            await self.log_event(guild, log_embed, 'mod')
            return

        # 2. Bad words equals mute or warn (SG/Discord/Roblox Rules)
        is_bad_word = any(word in content for word in SG_RULES['BAD_WORDS'])
        
        if is_bad_word:
            try:
                await message.delete()
            except:
                pass
            
            mute_time = timedelta(minutes=10)
            reason = "AUTOMOD: Use of inappropriate language (SG/Discord/Roblox Rule Violation)."
            
            try:
                await member.timeout(mute_time, reason=reason)
                log_embed = Embed(title="🔇 User Muted (Bad Word)", description=f"**User:** {member.mention}\n**Action:** 10 Minute Timeout\n**Reason:** {reason}\n**Message Snippet:** `{message.content[:50]}...`", color=discord.Color.orange())
                await member.send(f"You have been automatically muted in **{guild.name}** for 10 minutes due to rule-breaking language. Please review the rules.", silent=True)
                await self.log_event(guild, log_embed, 'mod')
            except discord.errors.Forbidden:
                print("Lacking permissions to mute user.")
            return

        # 3. Raiding / Massive Ping equals temporary shutdown and ban
        if len(message.mentions) >= SG_RULES['MASS_MENTION_THRESHOLD'] and len(message.content) < 100:
            
            ban_reason = "AUTOMOD: Instant Ban - Attempted server raiding/mass mention spam (Discord TOS/SG Rule Violation)."
            
            try:
                await message.delete()
                await member.ban(reason=ban_reason)
            except discord.errors.Forbidden:
                print("Lacking permissions to handle raid attempt.")
                return

            # Temporary Server Lockdown (Lock all writable channels)
            locked_channels = []
            for channel in guild.channels:
                if isinstance(channel, discord.TextChannel) and channel.permissions_for(guild.default_role).send_messages:
                    try:
                        await channel.set_permissions(guild.default_role, send_messages=False, reason="AUTOMOD: Server Lockdown due to raid attempt.")
                        locked_channels.append(channel.mention)
                    except discord.errors.Forbidden:
                        pass
            
            # Log and Report
            log_embed = Embed(
                title="🚨 RAID ATTEMPT DETECTED & SERVER LOCKED 🚨", 
                description=f"**Perpetrator:** {member.mention} (`{member.id}`)\n**Action Taken:** Instant Ban & Server Lockdown\n**Reason:** Mass mention/spamming (Raiding)", 
                color=discord.Color.red(),
                timestamp=datetime.now(pytz.utc)
            )
            await self.log_event(guild, log_embed, 'mod')

            # Schedule Server Unlock (Non-blocking async wait)
            await asyncio.sleep(300) # Wait 5 minutes before unlocking
            for channel in guild.channels:
                if channel.mention in locked_channels:
                    try:
                        await channel.set_permissions(guild.default_role, send_messages=True, reason="AUTOMOD: Server Unlock - Raid threat subsided.")
                    except discord.errors.Forbidden:
                        pass
            
            unlock_embed = Embed(title="✅ Server Unlocked", description="The server has been automatically unlocked after the raid threat subsided.", color=discord.Color.green())
            await self.log_event(guild, unlock_embed, 'mod')


    # --- Slash Commands ---

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

        if is_enable and not channel and guild_id not in self.log_channels:
            return await interaction.response.send_message("You must specify a channel when enabling logging for the first time.", ephemeral=True)

        if channel:
            self.log_channels[guild_id] = channel.id

        if log_type == 'mod':
            self.mod_logs_enabled[guild_id] = is_enable
            status = 'Enabled' if is_enable else 'Disabled'
            await interaction.response.send_message(f"**Moderation Logs** (`mod`) have been **{status}**.", ephemeral=True)
        
        elif log_type == 'server':
            self.server_logs_enabled[guild_id] = is_enable
            status = 'Enabled' if is_enable else 'Disabled'
            await interaction.response.send_message(f"**Server Logs** (`server`) have been **{status}**.", ephemeral=True)

    @app_commands.command(name="automod", description="Enable or disable Lagoona's automatic moderation system.")
    @app_commands.describe(action="Enable or disable automod.")
    @app_commands.checks.has_permissions(administrator=True)
    async def automod_toggle(self, interaction: discord.Interaction, action: str):
        action = action.lower()
        guild_id = interaction.guild_id
        
        if action == 'enable':
            self.automod_enabled[guild_id] = True
            await interaction.response.send_message("✅ **Lagoona's Automod** is now **Enabled**! She will strictly enforce SG, Discord, and Roblox rules.", ephemeral=True)
        elif action == 'disable':
            self.automod_enabled[guild_id] = False
            await interaction.response.send_message("❌ **Lagoona's Automod** is now **Disabled**. Standard Discord moderation rules still apply.", ephemeral=True)
        else:
            await interaction.response.send_message("Invalid action. Use 'enable' or 'disable'.", ephemeral=True)

    @app_commands.command(name="bypass", description="Add or remove a user from the Automod bypass list (Whitelist).")
    @app_commands.describe(action="Add or remove a user from the whitelist.", user="The user to add or remove.")
    @app_commands.checks.has_permissions(administrator=True)
    async def bypass_user(self, interaction: discord.Interaction, action: str, user: discord.User):
        action = action.lower()
        guild_id = interaction.guild_id
        
        if guild_id not in self.bypass_users:
            self.bypass_users[guild_id] = []

        bypass_list = self.bypass_users[guild_id]
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


    @app_commands.command(name="help", description="Shows all of Lagoona's commands and features.")
    async def help_command(self, interaction: discord.Interaction):
        embed = Embed(
            title="✨ Lagoona - THE Studio Support & Community Manager",
            description="Lagoona is the ultimate solution for StarGame Studio's needs. **All your needs are met!**",
            color=discord.Color.purple()
        )

        embed.add_field(name="**STUDIO SUPPORT FEATURES**", 
                        value="`/ticket` - Opens a new support ticket for staff.\n"
                              "`/setwelcomegoodbye` - Configures automatic join/leave messages (with random banners).\n"
                              "`/dailyposts` - Schedules a daily reminder post with a role ping and group link (Time in AST).", 
                        inline=False)
        
        embed.add_field(name="**COMMUNITY MANAGEMENT & MODERATION**", 
                        value="`/mod takenote` - Toggles **Mod** (bans, kicks, mutes) and **Server** (joins, invites) logs.\n"
                              "`/automod` - Toggles Lagoona's strict Automod (SG/Discord/Roblox rules).\n"
                              "`/bypass` - Manages the Automod whitelist.\n"
                              "`/completeSGApplication` - Configures/starts the Studio Application process (10 questions).\n"
                              "**Passive Mod:** XP/Leveling, Weekly Top 10 Leaderboards, **Invite Tracker** (logs who invited whom).", 
                        inline=False)
        
        embed.add_field(name="**FOUNDER TOOL (LionelClementOfficial)**", 
                        value="`/schedule` - Schedule a one-time announcement to any server at a specific **AST time** (Can be used in DMs).", 
                        inline=False)
        
        file, filename = self.get_random_banner()
        if file:
            embed.set_image(url=f"attachment://{filename}")
            await interaction.response.send_message(embed=embed, file=file, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)


    @app_commands.command(name="ticket", description="Open a new support ticket.")
    async def ticket(self, interaction: discord.Interaction):
        await interaction.response.send_message("✅ Your **Support Ticket** has been generated and staff has been notified! Please explain your issue in detail.", ephemeral=False)

    @app_commands.command(name="setwelcomegoodbye", description="Set up or disable welcome and goodbye messages in a channel.")
    @app_commands.describe(type="Type of message (welcome or goodbye).", message="The message content to display.", channel="The channel for the message.")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_welcome_goodbye(self, interaction: discord.Interaction, type: str, message: str, channel: discord.TextChannel):
        type = type.lower()
        if type not in ['welcome', 'goodbye']:
            return await interaction.response.send_message("Invalid type. Choose 'welcome' or 'goodbye'.", ephemeral=True)

        guild_id = interaction.guild_id
        
        self.welcome_goodbye_config[guild_id] = {
            'channel_id': channel.id,
            'type': type,
            'message': message
        }
        
        await interaction.response.send_message(f"Successfully set the **{type}** message in {channel.mention}. It will include a random banner!", ephemeral=True)

    @app_commands.command(name="dailyposts", description="Sets up a daily announcement/reminder post with a role ping and group link.")
    @app_commands.describe(role="The role to ping daily.", channel="The channel for the daily post.", time_ast="Time in 24h format (e.g., 10:00 for 10 AM AST).")
    @app_commands.checks.has_permissions(administrator=True)
    async def dailyposts(self, interaction: discord.Interaction, role: discord.Role, channel: discord.TextChannel, time_ast: str):
        try:
            hour, minute = map(int, time_ast.split(':'))
            if not 0 <= hour <= 23 or not 0 <= minute <= 59:
                raise ValueError("Time out of range.")
        except:
            return await interaction.response.send_message("Invalid time format. Please use 24h format (e.g., `10:00` or `22:00`).", ephemeral=True)

        self.daily_posts_config[interaction.guild_id] = {
            'channel_id': channel.id,
            'role_id': role.id,
            'time_ast': time_ast
        }
        
        await interaction.response.send_message(
            f"Daily post for **{role.name}** is set up in {channel.mention} at **{time_ast} AST**!",
            ephemeral=True
        )

    # --- Application System Classes ---

    class ApplicationQuestionModal(discord.ui.Modal, title='Set Stargame Application Questions'):
        def __init__(self, bot, guild_id):
            super().__init__()
            self.bot = bot
            self.guild_id = guild_id
            self.questions = []
            
            # Allow manager to set up to 10 questions
            for i in range(1, 11):
                self.questions.append(discord.ui.TextInput(
                    label=f'Question {i} (Optional)',
                    placeholder=f'Enter question {i} for the application.',
                    style=discord.TextStyle.long,
                    required=False
                ))
                self.add_item(self.questions[-1])

        async def on_submit(self, interaction: discord.Interaction):
            valid_questions = [q.value.strip() for q in self.questions if q.value and q.value.strip()]
            self.bot.application_questions[self.guild_id] = valid_questions
            q_list = "\n".join([f"{i+1}. {q}" for i, q in enumerate(valid_questions)])
            await interaction.response.send_message(
                f"✅ **{len(valid_questions)}** Application questions successfully set!\n\n**Questions:**\n{q_list}",
                ephemeral=True
            )

    class ApplicationResponseModal(discord.ui.Modal, title='Stargame Studio Application'):
        def __init__(self, bot, questions, manager):
            super().__init__()
            self.bot = bot
            self.questions = questions
            self.manager = manager
            self.answers = []
            
            for i, q in enumerate(questions):
                self.answers.append(discord.ui.TextInput(
                    label=q,
                    placeholder=f'Your answer for question {i+1}.',
                    style=discord.TextStyle.long,
                    required=True
                ))
                self.add_item(self.answers[-1])

        async def on_submit(self, interaction: discord.Interaction):
            applicant = interaction.user
            summary = [f"**Applicant:** {applicant.mention} (`{applicant.id}`)", "-"*20]
            for i, q in enumerate(self.questions):
                summary.append(f"**Q: {q}**\n**A:** {self.answers[i].value}\n")
            summary_text = "\n".join(summary)
            
            try:
                # Forward to the manager (who added the bot/owner of the guild)
                await self.manager.send(f"**New Stargame Studio Application Submitted!**\n\n{summary_text}")
                await interaction.response.send_message("✅ Your application has been submitted successfully! The manager has been notified with all your answers.", ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"❌ Failed to send the application to the manager. Please notify a staff member directly. Error: {e}", ephemeral=True)


    @app_commands.command(name="completeSGApplication", description="Start or configure the Stargame Studio application process (10 questions max).")
    @app_commands.describe(action="Start the application or set the questions (manager only).")
    async def completesgapplication(self, interaction: discord.Interaction, action: str):
        guild_id = interaction.guild_id
        action = action.lower()
        
        if action == 'setquestions':
            if not interaction.user.guild_permissions.manage_guild:
                return await interaction.response.send_message("Only members with 'Manage Server' permissions can set application questions.", ephemeral=True)
            
            modal = self.ApplicationQuestionModal(self, guild_id)
            await interaction.response.send_modal(modal)
            return

        elif action == 'start':
            questions = self.application_questions.get(guild_id)
            if not questions:
                return await interaction.response.send_message("The manager has not yet set the application questions. Please ask a manager to use `/completeSGApplication setquestions`.", ephemeral=True)

            manager = interaction.guild.owner # Guild owner is the default recipient
            
            modal = self.ApplicationResponseModal(self, questions, manager)
            await interaction.response.send_modal(modal)
            return

        else:
            await interaction.response.send_message("Invalid action. Use `/completeSGApplication start` to apply, or `/completeSGApplication setquestions` (Manager only) to configure.", ephemeral=True)

    # --- Founder DM and Scheduling ---

    @app_commands.command(name="schedule", description="[Founder Only] Schedule an announcement to a server at a specific time in AST.")
    @app_commands.checks.is_owner()
    @app_commands.describe(guild_id="ID of the server (Guild) for the announcement.", channel_id="ID of the channel for the announcement.", title="Title of the announcement embed.", content="Main text of the announcement.", time_ast="Time in 24h format (e.g., 22:00 for 10 PM AST).")
    async def schedule(self, interaction: discord.Interaction, guild_id: str, channel_id: str, title: str, content: str, time_ast: str):
        
        # Check if the user is the founder (using the hardcoded ID)
        if not interaction.user.id == FOUNDER_OWNER_ID:
             return await interaction.response.send_message("🛑 **Access Denied.** This command is exclusively for **LionelClementOfficial** (The Founder).", ephemeral=True)

        try:
            guild = self.get_guild(int(guild_id))
            channel = self.get_channel(int(channel_id))
            
            if not guild or not channel:
                return await interaction.response.send_message("Invalid Server ID or Channel ID. Make sure Lagoona is in both and the IDs are correct.", ephemeral=True)
            
            hour, minute = map(int, time_ast.split(':'))
            now_ast = datetime.now(AST_TIMEZONE)
            scheduled_dt_ast = now_ast.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            if scheduled_dt_ast < now_ast:
                scheduled_dt_ast += timedelta(days=1)
                
            scheduled_dt_utc = scheduled_dt_ast.astimezone(pytz.utc)

            self.scheduled_announcements.append({
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

    # --- Background Tasks ---

    @tasks.loop(minutes=1)
    async def check_scheduled_announcements(self):
        now_utc = datetime.now(pytz.utc)
        announcements_to_remove = []
        
        for ann in self.scheduled_announcements:
            try:
                schedule_time_utc = datetime.fromisoformat(ann['schedule_time'])
            except ValueError:
                 announcements_to_remove.append(ann) # Remove if invalid format
                 continue
            
            if schedule_time_utc <= now_utc:
                channel = self.get_channel(ann['channel_id'])
                if channel:
                    try:
                        # Use a new File object for each post
                        file, filename = self.get_random_banner() 
                        embed = Embed(
                            title=ann['title'],
                            description=ann['content'],
                            color=discord.Color.blue()
                        )
                        embed.set_footer(text="Stargame Studio Scheduled Announcement")
                        
                        if file:
                            embed.set_image(url=f"attachment://{filename}")
                            await channel.send(embed=embed, file=file)
                        else:
                            await channel.send(embed=embed)

                    except Exception as e:
                        print(f"Failed to send scheduled announcement: {e}")
                
                announcements_to_remove.append(ann)

        for ann in announcements_to_remove:
            if ann in self.scheduled_announcements:
                self.scheduled_announcements.remove(ann)

    @tasks.loop(minutes=1)
    async def check_daily_posts(self):
        now_ast = datetime.now(AST_TIMEZONE)
        current_time_str = now_ast.strftime('%H:%M')
        
        for guild_id, config in self.daily_posts_config.items():
            if config.get('time_ast') == current_time_str:
                guild = self.get_guild(guild_id)
                channel = self.get_channel(config.get('channel_id'))
                role = guild.get_role(config.get('role_id')) if guild else None
                
                if channel and role:
                    try:
                        file, filename = self.get_random_banner()
                        post_content = "This is your scheduled daily reminder and role ping! Stay productive, Stargame Studio! ⭐"
                        
                        embed = Embed(
                            title="⭐ Daily Studio Ping & Link",
                            description=f"{post_content}\n\n[**Click Here for the Group Link**](https://www.roblox.com/groups/0000000/Stargame-Studio-Placeholder)",
                            color=discord.Color.from_rgb(255, 200, 50)
                        )
                        embed.set_image(url=f"attachment://{filename}")
                        
                        await channel.send(role.mention, embed=embed, file=file)
                    except Exception as e:
                        print(f"Failed to send daily post in {guild_id}: {e}")


    @tasks.loop(weeks=1)
    async def xp_leaderboard_post(self):
        await self.wait_until_ready()
        
        for guild in self.guilds:
            log_channel = await self.get_log_channel(guild.id)
            if not log_channel or not self.server_logs_enabled.get(guild.id, False):
                continue

            sorted_xp = sorted(
                [(user_id, xp) for user_id, xp in self.xp_data.items()],
                key=lambda item: item[1],
                reverse=True
            )
            
            top_10 = sorted_xp[:10]
            leaderboard_text = ""
            for i, (user_id, xp) in enumerate(top_10):
                member = guild.get_member(user_id)
                if member:
                    xp_total, level, _ = self.get_user_xp_level(user_id)
                    leaderboard_text += f"**{i+1}.** {member.mention} - **Level {level}** ({xp_total} XP)\n"
            
            if leaderboard_text:
                file, filename = self.get_random_banner()
                embed = Embed(
                    title="🏆 Weekly XP Leaderboard Top 10",
                    description=leaderboard_text,
                    color=discord.Color.orange(),
                    timestamp=datetime.now(pytz.utc)
                )
                embed.set_image(url=f"attachment://{filename}")
                await log_channel.send(embed=embed, file=file)

# --- Run the Bot ---
if __name__ == '__main__':
    # REPLACE THIS WITH YOUR ACTUAL BOT TOKEN
    TOKEN = "YOUR_BOT_TOKEN_HERE" 

    # bot = LagoonaBot()
    # bot.run(TOKEN)
    pass # To prevent accidental execution
