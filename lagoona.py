import discord
from discord.ext import commands, tasks
import aiohttp
import os
import asyncio
import random
from datetime import time, datetime, timedelta
from dotenv import load_dotenv
from fuzzywuzzy import fuzz
import threading # For the simple web server fix

# --- Render/Uptime Fix: Simple Web Server ---
# This minimal web server binds a port to satisfy Render's requirement for a Web Service.
# This prevents the "Port scan timeout" error and keeps UptimeRobot happy.
# We run the actual bot logic as a standard discord bot process.
from http.server import SimpleHTTPRequestHandler, HTTPServer

class HealthCheckHandler(SimpleHTTPRequestHandler):
    """A minimal handler for a health check."""
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"Bot is running (Web server placeholder active).")

def run_web_server():
    """Starts the web server on the port specified by Render or default 8080."""
    port = int(os.environ.get("PORT", 8080))
    server_address = ('0.0.0.0', port)
    httpd = HTTPServer(server_address, HealthCheckHandler)
    print(f"Starting web server on port {port} for Render health check...")
    httpd.serve_forever()
# -----------------------------------------------

# Load environment variables
load_dotenv()

# --- CONFIGURATION & KNOWLEDGE BASE ---
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
CLIENT_ID = os.getenv('CLIENT_ID') 
ROBLOX_GROUP_ID = 32487083  # Stargame Studio Group ID
APPEAL_SERVER_LINK = "https://discord.gg/CFWv8fZnyY"

# Define the founder for command checks
FOUNDER_USERNAME = 'lionelclementofficial'
# Authorized users for staff announcements (founder + co-owner)
ANNOUNCEMENT_AUTHORS = ['niamaru87', FOUNDER_USERNAME]
STARGAME_DOMAINS = ["stargamestudio.com", f"roblox.com/groups/{ROBLOX_GROUP_ID}", APPEAL_SERVER_LINK.split('/')[-1]]

# The knowledge base (updated with payment fix)
STUDIO_KNOWLEDGE = (
    "Stargame Studio is a youth-powered ROBLOX development studio focused on creating immersive games (like Rampage Royale), "
    "UGC, 2D fashion, and artwork. We champion human artistry over AI art. "
    "Compensation: Active developers typically receive up to 10,000 Robux per project, plus a 2% revenue split. "
    "We use flexible payment methods including USD, ROBUX, revenue sharing, gift cards, and alternative methods. "
    "Rules: Be respectful, no harassment, follow directives from Owner (lionelclementofficial) and Co-Owner (niamaru87). "
    "Grounds for Termination: Violation of TOS (Stargame, Roblox, Discord), inappropriate conduct, insubordination, non-cooperation, prolonged inactivity, and unprofessional departure. "
    "Appeals are generally not available, but the appeal server is: " + APPEAL_SERVER_LINK + ". "
    "Roadmap: Late 2025 includes Relax Hangout and Veccera Cafe release. 2026 starts development on The Outbreak (Adventure/Horror). "
)

# Bot State Management (Non-persistent, will reset on bot restart)
MOD_STRIKES = {}          # Single counter for minor TOS violations (caps, gifs)
DOUBLE_COUNTER = {}       # Double counter for higher security offenses (raids, alts)
TASK_REMINDERS = {}       # {user_id: [{task, deadline_timestamp, original_setter}]}
WELCOME_SETTINGS = {
    'enabled': False,
    'channel_id': None,
    'welcome_message': "Welcome {member}, dream it, commission it, we build it! Use /help if you need assistance.",
    'goodbye_message': "Goodbye {member}, we hope to see you again soon!"
}

# Banner Images (Mocking the storage of image URLs for randomization)
BANNER_IMAGES = [
    "https://placehold.co/1200x400/0000FF/FFFFFF?text=SG+Studio+Banner+1", # Mock URL for uploaded:officialbanner.jpg
    "https://placehold.co/1200x400/2A2D43/FFFFFF?text=SG+Studio+Banner+2"  # Mock URL for uploaded:SGStudioBannerEdited.jpg
]


# --- BOT SETUP ---
intents = discord.Intents.default()
# Crucial intents for all the new features
intents.message_content = True 
intents.members = True 
intents.guilds = True
intents.typing = False # Optional, saves resources

bot = commands.Bot(command_prefix='!', intents=intents)

# --- GEMINI API FUNCTION (Modified to be more flexible) ---

async def generate_response(prompt: str, context: str, user: str = None):
    """Generates a text response using the Gemini API, combining context and prompt."""
    if not GEMINI_API_KEY:
        return "Error: Gemini API key not configured."

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent?key={GEMINI_API_KEY}"

    system_instruction = (
        f"You are Lagoona, the official, friendly, and expert support agent for 'Stargame Studio'. "
        f"Your response must be welcoming and interactive. Always try to be helpful and concise. "
        f"Context for Stargame Studio: {context}"
    )
    
    # Custom prompt for the AI to include user context
    full_prompt = (
        f"User ({user}) message/query: '{prompt}'. "
        "Please respond in a friendly, interactive, and enthusiastic tone. "
        "Acknowledge the user and then answer the question or offer assistance based on the provided context."
    )

    payload = {
        "contents": [{"parts": [{"text": full_prompt}]}],
        "systemInstruction": {"parts": [{"text": system_instruction}]},
    }
    
    async with aiohttp.ClientSession() as session:
        for i in range(3): 
            try:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        text = data.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', 'Oops! Lagoona is having a little trouble finding the exact answer right now. Could you rephrase your question?')
                        return text
                    elif response.status == 429:
                        await asyncio.sleep(2 ** i)
                        continue
                    else:
                        return f"API Error: Lagoona's connection is down (Status: {response.status})."
            except Exception:
                await asyncio.sleep(2 ** i)
                continue
        return "Lagoona is too busy right now. Please try again later."


# --- HELPER FUNCTIONS ---

def is_authorized(username: str) -> bool:
    """Checks if a username is in the authorized list (case-insensitive)."""
    return username.lower() in [name.lower() for name in ANNOUNCEMENT_AUTHORS]

def is_founder(username: str) -> bool:
    """Checks if the user is the founder."""
    return username.lower() == FOUNDER_USERNAME.lower()

async def add_announcement_reactions(message: discord.Message):
    """Adds the required reactions to an announcement message."""
    try:
        await message.add_reaction('💛') # :yellow_heart:
        await message.add_reaction('⭐') # :star:
        # discord.utils.get(message.guild.emojis, name='yah') # If custom emoji is used
        await message.add_reaction('🙌') # close enough for :yah:
    except Exception as e:
        print(f"Failed to add reactions: {e}")

async def apply_high_security_action(member: discord.Member, reason: str, is_alt: bool = False):
    """ASAP Mute, lock all access, and DM warning for high-security threats (Raids/Alts)."""
    user_id = member.id
    guild = member.guild
    
    # 1. Lock Access (Mute/Timeout)
    try:
        # Timeout the user for 1 hour to immediately stop raid activity
        await member.timeout(timedelta(hours=1), reason=reason)
        action_msg = f"🔒 **SECURITY ALERT!** {member.mention} has been placed in **ASAP Lockdown** (1h Timeout) for: **{reason}**."
    except discord.Forbidden:
        action_msg = f"❌ **SECURITY ALERT!** I cannot timeout {member.mention}. Please review my permissions. Reason: **{reason}**."
    
    # 2. Increment Double Counter
    DOUBLE_COUNTER[user_id] = DOUBLE_COUNTER.get(user_id, 0) + 1
    action_msg += f"\nDouble Counter Strike: **{DOUBLE_COUNTER[user_id]}**."
    
    # 3. DM Warning
    try:
        dm_prompt = f"A high security violation was detected from your account (Reason: {reason}). You have been placed in temporary lockdown. You have {DOUBLE_COUNTER[user_id]} security strike(s). If you believe this is an error or need to appeal, please join our appeal server: {APPEAL_SERVER_LINK}."
        dm_response = await generate_response(dm_prompt, f"Act as a serious, but fair, security bot for a developer studio. The user is in trouble. The appeal server is {APPEAL_SERVER_LINK}.", member.name)
        await member.send(dm_response)
        action_msg += "\n*User has been DMed with the warning and appeal link.*"
    except Exception:
        action_msg += "\n*(Could not DM user.)*"

    # Post security alert to system channel (or dedicated mod channel)
    if guild.system_channel:
        await guild.system_channel.send(action_msg)
        

# --- BOT EVENTS ---

@bot.event
async def on_ready():
    """Confirms the bot is logged in and starts scheduled tasks."""
    print(f'Logged in as {bot.user.name} ({bot.user.id})')
    
    if CLIENT_ID:
        try:
            await bot.tree.sync()
            print("Synced application commands globally.")
        except Exception as e:
            print(f"Failed to sync commands: {e}")
            
    if not daily_post_task.is_running():
        daily_post_task.start()
        
    if not task_reminder_task.is_running():
        task_reminder_task.start()

@bot.event
async def on_member_join(member):
    """Handles automated welcome and security checks (Alt/Raid prevention)."""
    
    # 1. High Security Check: Alt Account/Raid Detection
    account_age = datetime.now(tz=member.joined_at.tzinfo) - member.created_at
    if account_age < timedelta(minutes=5):
        reason = f"New account created only {account_age.seconds} seconds ago. Possible Alt/Raid Account."
        await apply_high_security_action(member, reason, is_alt=True)
        # Prevent welcome message for potential threat
        return 

    # 2. Welcome Message
    if WELCOME_SETTINGS['enabled'] and WELCOME_SETTINGS['channel_id']:
        channel = member.guild.get_channel(WELCOME_SETTINGS['channel_id'])
        if channel:
            welcome_text = WELCOME_SETTINGS['welcome_message'].replace('{member}', member.mention)
            await channel.send(welcome_text)

@bot.event
async def on_member_remove(member):
    """Handles goodbye messages."""
    if WELCOME_SETTINGS['enabled'] and WELCOME_SETTINGS['channel_id']:
        channel = member.guild.get_channel(WELCOME_SETTINGS['channel_id'])
        if channel:
            goodbye_text = WELCOME_SETTINGS['goodbye_message'].replace('{member}', member.name)
            await channel.send(goodbye_text)

@bot.event
async def on_message(message):
    """Handles keyword response, moderation, and DM support."""
    if message.author.bot:
        return

    # --- DM Support (Customer Support in DMs) ---
    if isinstance(message.channel, discord.DMChannel):
        if 'lagoona' in message.content.lower():
            await message.channel.send("👋 **Hello!** Lagoona is activating support for you...")
        
        prompt = message.content
        context = STUDIO_KNOWLEDGE + f"\n\n**Special Instruction:** The user is contacting you in a private message. Advise them that if they are looking to appeal a ban or kick, they must use the appeal server link: {APPEAL_SERVER_LINK}"
        
        response_text = await generate_response(prompt, context, message.author.name)
        await message.channel.send(response_text)
        return # Stop processing DMs

    # --- Server Moderation & Keyword Response ---
    content = message.content.lower()
    
    # 1. Moderation: Check for minor TOS violations
    is_violation = False
    reason = None
    
    if is_excessive_caps(message.content):
        is_violation = True
        reason = "Excessive capitalization (TOS violation)."

    if is_gif_post(message):
        is_violation = True
        reason = "Posting unsolicited GIFs (TOS violation)."

    if is_violation:
        try:
            await message.delete() 
            await apply_moderation_action(message.author, message.channel, reason, action='warn')
        except discord.Forbidden:
             await message.channel.send("⚠️ Cannot moderate this message due to missing permissions. Please fix bot permissions.", delete_after=5)
        return 

    # 2. Lagoona Keyword Response
    if 'lagoona' in content or '/help' in content: # Trigger also if /help is used
        if 'lagoona' in content:
            await message.channel.send(f"Activating support for {message.author.mention}. Please wait while Lagoona processes your request...")
            
        response_text = await generate_response(message.content, STUDIO_KNOWLEDGE, message.author.name)
        await message.channel.send(response_text)

    await bot.process_commands(message) 

# --- SLASH COMMANDS ---

# Re-defining moderation helpers here for visibility
def is_excessive_caps(content: str) -> bool:
    if len(content) < 10: return False
    uppercase_count = sum(1 for char in content if char.isupper() and char.isalpha())
    alpha_count = sum(1 for char in content if char.isalpha())
    if alpha_count < 5: return False
    return (uppercase_count / alpha_count) > 0.60

def is_gif_post(message: discord.Message) -> bool:
    gif_keywords = ['tenor.com', 'giphy.com', '.gif']
    content_lower = message.content.lower()
    return any(k in content_lower for k in gif_keywords) or any(embed.type == 'gifv' for embed in message.embeds)

async def apply_moderation_action(member: discord.Member, channel: discord.TextChannel, reason: str, action: str = 'warn'):
    user_id = member.id
    STRIKE_WARN, STRIKE_MUTE, STRIKE_KICK = 1, 3, 5
    
    MOD_STRIKES[user_id] = MOD_STRIKES.get(user_id, 0) + 1
    strikes = MOD_STRIKES[user_id]
    
    mod_message = ""
    
    if strikes == STRIKE_WARN:
        mod_message = f"🚨 **WARNING** {member.mention}: {reason}. Strike **{strikes}/{STRIKE_KICK}**."
    elif strikes == STRIKE_MUTE:
        mod_message = f"🔇 **MUTE ALERT** {member.mention}: You've reached **{strikes} strikes**. You are muted for 15 minutes."
        try:
            await member.timeout(timedelta(minutes=15), reason=reason)
        except discord.Forbidden:
            mod_message += "\n(Error: Cannot apply Mute/Timeout due to missing permissions.)"
    elif strikes >= STRIKE_KICK:
        try:
            mod_message = f"👋 **KICK** {member.mention}: Maximum strikes reached (**{strikes}**). You are being kicked as per TOS."
            await member.kick(reason=f"Automated moderation for repeated violations: {reason}")
            del MOD_STRIKES[user_id] 
        except discord.Forbidden:
            mod_message += "\n(Error: Cannot apply Kick due to missing permissions.)"
    else:
        mod_message = f"⚠️ **NOTICE** {member.mention}: Strike count updated to **{strikes}** for {reason}."
        
    await channel.send(mod_message)

@bot.tree.command(name="announcement", description="Post a staff announcement with custom title and reactions.")
@discord.app_commands.describe(
    title="The banner title for the announcement.",
    message="The main message content for the announcement.",
    image_url="Optional: URL of an image for the banner. Leave empty for a random Stargame banner."
)
async def announcement_command(interaction: discord.Interaction, title: str, message: str, image_url: str = None):
    """Allows only authorized users to post an announcement with customization."""
    author_username = interaction.user.name 

    if is_authorized(author_username):
        
        # Determine footer and image
        footer_text = "Authorized Message by lionelclementofficial" if is_founder(author_username) else "Authorized Message by Stargame Studio Staff"
        final_image_url = image_url if image_url else random.choice(BANNER_IMAGES)
        
        embed = discord.Embed(
            title=f"📣 {title}",
            description=message,
            color=discord.Color.blue()
        )
        embed.set_image(url=final_image_url)
        embed.set_footer(text=footer_text)
        
        await interaction.response.send_message("Announcement pending! Posting now...", ephemeral=True) 
        
        public_message = await interaction.channel.send("@everyone", embed=embed) 

        # Add reactions if @everyone or @Community Member (mocked role mention) is in the message
        if "@everyone" in message or "@community member" in message.lower():
            await add_announcement_reactions(public_message)
    else:
        await interaction.response.send_message(
            f"🚫 Access Denied. Only authorized staff ({', '.join(ANNOUNCEMENT_AUTHORS)}) can use this command.",
            ephemeral=True
        )

# --- Welcome/Goodbye Command ---
@bot.tree.command(name="set_welcome_goodbye", description="Set up or disable welcome and goodbye messages.")
@discord.app_commands.describe(
    action="Enable or disable the messages.",
    channel="The channel for the messages.",
    welcome_msg="New member message (use {member} as placeholder).",
    goodbye_msg="Leaving member message (use {member} as placeholder)."
)
async def set_welcome_goodbye_command(interaction: discord.Interaction, action: str, channel: discord.TextChannel = None, welcome_msg: str = None, goodbye_msg: str = None):
    """Enables/disables and configures the welcome/goodbye system."""
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("You must be an administrator to manage welcome messages.", ephemeral=True)

    action = action.lower()
    if action == 'enable':
        if not channel:
            return await interaction.response.send_message("You must specify a channel to enable the feature.", ephemeral=True)
            
        WELCOME_SETTINGS['enabled'] = True
        WELCOME_SETTINGS['channel_id'] = channel.id
        if welcome_msg:
             WELCOME_SETTINGS['welcome_message'] = welcome_msg
        if goodbye_msg:
             WELCOME_SETTINGS['goodbye_message'] = goodbye_msg

        await interaction.response.send_message(
            f"✅ Welcome/Goodbye messages **enabled** in {channel.mention}.\nWelcome: `{WELCOME_SETTINGS['welcome_message']}`\nGoodbye: `{WELCOME_SETTINGS['goodbye_message']}`",
            ephemeral=True
        )
    elif action == 'disable':
        WELCOME_SETTINGS['enabled'] = False
        WELCOME_SETTINGS['channel_id'] = None
        await interaction.response.send_message("❌ Welcome/Goodbye messages **disabled**.", ephemeral=True)
    else:
        await interaction.response.send_message("Invalid action. Use 'enable' or 'disable'.", ephemeral=True)


# --- Task Management Commands ---

@bot.tree.command(name="settask", description="Assign a task and deadline to a user.")
@discord.app_commands.describe(
    user="The user receiving the task.",
    task="The task description.",
    deadline="The deadline (YYYY-MM-DD HH:MM format, e.g., 2025-10-30 14:00)."
)
async def set_task_command(interaction: discord.Interaction, user: discord.Member, task: str, deadline: str):
    """Allows staff to set a task with a deadline."""
    if not is_authorized(interaction.user.name):
        return await interaction.response.send_message("🚫 Only authorized staff can manage tasks.", ephemeral=True)

    try:
        deadline_dt = datetime.strptime(deadline, '%Y-%m-%d %H:%M')
        
        user_id = user.id
        if user_id not in TASK_REMINDERS:
            TASK_REMINDERS[user_id] = []
            
        TASK_REMINDERS[user_id].append({
            'task': task,
            'deadline': deadline_dt,
            'original_setter': interaction.user.name,
            'status': 'In Progress'
        })
        
        await interaction.response.send_message(
            f"✅ Task assigned to {user.mention} with deadline **{deadline_dt.strftime('%Y-%m-%d %H:%M')}**.\nTask: `{task}`",
            ephemeral=False # Post publicly for accountability
        )
    except ValueError:
        await interaction.response.send_message(
            "❌ Invalid deadline format. Please use **YYYY-MM-DD HH:MM** (e.g., 2025-10-30 14:00).", 
            ephemeral=True
        )

@bot.tree.command(name="completetask", description="Mark a task as complete for a user.")
@discord.app_commands.describe(user="The user who completed the task.")
async def complete_task_command(interaction: discord.Interaction, user: discord.Member):
    if not is_authorized(interaction.user.name):
        return await interaction.response.send_message("🚫 Only authorized staff can manage tasks.", ephemeral=True)
        
    user_id = user.id
    if user_id in TASK_REMINDERS and TASK_REMINDERS[user_id]:
        # Find the oldest pending task
        pending_task = TASK_REMINDERS[user_id].pop(0) 
        
        await interaction.response.send_message(
            f"🎉 Task completed! {user.mention} has finished: **{pending_task['task']}**.",
            ephemeral=False
        )
        if not TASK_REMINDERS[user_id]:
            del TASK_REMINDERS[user_id]
    else:
        await interaction.response.send_message(f"❌ {user.mention} has no active tasks.", ephemeral=True)

@bot.tree.command(name="extendedtask", description="Extend the deadline for a user's task.")
@discord.app_commands.describe(
    user="The user whose task deadline to extend.",
    new_deadline="The new deadline (YYYY-MM-DD HH:MM format)."
)
async def extended_task_command(interaction: discord.Interaction, user: discord.Member, new_deadline: str):
    if not is_authorized(interaction.user.name):
        return await interaction.response.send_message("🚫 Only authorized staff can manage tasks.", ephemeral=True)
        
    user_id = user.id
    if user_id in TASK_REMINDERS and TASK_REMINDERS[user_id]:
        try:
            new_deadline_dt = datetime.strptime(new_deadline, '%Y-%m-%d %H:%M')
            TASK_REMINDERS[user_id][0]['deadline'] = new_deadline_dt
            
            await interaction.response.send_message(
                f"⏱️ Task deadline for {user.mention} has been extended to **{new_deadline}**.",
                ephemeral=False
            )
        except ValueError:
            await interaction.response.send_message("❌ Invalid deadline format. Please use **YYYY-MM-DD HH:MM**.", ephemeral=True)
    else:
        await interaction.response.send_message(f"❌ {user.mention} has no active tasks to extend.", ephemeral=True)

@bot.tree.command(name="incompletetask", description="Mark a task as incomplete/failed for a user.")
@discord.app_commands.describe(user="The user who failed the task.")
async def incomplete_task_command(interaction: discord.Interaction, user: discord.Member):
    if not is_authorized(interaction.user.name):
        return await interaction.response.send_message("🚫 Only authorized staff can manage tasks.", ephemeral=True)
        
    user_id = user.id
    if user_id in TASK_REMINDERS and TASK_REMINDERS[user_id]:
        failed_task = TASK_REMINDERS[user_id].pop(0)
        
        await interaction.response.send_message(
            f"❌ Task marked as INCOMPLETE for {user.mention}: **{failed_task['task']}**. Staff will follow up.",
            ephemeral=False
        )
        if not TASK_REMINDERS[user_id]:
            del TASK_REMINDERS[user_id]
    else:
        await interaction.response.send_message(f"❌ {user.mention} has no active tasks.", ephemeral=True)

@bot.tree.command(name="forwardedtask", description="Forward a task to a new user.")
@discord.app_commands.describe(
    old_user="The user the task is being taken from.",
    new_user="The user the task is being forwarded to."
)
async def forwarded_task_command(interaction: discord.Interaction, old_user: discord.Member, new_user: discord.Member):
    if not is_authorized(interaction.user.name):
        return await interaction.response.send_message("🚫 Only authorized staff can manage tasks.", ephemeral=True)
        
    old_user_id = old_user.id
    new_user_id = new_user.id

    if old_user_id in TASK_REMINDERS and TASK_REMINDERS[old_user_id]:
        task_to_forward = TASK_REMINDERS[old_user_id].pop(0)
        
        if new_user_id not in TASK_REMINDERS:
            TASK_REMINDERS[new_user_id] = []
            
        TASK_REMINDERS[new_user_id].append(task_to_forward)

        await interaction.response.send_message(
            f"➡️ Task successfully forwarded from {old_user.mention} to {new_user.mention}.\nTask: `{task_to_forward['task']}` (Deadline: {task_to_forward['deadline'].strftime('%Y-%m-%d %H:%M')}).",
            ephemeral=False
        )
        if not TASK_REMINDERS[old_user_id]:
            del TASK_REMINDERS[old_user_id]
    else:
        await interaction.response.send_message(f"❌ {old_user.mention} has no active tasks to forward.", ephemeral=True)


# --- Scheduled Task for Task Reminders ---
@tasks.loop(minutes=5)
async def task_reminder_task():
    """Checks for upcoming deadlines and sends reminders."""
    for user_id, tasks_list in list(TASK_REMINDERS.items()):
        member = bot.get_user(user_id)
        if not member:
            del TASK_REMINDERS[user_id]
            continue
            
        for task_item in list(tasks_list):
            time_until_deadline = task_item['deadline'] - datetime.now()
            
            # Reminder 1: 12 hours before
            if timedelta(hours=11, minutes=55) <= time_until_deadline <= timedelta(hours=12, minutes=5):
                reminder_prompt = f"Friendly reminder for {member.name}: Your task '{task_item['task']}' is due in approximately 12 hours at {task_item['deadline'].strftime('%Y-%m-%d %H:%M')}."
                reminder_message = await generate_response(reminder_prompt, "Act as a friendly productivity assistant.", member.name)
                try:
                    await member.send(reminder_message)
                except Exception:
                    pass # Cannot DM user

            # Reminder 2: Deadline reached
            elif time_until_deadline <= timedelta(minutes=0):
                # Deadline met/passed - send final warning and remove
                tasks_list.remove(task_item)
                
                final_prompt = f"The deadline for your task '{task_item['task']}' has passed! Please use `/completetask` or notify staff (Setter: {task_item['original_setter']}) immediately."
                final_message = await generate_response(final_prompt, "Act as an urgent, professional notice bot.", member.name)
                
                try:
                    await member.send(final_message)
                except Exception:
                    pass
                
                # Notify original setter (if possible)
                for guild in bot.guilds:
                    setter = discord.utils.get(guild.members, name=task_item['original_setter'])
                    if setter:
                        try:
                            await setter.send(f"⚠️ **DEADLINE ALERT:** Task '{task_item['task']}' for {member.name} has passed.")
                        except Exception:
                            pass
                
        if not tasks_list:
            del TASK_REMINDERS[user_id]


# --- Founder Only Commands ---

@bot.tree.command(name="revampallusernames", description="[FOUNDER ONLY] Revamp all server members' nicknames.")
@discord.app_commands.describe(nickname_prefix="The prefix/template for the new nicknames (e.g., 'SG | {name}').")
async def revamp_usernames_command(interaction: discord.Interaction, nickname_prefix: str):
    """Allows founder to set nicknames for all members."""
    if not is_founder(interaction.user.name):
        return await interaction.response.send_message("🚫 **ACCESS DENIED.** Only the founder can use this command.", ephemeral=True)

    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild
    success_count = 0
    fail_count = 0
    
    for member in guild.members:
        if member.bot:
            continue
            
        # Create smart nickname (e.g., first word of username + discriminator)
        base_name = member.name.split(' ')[0]
        new_nickname = nickname_prefix.replace('{name}', base_name)
        
        try:
            # Check if bot has permission and role hierarchy is lower
            if member.top_role < guild.me.top_role:
                await member.edit(nick=new_nickname)
                success_count += 1
        except discord.Forbidden:
            fail_count += 1
        except Exception:
            fail_count += 1

    await interaction.followup.send(
        f"✅ **Username Revamp Complete!** Successfully updated **{success_count}** nicknames. Failed to update {fail_count} (likely due to role hierarchy/permissions).", 
        ephemeral=False
    )

@bot.tree.command(name="verifyallmembers", description="[STAFF ONLY] Check all members for Roblox Group membership and ping non-members.")
async def verify_all_members_command(interaction: discord.Interaction):
    """Pings users not in the specified Roblox Group (MOCK function)."""
    if not is_authorized(interaction.user.name):
        return await interaction.response.send_message("🚫 Only authorized staff can run mass verification checks.", ephemeral=True)

    await interaction.response.defer()
    
    # --- MOCKING Roblox API Check ---
    # NOTE: Real implementation requires an external API call to check group membership.
    # We will simulate the check here.
    
    non_members = []
    
    # Simulate finding 5 random non-verified users (in a real app, this list comes from an API)
    for member in interaction.guild.members:
        if not member.bot and random.random() < 0.05 and len(non_members) < 5: 
            non_members.append(member.mention)

    if non_members:
        non_members_list = ", ".join(non_members)
        ping_message = (
            f"🔔 **Attention!** The following members appear to be missing from the **Stargame Studio Roblox Group (ID: {ROBLOX_GROUP_ID})** or are unverified: {non_members_list}\n\n"
            "Please **join the group** and use `/verify` to link your Roblox account with Discord to ensure you have full access to community roles!"
        )
        await interaction.followup.send(ping_message)
    else:
        await interaction.followup.send("✅ All active members seem verified or the check is complete (No non-members found in this sweep).", ephemeral=False)


# --- START THE BOT ---
if __name__ == "__main__":
    if not DISCORD_TOKEN or not GEMINI_API_KEY or not CLIENT_ID:
        print("\n--- CRITICAL ERROR: REQUIRED ENVIRONMENT VARIABLES MISSING ---")
        print("Please ensure DISCORD_TOKEN, GEMINI_API_KEY, and CLIENT_ID are set.")
    else:
        # Start the web server in a separate thread to keep Render happy
        # while the bot runs in the main thread
        web_server_thread = threading.Thread(target=run_web_server)
        web_server_thread.daemon = True # Daemon thread exits when the main program ends
        web_server_thread.start()
        
        # Run the Discord bot
        bot.run(DISCORD_TOKEN)
