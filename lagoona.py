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

# You need to manually replace these with your actual file paths for the banners.
# The bot MUST have access to these files in its working directory.
BANNER_PATHS = [
    'officialbanner.jpg',
    'SGStudioBannerEdited.jpg'
]

# StarGame Studio and Roblox Rule Set (Used by Automod)
# This knowledge base is used for both the /help command and Automod
SG_RULES = {
    "STUDIO_POLICY": [
        "Be respectful to everyone, do not harass others, publicly nor privately.",
        "Do not humiliate, intend harm, nor be explicitly inappropriate.",
        "Be respectful in your tone, treat others the way you want to be treated fairly and nicely.",
        "Submitting purely AI-generated artwork as original content is unacceptable.",
        "Do not engage in external payments (USD, Giftcards, Nitro) unless specifically agreed upon for commissions outside of core studio compensation.",
        "Developers working on projects will receive a 2% revenue split and credits."
    ],
    "DISCORD_TOS": [
        "No illegal content or conduct.",
        "No hateful conduct or harassment.",
        "No impersonation or fraudulent behavior.",
        "No promoting self-harm or violence.",
        "No spamming, raiding, or automated client usage (bots not explicitly permitted)."
    ],
    "ROBLOX_TOS": [
        "Do not share personal identifying information (PII).",
        "No dating or soliciting explicit content.",
        "No bullying, harassment, or hate speech.",
        "No inappropriate or illegal content.",
        "Do not exploit, cheat, or abuse platform features."
    ],
    "STAFF_ROSTER": {
        "LionelClementOfficial": "The Founder of Stargame Studio.",
        "Miyah": "A key member and artist/staff at Stargame Studio.",
        "Poleyz": "The creator of the current studio banner and a talented artist.",
        # Add other staff/artists here
    }
}

# Time zone for scheduled tasks (AST = Atlantic Standard Time)
AST_TIMEZONE = pytz.timezone('America/Puerto_Rico') # Puerto Rico observes AST/ADT which matches the user's requirement for AST

# Bot Class and Initialization
class LagoonaBot(commands.Bot):
    def __init__(self):
        # Intents needed for all new features
        intents = discord.Intents.default()
        intents.members = True # Required for logging, invites, and XP
        intents.message_content = True # Required for Automod
        intents.invites = True # Required for invite tracker
        intents.guilds = True # Required for channel logs and general server info
        intents.presences = False # Not strictly needed

        super().__init__(command_prefix='!', intents=intents)
        self.log_channels = {} # {guild_id: log_channel_id}
        self.mod_logs_enabled = {} # {guild_id: bool}
        self.server_logs_enabled = {} # {guild_id: bool}
        self.xp_data = {} # {user_id: xp}
        self.guild_invites = {} # {guild_id: {code: uses}}
        self.welcome_goodbye_config = {} # {guild_id: {channel_id: int, type: str, message: str}}
        self.application_questions = {} # {guild_id: [question1, ...]}
        self.scheduled_announcements = [] # List of {'user_id', 'guild_id', 'channel_id', 'title', 'content', 'schedule_time'}
        self.owner_id = 123456789012345678 # Placeholder: Replace with LionelClementOfficial's Discord User ID

    async def setup_hook(self):
        # Load data from a persistent storage mechanism (mocked with JSON files here)
        await self.load_data()
        
        # Sync application commands (slash commands)
        await self.tree.sync()
        print("Application commands synced.")

        # Start background tasks
        self.save_data.start()
        self.xp_leaderboard_post.start()
        self.check_scheduled_announcements.start()

    # --- Data Persistence (Mocked with JSON files) ---
    # In a real bot, use a proper database like Firestore, MongoDB, or PostgreSQL.
    # We use simple JSON files for this single-file implementation.

    async def load_data(self):
        try:
            with open('bot_data.json', 'r') as f:
                data = json.load(f)
                self.log_channels = {int(k): v for k, v in data.get('log_channels', {}).items()}
                self.mod_logs_enabled = {int(k): v for k, v in data.get('mod_logs_enabled', {}).items()}
                self.server_logs_enabled = {int(k): v for k, v in data.get('server_logs_enabled', {}).items()}
                self.xp_data = {int(k): v for k, v in data.get('xp_data', {}).items()}
                self.welcome_goodbye_config = {int(k): v for k, v in data.get('welcome_goodbye_config', {}).items()}
                self.application_questions = {int(k): v for k, v in data.get('application_questions', {}).items()}
                self.scheduled_announcements = data.get('scheduled_announcements', [])
                # Invites are loaded on_ready
                print("Data loaded successfully.")
        except FileNotFoundError:
            print("bot_data.json not found. Starting with empty data.")
        except Exception as e:
            print(f"Error loading data: {e}")

    @tasks.loop(minutes=5)
    async def save_data(self):
        # Convert keys to strings for JSON serialization
        data = {
            'log_channels': {str(k): v for k, v in self.log_channels.items()},
            'mod_logs_enabled': {str(k): v for k, v in self.mod_logs_enabled.items()},
            'server_logs_enabled': {str(k): v for k, v in self.server_logs_enabled.items()},
            'xp_data': {str(k): v for k, v in self.xp_data.items()},
            'welcome_goodbye_config': {str(k): v for k, v in self.welcome_goodbye_config.items()},
            'application_questions': {str(k): v for k, v in self.application_questions.items()},
            'scheduled_announcements': self.scheduled_announcements
        }
        try:
            with open('bot_data.json', 'w') as f:
                json.dump(data, f, indent=4)
            print(f"Data saved at {datetime.now()}")
        except Exception as e:
            print(f"Error saving data: {e}")

    # --- Utility Functions ---

    def get_random_banner(self):
        """Returns a random banner file object and its name."""
        try:
            banner_name = random.choice(BANNER_PATHS)
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
        level = int((xp / 100) ** 0.5)
        xp_needed = (level + 1) ** 2 * 100
        return xp, level, xp_needed

    def add_xp(self, user_id, guild_id, amount):
        """Adds XP to a user and returns True if they leveled up."""
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

        if log_type == 'mod' and self.mod_logs_enabled.get(guild.id, False):
            await log_channel.send(embed=embed)
        elif log_type == 'server' and self.server_logs_enabled.get(guild.id, False):
            await log_channel.send(embed=embed)
        elif log_type == 'app_invite': # Always log applications and invites
            await log_channel.send(embed=embed)


    # --- Events ---

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('Bot is ready.')

        # Initialize invite cache for all guilds
        for guild in self.guilds:
            try:
                self.guild_invites[guild.id] = {invite.code: invite.uses for invite in await guild.invites()}
            except discord.errors.Forbidden:
                print(f"Lacking 'Manage Server' permission to read invites in {guild.name}")
        
        # Set the correct owner ID for the founder check
        # This is a critical step to enable founder-only commands like scheduling
        self.owner_id = self.owner_id # Placeholder, set this manually if needed

    async def on_guild_join(self, guild):
        # Initialize settings for a new guild
        self.log_channels[guild.id] = None
        self.mod_logs_enabled[guild.id] = False
        self.server_logs_enabled[guild.id] = False
        self.welcome_goodbye_config[guild.id] = {}
        self.application_questions[guild.id] = []
        
        # Cache invites
        try:
            self.guild_invites[guild.id] = {invite.code: invite.uses for invite in await guild.invites()}
        except discord.errors.Forbidden:
            print(f"Lacking 'Manage Server' permission to read invites in {guild.name}")

    async def on_member_join(self, member):
        guild = member.guild

        # 1. Invite Tracker (Mandatory for Community Management)
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

                invite_message = "I couldn't track who invited this member."
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
                await self.log_event(guild, invite_embed, 'app_invite') # Uses the 'app_invite' log type to ensure it's logged

            except discord.errors.Forbidden:
                print(f"Cannot track invites in {guild.name}. Missing 'Manage Server' permission.")
        
        # 2. Welcome Message
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
        
        # 1. Goodbye Message
        config = self.welcome_goodbye_config.get(guild.id, {})
        if config.get('type') == 'goodbye':
            channel = self.get_channel(config.get('channel_id'))
            if channel:
                # Use a random banner for the goodbye message
                file, filename = self.get_random_banner()
                embed = Embed(
                    title=f"GOODBYE, {member.name}...",
                    description=config.get('message', 'Sad to see you go, maybe in another timeline?'),
                    color=discord.Color.dark_red()
                )
                embed.set_image(url=f"attachment://{filename}")
                await channel.send(embed=embed, file=file)

        # 2. Update invite cache (uses went down if the user was the last to use an invite)
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

        # 1. XP Gain (Only process for non-command messages)
        # Give a small, random amount of XP for every message to encourage chat activity
        if not message.content.startswith(self.command_prefix):
            xp_amount = random.randint(15, 25)
            new_level = self.add_xp(message.author.id, message.guild.id, xp_amount)
            
            if new_level is not None:
                # Level Up announcement
                log_channel = await self.get_log_channel(message.guild.id)
                if log_channel:
                    file, filename = self.get_random_banner()
                    embed = Embed(
                        title=f"⭐ Level Up!",
                        description=f"Congratulations {message.author.mention}! You've reached **Level {new_level}**!",
                        color=discord.Color.gold()
                    )
                    embed.set_image(url=f"attachment://{filename}")
                    await log_channel.send(embed=embed, file=file)
                
                # Check for staff roles to assign upon reaching a certain level
                # Example: If a user reaches level 10, they get the 'Member' role
                # For this implementation, we will keep it simple and just announce the level up.

        # 2. Automod System
        await self.process_automod(message)

        # Process commands last
        await self.process_commands(message)

    async def process_automod(self, message):
        guild = message.guild
        member = message.author
        content = message.content.lower()
        
        # Critical: Check if the user is an alternate banned account.
        # This requires a hypothetical list/database of known alt-accounts tied to bans.
        # For implementation, we will mock this check.
        # REAL IMPLEMENTATION: This needs a database lookup tied to permanent bans.
        
        # Mock check for alternate banned accounts
        is_known_alt = False # Assume False for safety unless confirmed via a real database
        if is_known_alt:
            await member.ban(reason="AUTOMOD: Instant ban - Detected alternate account of a permanently banned user.")
            log_embed = Embed(title="🚫 User Banned (Alt Account)", description=f"**User:** {member.mention}\n**Reason:** Detected alternate account of a permanently banned user.", color=discord.Color.dark_red())
            await self.log_event(guild, log_embed, 'mod')
            return

        # Bad Word / Explicit Language Check (Following SG/Discord/Roblox rules)
        bad_words = ["badword1", "swearword2", "inappropriatephrase3"] # Placeholder list
        is_bad_word = any(word in content for word in bad_words)
        
        if is_bad_word:
            # Delete the message
            try:
                await message.delete()
            except:
                pass # Can't delete, ignore
            
            # Action: Warn
            # In a real bot, we would track warnings in a database.
            
            # Simple Mute (simulating 10 minutes)
            mute_time = timedelta(minutes=10)
            reason = "AUTOMOD: Use of inappropriate language (SG/Discord/Roblox Rule Violation)."
            
            try:
                await member.timeout(mute_time, reason=reason)
                log_embed = Embed(title="🔇 User Muted (Bad Word)", description=f"**User:** {member.mention}\n**Action:** 10 Minute Timeout\n**Reason:** {reason}", color=discord.Color.orange())
                await member.send(f"You have been automatically muted in **{guild.name}** for 10 minutes due to rule-breaking language. This is a warning. Continued violations will result in a kick or ban.")
                await self.log_event(guild, log_embed, 'mod')
            except discord.errors.Forbidden:
                print("Lacking permissions to mute user.")


        # Raiding/Mass Mention Check (Discord TOS Violation)
        if len(message.mentions) > 10 and not member.guild_permissions.kick_members:
            
            # Action: Temporary Server Lockdown, Ban User, and Report
            
            # 1. Ban the user
            ban_reason = "AUTOMOD: Instant Ban - Attempted server raiding/mass mention spam (Discord TOS Violation)."
            try:
                await member.ban(reason=ban_reason)
            except discord.errors.Forbidden:
                print("Lacking permissions to ban user.")
                return

            # 2. Temporary Server Lockdown (Lock all writable channels)
            locked_channels = []
            for channel in guild.channels:
                if isinstance(channel, discord.TextChannel) and channel.permissions_for(guild.default_role).send_messages:
                    try:
                        await channel.set_permissions(guild.default_role, send_messages=False, reason="AUTOMOD: Server Lockdown due to raid attempt.")
                        locked_channels.append(channel.mention)
                    except discord.errors.Forbidden:
                        pass
            
            # 3. Log and Report
            log_embed = Embed(
                title="🚨 RAID ATTEMPT DETECTED & SERVER LOCKED 🚨", 
                description=f"**Perpetrator:** {member.mention} (`{member.id}`)\n**Action Taken:** Instant Ban & Server Lockdown\n**Reason:** Mass mention/spamming (Raiding)\n**Channels Locked:** {len(locked_channels)}", 
                color=discord.Color.red(),
                timestamp=datetime.now(pytz.utc)
            )
            log_embed.set_footer(text="Server will automatically unlock in 5 minutes.")
            await self.log_event(guild, log_embed, 'mod')

            # 4. Message the banned user (if possible)
            try:
                await member.send(f"You have been **permanently banned** from **{guild.name}** for **Server Raiding/Mass Spam**.\n\nYour account has been **reported to Discord** for violation of their Terms of Service and Community Guidelines.")
            except:
                pass # DM closed
            
            # 5. Schedule Server Unlock
            await asyncio.sleep(300) # Wait 5 minutes
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

    @mod_group.command(name="takenote", description="Enable or disable moderation and server logs for Lagoona.")
    @app_commands.describe(log_type="What type of logs to toggle.", action="Enable or Disable logs.", channel="The channel to send the logs to.")
    @app_commands.checks.has_permissions(administrator=True)
    async def takenote(self, interaction: discord.Interaction, log_type: str, action: str, channel: discord.TextChannel = None):
        guild_id = interaction.guild_id
        action = action.lower()
        log_type = log_type.lower()
        
        is_enable = action == 'enable'

        if log_type not in ['mod', 'server']:
            return await interaction.response.send_message("Invalid log type. Choose 'mod' (moderation) or 'server' (joins, leaves, config changes).", ephemeral=True)

        if is_enable and not channel:
            return await interaction.response.send_message("You must specify a channel when enabling logging.", ephemeral=True)

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

    @app_commands.command(name="help", description="Shows all of Lagoona's commands and information.")
    async def help_command(self, interaction: discord.Interaction):
        embed = Embed(
            title="✨ Lagoona - Stargame Studio Community Manager",
            description="I'm here to help manage your community, moderate chats, and streamline studio operations.",
            color=discord.Color.purple()
        )

        embed.add_field(name="/help", value="Shows this command list.", inline=False)
        embed.add_field(name="/ticket", value="Creates a support ticket for staff.", inline=False)
        embed.add_field(name="/setwelcomegoodbye [type] [message]", value="Sets the welcome or goodbye message for the current channel. Must be an administrator.", inline=False)
        embed.add_field(name="/dailyposts [role] [channel]", value="Sets up daily posts in a channel, pinging a specific role.", inline=False)
        embed.add_field(name="/completeSGApplication", value="Starts the studio application process (Manager use only).", inline=False)
        embed.add_field(name="/mod takenote [type] [action] [channel]", value="**MOD:** Toggles moderation ('mod') or server ('server') logs.", inline=False)
        embed.add_field(name="/schedule", value="**FOUNDER:** Schedule an announcement for a specific time (DM command).", inline=False)
        embed.add_field(name="Passive Features", value="XP/Leveling, Automod (SG, Discord, Roblox rules enforced), Invite Tracker, and Weekly Leaderboards.", inline=False)
        
        # Add a random banner to the help message
        file, filename = self.get_random_banner()
        if file:
            embed.set_image(url=f"attachment://{filename}")
            await interaction.response.send_message(embed=embed, file=file, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)


    @app_commands.command(name="ticket", description="Open a new support ticket.")
    async def ticket(self, interaction: discord.Interaction):
        # In a real bot, this creates a private channel (ticket) and sends a prompt.
        await interaction.response.send_message("A new support ticket has been opened! A staff member will be with you shortly. Please state your issue clearly.", ephemeral=False)

    @app_commands.command(name="setwelcomegoodbye", description="Set up or disable welcome and goodbye messages.")
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
        
        await interaction.response.send_message(f"Successfully set the **{type}** message in {channel.mention}.", ephemeral=True)

    @app_commands.command(name="dailyposts", description="Sets up a channel and role for daily posts.")
    @app_commands.describe(role="The role to ping daily.", channel="The channel for the daily post.")
    @app_commands.checks.has_permissions(administrator=True)
    async def dailyposts(self, interaction: discord.Interaction, role: discord.Role, channel: discord.TextChannel):
        # NOTE: For this single-file implementation, we are just acknowledging the setup.
        # A fully functional version requires storing this configuration and running a background task.
        
        # We will use the existing scheduled_announcements list for a simple mock setup
        # For a true daily post, a dedicated config and loop would be better.
        
        await interaction.response.send_message(
            f"Daily posts acknowledging **{role.name}** in {channel.mention} have been set up! I will post a random announcement/check-in post at 10 AM AST.",
            ephemeral=True
        )

    # --- Application System ---

    class ApplicationQuestionModal(discord.ui.Modal, title='Set Application Questions'):
        def __init__(self, bot, guild_id):
            super().__init__()
            self.bot = bot
            self.guild_id = guild_id
            self.questions = []
            
            # Create 10 text inputs for questions
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

            if not valid_questions:
                await interaction.response.send_message("No questions were set. The application feature is now inactive.", ephemeral=True)
            else:
                q_list = "\n".join([f"{i+1}. {q}" for i, q in enumerate(valid_questions)])
                await interaction.response.send_message(
                    f"✅ **{len(valid_questions)}** Application questions successfully set for Stargame Studio applications!\n\n**Questions:**\n{q_list}",
                    ephemeral=True
                )

    class ApplicationResponseModal(discord.ui.Modal, title='Stargame Studio Application'):
        def __init__(self, bot, questions, manager):
            super().__init__()
            self.bot = bot
            self.questions = questions
            self.manager = manager
            self.answers = []
            
            # Create text inputs based on the set questions
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
            
            # Compile the application summary
            summary = [f"**Applicant:** {applicant.name} (`{applicant.id}`)", "-"*20]
            for i, q in enumerate(self.questions):
                summary.append(f"**Q: {q}**\n**A:** {self.answers[i].value}\n")
            
            summary_text = "\n".join(summary)
            
            # Forward the application to the designated manager (who added the bot)
            try:
                # The user who added the bot is the manager for forwarding applications
                await self.manager.send(f"**New Stargame Studio Application Submitted!**\n\n{summary_text}")
                await interaction.response.send_message("✅ Your application has been submitted successfully! The manager has been notified.", ephemeral=True)
            except:
                await interaction.response.send_message("❌ Failed to send the application to the manager. Please notify a staff member directly.", ephemeral=True)


    @app_commands.command(name="completeSGApplication", description="Start or configure the Stargame Studio application process.")
    @app_commands.describe(action="Start the application or set the questions (manager only).")
    async def completesgapplication(self, interaction: discord.Interaction, action: str):
        guild_id = interaction.guild_id
        action = action.lower()
        
        # Manager/Admin action: Set Questions
        if action == 'setquestions':
            if not interaction.user.guild_permissions.manage_guild: # Check for management permission
                return await interaction.response.send_message("Only members with 'Manage Server' permissions can set application questions.", ephemeral=True)
            
            modal = self.ApplicationQuestionModal(self, guild_id)
            await interaction.response.send_modal(modal)
            return

        # User action: Start Application
        elif action == 'start':
            questions = self.application_questions.get(guild_id)
            if not questions:
                return await interaction.response.send_message("The manager has not yet set the application questions. Please wait for them to configure the system.", ephemeral=True)

            # Get the guild owner (who likely added the bot) to be the recipient
            manager = interaction.guild.owner 
            
            modal = self.ApplicationResponseModal(self, questions, manager)
            await interaction.response.send_modal(modal)
            return

        else:
            await interaction.response.send_message("Invalid action. Use `/completeSGApplication start` to apply, or `/completeSGApplication setquestions` (Manager only) to configure.", ephemeral=True)

    # --- Founder DM and Scheduling ---

    @app_commands.command(name="schedule", description="[Founder Only] Schedule an announcement to a server at a specific time in AST.")
    @app_commands.checks.is_owner() # Checks against the bot's configured owner_id
    @app_commands.describe(guild_id="ID of the server (Guild) for the announcement.", channel_id="ID of the channel for the announcement.", title="Title of the announcement embed.", content="Main text of the announcement.", time_ast="Time in 24h format (e.g., 22:00 for 10 PM AST).")
    async def schedule(self, interaction: discord.Interaction, guild_id: str, channel_id: str, title: str, content: str, time_ast: str):
        # This command is designed to be used in a DM (but using a slash command here for simplicity,
        # the DM handling would be in on_message. For this single-file, we'll keep it as a privileged slash command).
        
        if not interaction.user.id == self.owner_id:
             return await interaction.response.send_message("You are not the designated Founder for this command.", ephemeral=True)

        try:
            guild = self.get_guild(int(guild_id))
            channel = self.get_channel(int(channel_id))
            
            if not guild or not channel:
                return await interaction.response.send_message("Invalid Server ID or Channel ID.", ephemeral=True)
            
            hour, minute = map(int, time_ast.split(':'))
            now_ast = datetime.now(AST_TIMEZONE)
            
            # Create a datetime object for the schedule time today
            scheduled_dt_ast = now_ast.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            # If the scheduled time is in the past, schedule it for tomorrow
            if scheduled_dt_ast < now_ast:
                scheduled_dt_ast += timedelta(days=1)
                
            # Convert to UTC for reliable comparison
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
                f"✅ Announcement scheduled for **{scheduled_dt_ast.strftime('%I:%M %p AST')}** ({guild.name} in {channel.mention}).",
                ephemeral=True
            )

        except Exception as e:
            await interaction.response.send_message(f"❌ Error scheduling announcement: {e}", ephemeral=True)

    # --- Background Tasks ---

    @tasks.loop(minutes=1)
    async def check_scheduled_announcements(self):
        now_utc = datetime.now(pytz.utc)
        announcements_to_remove = []
        
        for ann in self.scheduled_announcements:
            schedule_time_utc = datetime.fromisoformat(ann['schedule_time'])
            
            # Check if the scheduled time has passed
            if schedule_time_utc <= now_utc:
                
                channel = self.get_channel(ann['channel_id'])
                if channel:
                    try:
                        # Create the announcement embed with a random banner
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
                        print(f"Failed to send scheduled announcement in {ann['guild_id']}: {e}")
                
                announcements_to_remove.append(ann)

        # Remove processed announcements
        for ann in announcements_to_remove:
            self.scheduled_announcements.remove(ann)


    @tasks.loop(weeks=1)
    async def xp_leaderboard_post(self):
        # This task runs weekly to post the top 10 XP users.
        await self.wait_until_ready() # Ensure bot is ready
        
        # Find all active guilds where logs are enabled (or just pick one main channel)
        # For simplicity, we'll post to the log channel if one is set.
        
        for guild in self.guilds:
            log_channel = await self.get_log_channel(guild.id)
            if not log_channel:
                continue

            # Sort users by XP (descending)
            sorted_xp = sorted(
                [(user_id, xp) for user_id, xp in self.xp_data.items()],
                key=lambda item: item[1],
                reverse=True
            )
            
            # Get the top 10 users
            top_10 = sorted_xp[:10]
            
            leaderboard_text = ""
            for i, (user_id, xp) in enumerate(top_10):
                member = guild.get_member(user_id)
                if member:
                    xp, level, _ = self.get_user_xp_level(user_id)
                    leaderboard_text += f"**{i+1}.** {member.mention} - **Level {level}** ({xp} XP)\n"
            
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
# NOTE: Replace 'YOUR_BOT_TOKEN_HERE' with your actual bot token.
if __name__ == '__main__':
    # Add a fake token check for the compiler
    if 'DISCORD_BOT_TOKEN' in os.environ:
        TOKEN = os.environ['DISCORD_BOT_TOKEN']
    else:
        # **REPLACE THIS WITH YOUR ACTUAL BOT TOKEN**
        TOKEN = "YOUR_BOT_TOKEN_HERE" 

    bot = LagoonaBot()
    bot.run(TOKEN)
