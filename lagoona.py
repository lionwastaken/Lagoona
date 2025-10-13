import discord
from discord.ext import commands, tasks
import aiohttp
import os
import asyncio
import random
from datetime import time, datetime, timedelta
from dotenv import load_dotenv
import threading 
from http.server import SimpleHTTPRequestHandler, HTTPServer
import json

# --- Render/Uptime Fix: Simple Web Server ---

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

# Studio Specific Configs
ROBLOX_GROUP_ID = 32487083  # Stargame Studio Group ID
APPEAL_SERVER_LINK = "https://discord.gg/CFWv8fZnyY" # Mock link
# Authorized users for staff announcements (founder + co-owner + head staff)
FOUNDER_USERNAME = 'lionelclementofficial'
ANNOUNCEMENT_AUTHORS = ['niamaru87', FOUNDER_USERNAME, 'whiteboard'] # Added Whiteboard
STARGAME_DOMAINS = ["stargamestudio.com", f"roblox.com/groups/{ROBLOX_GROUP_ID}"]

# Banner Images (Using the uploaded file names as mock URLs for the two banners)
BANNER_IMAGES = [
    "https://placehold.co/1200x400/0000FF/FFFFFF?text=SG+Official+Banner+1", # Mock for officialbanner.jpg
    "https://placehold.co/1200x400/2A2D43/FFFFFF?text=SG+Edited+Banner+2"  # Mock for SGStudioBannerEdited.jpg
]

# The consolidated knowledge base
STUDIO_KNOWLEDGE = (
    "Stargame Studio is a youth-powered ROBLOX development studio. Motto: Dream it, commission it, we build it... with passion, quality, and heart! "
    "**Lagoona's Creator/Designer: Miyah (Instagram: https://www.instagram.com/miyahs.sb/)** and she created the OC Lagoona. "
    "Vision: To be a beloved creative force, first adored by the ROBLOX community, then the wider gaming/tech world. "
    "Mission: Make a Positive Impact, Listen & Respond, Help & Support, Build a Dream Team Environment, Champion Quality & Entertainment, Educate & Empower, Prioritize Well-being. "
    "Output Focus: Engaging Games (Rampage Royale, Relax Hangout, Veccera Cafe, The Outbreak), Trendsetting Assets (2D clothes, UGC), Informative Content, and a Positive Community Space. "
    "Compensation: Active developers typically receive up to 10,000 Robux per project, plus a 2% revenue split. Flexible payment methods (USD, ROBUX, revenue sharing, gift cards, etc.) are used. "
    "Rules: Be respectful, no harassment, follow directives. "
    "**Key Staff & Artists:** "
    "**Head Staff:** Niamaru87, Whiteboard. "
    "**Other Staff:** Snowy, Kleffy_Gamin. "
    "**Artists:** polarplatypus, angfry, honeypah, poleyz, Linda. "
    "**Other Key Staff:** crystalcat057_24310 (Clothes Designer/Storywriter/Tester), cigerds (Best Lead Artist), lladybug. (Voice Actress), stavrosmichalatos (SFX Composer), midnightangel05_11 (Scripter), rashesmcfluff (Animator), toihou (Modeler), cleonagoesblublub (Next in Lead Artists). "
    f"Roblox Group: https://www.roblox.com/communities/{ROBLOX_GROUP_ID}/Stargame-Studio "
)

# Bot State Management (Non-persistent)
MOD_STRIKES = {}          
DOUBLE_COUNTER = {}       
TASK_REMINDERS = {}       
WELCOME_SETTINGS = {
    'enabled': False,
    'channel_id': None,
    'welcome_message': "Welcome {member}, dream it, commission it, we build it! Use /help if you need assistance.",
    'goodbye_message': "Goodbye {member}, we hope to see you again soon!"
}

DAILY_POST_SETTINGS = {
    'channel_id': None,
    'time': time(hour=10, minute=0) # 10:00 AM UTC default
}

ANNOUNCE_POST_SETTINGS = {
    'platform_settings': {} # {platform: {channel_id: int, enabled: bool, link: str}}
}

LEVEL_UP_SETTINGS = {
    'enabled': False,
    'channel_id': None,
    'xp_per_message': 15,
    'xp_per_reaction': 5,
    'xp_per_vc_minute': 10
}

USER_LEVELS = {} # {user_id: {'xp': int, 'level': int}}

# XP Utility function
def get_level_for_xp(xp):
    """Calculates level based on XP (simple progression: Level = floor(sqrt(XP / 100)))"""
    return int((xp / 100) ** 0.5)

# --- BOT SETUP ---
intents = discord.Intents.default()
intents.message_content = True 
intents.members = True 
intents.guilds = True
intents.voice_states = True # Required for VC activity tracking
intents.typing = False 

bot = commands.Bot(command_prefix='!', intents=intents)

# --- GEMINI API FUNCTION ---

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
    
    full_prompt = (
        f"User ({user}) message/query: '{prompt}'. "
        "Please respond in a friendly, interactive, and enthusiastic tone. "
        "Acknowledge the user and then answer the question or offer assistance based on the provided context."
    )

    payload = {
        "contents": [{"parts": [{"text": full_prompt}]}],
        "systemInstruction": {"parts": [{"text": system_instruction}]},
    }
    
    # Simple retry logic with exponential backoff
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
                        error_details = await response.text()
                        print(f"Gemini API Non-200 Error: {response.status} - {error_details}")
                        return f"API Error: Lagoona's connection is down (Status: {response.status})."
            except Exception as e:
                print(f"Gemini API Request Failed (Attempt {i+1}): {e}")
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
        await message.add_reaction('🙌') # Mock for :yah:
    except Exception as e:
        print(f"Failed to add reactions: {e}")

# --- BOT EVENTS ---

@bot.event
async def on_ready():
    """Confirms the bot is logged in and starts scheduled tasks."""
    print(f'Logged in as {bot.user.name} ({bot.user.id})')
    
    if CLIENT_ID:
        try:
            # Syncing global commands
            await bot.tree.sync()
            print("Synced application commands globally. Please allow a few minutes for Discord to update the list.")
        except Exception as e:
            print(f"Failed to sync commands: {e}")
            
    if not daily_post_task.is_running():
        daily_post_task.start()
        
    if not task_reminder_task.is_running():
        task_reminder_task.start()
        
    if not vc_xp_task.is_running():
        vc_xp_task.start()

@bot.event
async def on_member_join(member):
    """Handles automated welcome and security checks."""
    
    # 1. Welcome Message
    if WELCOME_SETTINGS['enabled'] and WELCOME_SETTINGS['channel_id']:
        channel = member.guild.get_channel(WELCOME_SETTINGS['channel_id'])
        if channel:
            welcome_text = WELCOME_SETTINGS['welcome_message'].replace('{member}', member.mention)
            
            # Send the welcome message with a random banner image
            embed = discord.Embed(
                title="✨ Welcome to Stargame Studio! ✨",
                description=welcome_text,
                color=discord.Color.blue()
            )
            embed.set_image(url=random.choice(BANNER_IMAGES))
            
            await channel.send(member.mention, embed=embed)
    
    # Initialize user in the level system
    USER_LEVELS[member.id] = USER_LEVELS.get(member.id, {'xp': 0, 'level': 0})

@bot.event
async def on_member_remove(member):
    """Handles goodbye messages."""
    if WELCOME_SETTINGS['enabled'] and WELCOME_SETTINGS['channel_id']:
        channel = member.guild.get_channel(WELCOME_SETTINGS['channel_id'])
        if channel:
            goodbye_text = WELCOME_SETTINGS['goodbye_message'].replace('{member}', member.name)
            
            # Send the goodbye message with a random banner image
            embed = discord.Embed(
                title="👋 Goodbye, Star!",
                description=goodbye_text,
                color=discord.Color.dark_blue()
            )
            embed.set_image(url=random.choice(BANNER_IMAGES))
            
            await channel.send(embed=embed)


@bot.event
async def on_message(message):
    """Handles keyword response, moderation, and XP."""
    if message.author.bot:
        return

    # --- DM Support ---
    if isinstance(message.channel, discord.DMChannel):
        if 'lagoona' in message.content.lower():
            await message.channel.send("👋 **Hello!** Lagoona is activating support for you...")
        
        prompt = message.content
        dm_context = f"You are Lagoona, the professional and supportive DM customer service agent for Stargame Studio. The appeal server is {APPEAL_SERVER_LINK}. Remember Miyah created you."
        response_text = await generate_response(prompt, dm_context, message.author.name)
        await message.channel.send(response_text)
        return # Stop processing DMs

    # --- Server Moderation & XP (Simplified for brevity) ---
    content = message.content.lower()
    
    # 1. Level Up XP for Message
    if LEVEL_UP_SETTINGS['enabled']:
        user_id = message.author.id
        USER_LEVELS[user_id] = USER_LEVELS.get(user_id, {'xp': 0, 'level': 0})
        
        current_xp = USER_LEVELS[user_id]['xp']
        current_level = USER_LEVELS[user_id]['level']
        
        # Add message XP
        new_xp = current_xp + LEVEL_UP_SETTINGS['xp_per_message']
        new_level = get_level_for_xp(new_xp)
        
        USER_LEVELS[user_id]['xp'] = new_xp
        USER_LEVELS[user_id]['level'] = new_level
        
        # Check for level up
        if new_level > current_level:
            level_channel = bot.get_channel(LEVEL_UP_SETTINGS['channel_id'])
            if level_channel:
                 # Send level up message with a random banner image
                 embed = discord.Embed(
                     title=f"⭐ LEVEL UP: Level {new_level} Reached! ⭐",
                     description=f"🎉 **Congratulations** {message.author.mention}! You've reached Level **{new_level}**! Keep creating, building, and designing!",
                     color=discord.Color.gold()
                 )
                 embed.set_image(url=random.choice(BANNER_IMAGES))
                 
                 await level_channel.send(embed=embed)


    # 2. Lagoona Keyword Response
    if 'lagoona' in content: 
        await message.channel.send(f"Activating support for {message.author.mention}. Please wait while Lagoona processes your request...")
            
        response_text = await generate_response(message.content, STUDIO_KNOWLEDGE, message.author.name)
        await message.channel.send(response_text)
    
    # Ensure commands are processed after message content checks
    await bot.process_commands(message) 

@bot.event
async def on_reaction_add(reaction, user):
    """Handles XP for adding reactions."""
    if user.bot or not LEVEL_UP_SETTINGS['enabled']:
        return
    
    user_id = user.id
    USER_LEVELS[user_id] = USER_LEVELS.get(user_id, {'xp': 0, 'level': 0})
    
    current_xp = USER_LEVELS[user_id]['xp']
    current_level = USER_LEVELS[user_id]['level']
    
    # Add reaction XP
    new_xp = current_xp + LEVEL_UP_SETTINGS['xp_per_reaction']
    new_level = get_level_for_xp(new_xp)
    
    USER_LEVELS[user_id]['xp'] = new_xp
    USER_LEVELS[user_id]['level'] = new_level
    
    # Check for level up
    if new_level > current_level:
        level_channel = bot.get_channel(LEVEL_UP_SETTINGS['channel_id'])
        if level_channel:
             # Send level up message with a random banner image
             embed = discord.Embed(
                 title=f"⭐ LEVEL UP: Level {new_level} Reached! ⭐",
                 description=f"🎉 **Congratulations** {user.mention}! You've reached Level **{new_level}** from reacting to a message!",
                 color=discord.Color.gold()
             )
             embed.set_image(url=random.choice(BANNER_IMAGES))
             
             await level_channel.send(embed=embed)


# --- TASK SCHEDULERS ---

@tasks.loop(minutes=1)
async def vc_xp_task():
    """Gives XP for every minute spent in a voice channel."""
    if not LEVEL_UP_SETTINGS['enabled']:
        return

    xp_per_min = LEVEL_UP_SETTINGS['xp_per_vc_minute']
    
    for guild in bot.guilds:
        for member in guild.members:
            # Check if user is in a voice channel, is not a bot, and is not muted/deafened (active)
            if member.voice and member.voice.channel and not member.bot and not member.voice.self_mute and not member.voice.self_deaf:
                user_id = member.id
                USER_LEVELS[user_id] = USER_LEVELS.get(user_id, {'xp': 0, 'level': 0})
                
                current_xp = USER_LEVELS[user_id]['xp']
                current_level = USER_LEVELS[user_id]['level']
                
                new_xp = current_xp + xp_per_min
                new_level = get_level_for_xp(new_xp)
                
                USER_LEVELS[user_id]['xp'] = new_xp
                USER_LEVELS[user_id]['level'] = new_level
                
                # Check for level up
                if new_level > current_level:
                    level_channel = bot.get_channel(LEVEL_UP_SETTINGS['channel_id'])
                    if level_channel:
                         # Send level up message with a random banner image
                         embed = discord.Embed(
                             title=f"⭐ LEVEL UP: Level {new_level} Reached! ⭐",
                             description=f"🎉 **Congratulations** {member.mention}! You've reached Level **{new_level}** for being active in a voice channel!",
                             color=discord.Color.gold()
                         )
                         embed.set_image(url=random.choice(BANNER_IMAGES))
                         
                         await level_channel.send(embed=embed)


@tasks.loop(time=DAILY_POST_SETTINGS['time'])
async def daily_post_task():
    """Generates and posts a daily quote or question to encourage engagement."""
    
    channel_id = DAILY_POST_SETTINGS['channel_id']
    if not channel_id:
        return 

    channel = bot.get_channel(channel_id)
    if not channel:
        return 

    is_question = random.choice([True, False])
    
    if is_question:
        prompt = "Generate a single, engaging, and thoughtful question for a developer community (Stargame Studio) about game design, future tech, or creative work. Start the response with '❓ Daily Question:'"
    else:
        prompt = "Generate a single, motivating, and concise quote about creativity, teamwork, or development. Attribute it to a fictional 'Lagoona' or a famous tech/creative figure. Start the response with '⭐ Daily Quote:'"
        
    context = STUDIO_KNOWLEDGE + "\n\n**Special Instruction:** Ensure the output is *only* the quote/question and its attribution, ready to be posted directly. Do not include any extra conversation or formatting."
    
    post_content = await generate_response(prompt, context, "System Bot")

    embed = discord.Embed(
        title="✨ Stargame Studio Daily Engagement ✨",
        description=post_content,
        color=discord.Color.purple()
    )
    # Add a random banner to the daily post
    embed.set_image(url=random.choice(BANNER_IMAGES)) 

    try:
        message = await channel.send("@everyone", embed=embed)
        await add_announcement_reactions(message)
    except discord.Forbidden:
        print(f"Failed to send daily post to channel {channel_id} (Forbidden).")


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
                    pass 

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

# --- SLASH COMMANDS ---

# --- Level Up System Commands ---
@bot.tree.command(name="levelup", description="[STAFF ONLY] Set up or disable the level-up system.")
@discord.app_commands.describe(
    action="Enable or disable the system.",
    channel="The channel where level-up notifications are posted."
)
async def levelup_command(interaction: discord.Interaction, action: str, channel: discord.TextChannel = None):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("🚫 You must be an administrator to manage the level-up system.", ephemeral=True)

    action = action.lower()
    if action == 'enable':
        if not channel:
            return await interaction.response.send_message("You must specify a channel to enable the feature.", ephemeral=True)
            
        LEVEL_UP_SETTINGS['enabled'] = True
        LEVEL_UP_SETTINGS['channel_id'] = channel.id
        await interaction.response.send_message(
            f"✅ Level-up system **enabled** in {channel.mention}. XP gained from messages, reactions, and VC activity.",
            ephemeral=True
        )
    elif action == 'disable':
        LEVEL_UP_SETTINGS['enabled'] = False
        LEVEL_UP_SETTINGS['channel_id'] = None
        await interaction.response.send_message("❌ Level-up system **disabled**.", ephemeral=True)
    else:
        await interaction.response.send_message("Invalid action. Use 'enable' or 'disable'.", ephemeral=True)

@bot.tree.command(name="rank", description="Check your current level and XP.")
async def rank_command(interaction: discord.Interaction, user: discord.Member = None):
    target = user if user else interaction.user
    user_data = USER_LEVELS.get(target.id, {'xp': 0, 'level': 0})
    
    xp = user_data['xp']
    level = user_data['level']
    xp_for_next = (level + 1) ** 2 * 100
    
    embed = discord.Embed(
        title=f"⭐ {target.name}'s Rank ⭐",
        description=f"Level: **{level}**\nXP: **{xp}**\nNext Level at: **{xp_for_next}** XP",
        color=discord.Color.gold()
    )
    embed.set_footer(text="Keep participating to rank up!")
    await interaction.response.send_message(embed=embed, ephemeral=False)

# --- Social Media Announcement Command ---
@bot.tree.command(name="announceforposts", description="[STAFF ONLY] Configure automated social media post announcements.")
@discord.app_commands.describe(
    platform="The social media platform.",
    action="Enable or disable announcements for this platform.",
    channel="The channel for the announcement.",
    link="The main profile link for this platform."
)
@discord.app_commands.choices(
    platform=[
        discord.app_commands.Choice(name="YouTube", value="youtube"),
        discord.app_commands.Choice(name="Instagram", value="instagram"),
        discord.app_commands.Choice(name="Twitter", value="twitter"),
        discord.app_commands.Choice(name="TikTok", value="tiktok"),
        discord.app_commands.Choice(name="All", value="all"),
    ],
    action=[
        discord.app_commands.Choice(name="Enable", value="enable"),
        discord.app_commands.Choice(name="Disable", value="disable"),
    ]
)
async def announce_for_posts_command(interaction: discord.Interaction, platform: str, action: str, channel: discord.TextChannel = None, link: str = None):
    if not is_authorized(interaction.user.name):
        return await interaction.response.send_message("🚫 Only authorized staff can set up post announcements.", ephemeral=True)

    platforms = [platform] if platform != 'all' else ['youtube', 'instagram', 'twitter', 'tiktok']
    
    if action == 'enable' and (not channel or not link):
        return await interaction.response.send_message(
            "❌ To enable, you must specify a **channel** and a **profile link**.", 
            ephemeral=True
        )

    for p in platforms:
        if action == 'enable':
            ANNOUNCE_POST_SETTINGS['platform_settings'][p] = {
                'channel_id': channel.id,
                'enabled': True,
                'link': link
            }
        elif action == 'disable':
            if p in ANNOUNCE_POST_SETTINGS['platform_settings']:
                ANNOUNCE_POST_SETTINGS['platform_settings'][p]['enabled'] = False

    message = f"✅ Post announcements for **{platform.upper()}** have been **{action.upper()}D**."
    if action == 'enable' and channel:
         message += f" (Channel: {channel.mention}, Link: {link})"
         
    await interaction.response.send_message(message, ephemeral=True)


# --- Core Commands ---

@bot.tree.command(name="help", description="Get a list of commands and general studio assistance.")
async def help_command(interaction: discord.Interaction, topic: str = None):
    """Provides a dynamic help response using the Gemini API."""
    
    if topic:
        prompt = f"The user is asking for help on the topic: '{topic}'. Use the provided studio knowledge to give a detailed, helpful answer."
    else:
        prompt = "The user is asking for general help. Provide a welcoming overview of Stargame Studio, list the main slash commands for support, and tell them about the 'LAGOONA' keyword feature."

    context = STUDIO_KNOWLEDGE + (
        "\n\n**Main Commands:** /announcement, /settask, /ticket, /verify, /setwelcomegoodbye, /levelup, /announceforposts, /dailyposts. "
        "Also, the bot responds to the keyword 'LAGOONA' for quick questions."
    )
    
    response_text = await generate_response(prompt, context, interaction.user.name)
    await interaction.response.send_message(response_text, ephemeral=False)

@bot.tree.command(name="ticket", description="Create a private ticket thread for staff support/appeals.")
@discord.app_commands.describe(issue="Brief description of the issue or appeal.")
async def ticket_command(interaction: discord.Interaction, issue: str):
    """Creates a private thread for a user to discuss an issue with staff."""
    
    start_message = (
        f"**New Support Ticket for {interaction.user.mention}**\n\n"
        f"**Issue:** {issue}\n\n"
        f"A staff member will be with you shortly. If this is an appeal, please provide relevant context and evidence."
    )

    try:
        # Create a private thread in the channel where the command was used
        thread = await interaction.channel.create_thread(
            name=f"Ticket-{interaction.user.name}-{random.randint(100, 999)}",
            type=discord.ChannelType.private_thread,
            reason="User initiated support ticket"
        )
        await thread.send(start_message)
        
        await interaction.response.send_message(
            f"✅ Your support ticket has been opened! Please head to **{thread.mention}** to continue your discussion privately with staff.",
            ephemeral=True
        )

    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ I do not have permission to create threads in this channel. Please ask an admin to check my permissions.",
            ephemeral=True
        )

@bot.tree.command(name="verify", description="Verify your Roblox account membership in the Stargame Studio Group.")
async def verify_command(interaction: discord.Interaction):
    """Initiates a mock Roblox verification process."""
    
    response_text = (
        f"🔗 **Roblox Verification Initiated for {interaction.user.name}**\n\n"
        "To verify your identity and link your Roblox account, please follow these steps:\n"
        f"1. **Join the official Stargame Studio Group:** (Group ID: `{ROBLOX_GROUP_ID}`).\n"
        "2. **DM a specific verification code** to me (Lagoona) from your Roblox account bio/status (this step is mocked).\n\n"
        f"Roblox Group Link: https://www.roblox.com/communities/{ROBLOX_GROUP_ID}/Stargame-Studio#!/about"
    )
    
    await interaction.response.send_message(response_text, ephemeral=True)

@bot.tree.command(name="dailyposts", description="[STAFF ONLY] Set the channel and time for the daily quote/question post.")
@discord.app_commands.describe(
    channel="The channel for daily posts.",
    utc_time="The time for the post (HH:MM UTC format, e.g., 10:00)."
)
async def dailyposts_command(interaction: discord.Interaction, channel: discord.TextChannel, utc_time: str):
    """Configures the daily scheduled post."""
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("🚫 You must be an administrator to set up daily posts.", ephemeral=True)

    try:
        hour, minute = map(int, utc_time.split(':'))
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError
            
        new_time = time(hour=hour, minute=minute)
        DAILY_POST_SETTINGS['channel_id'] = channel.id
        DAILY_POST_SETTINGS['time'] = new_time

        # Restart the loop task to apply the new time immediately
        daily_post_task.change_interval(time=new_time)
        daily_post_task.restart()

        await interaction.response.send_message(
            f"✅ Daily quote/question post set for {channel.mention} at **{utc_time} UTC**.",
            ephemeral=True
        )
    except ValueError:
        await interaction.response.send_message(
            "❌ Invalid time format. Please use **HH:MM** (24-hour UTC time, e.g., 08:30).",
            ephemeral=True
        )

@bot.tree.command(name="setwelcomegoodbye", description="[STAFF ONLY] Set up or disable welcome and goodbye messages.")
@discord.app_commands.describe(
    action="Enable or disable the feature.",
    channel="The channel for welcome/goodbye messages (required if enabling)."
)
@discord.app_commands.choices(
    action=[
        discord.app_commands.Choice(name="Enable", value="enable"),
        discord.app_commands.Choice(name="Disable", value="disable"),
    ]
)
async def set_welcome_goodbye_command(interaction: discord.Interaction, action: str, channel: discord.TextChannel = None):
    """Sets the channel for welcome and goodbye messages."""
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("🚫 You must be an administrator to manage this feature.", ephemeral=True)

    action = action.lower()
    if action == 'enable':
        if not channel:
            return await interaction.response.send_message("You must specify a channel to enable the feature.", ephemeral=True)
            
        WELCOME_SETTINGS['enabled'] = True
        WELCOME_SETTINGS['channel_id'] = channel.id
        await interaction.response.send_message(
            f"✅ Welcome/Goodbye messages **enabled** and set to post in {channel.mention}.",
            ephemeral=True
        )
    elif action == 'disable':
        WELCOME_SETTINGS['enabled'] = False
        WELCOME_SETTINGS['channel_id'] = None
        await interaction.response.send_message("❌ Welcome/Goodbye messages **disabled**.", ephemeral=True)
    else:
        await interaction.response.send_message("Invalid action. Use 'enable' or 'disable'.", ephemeral=True)


# --- Task Management Commands (Retained from prior version) ---

@bot.tree.command(name="settask", description="[STAFF ONLY] Assign a task and deadline to a user.")
@discord.app_commands.describe(
    user="The user to whom the task is assigned.",
    task="Description of the task.",
    deadline="Deadline (YYYY-MM-DD HH:MM format, UTC)."
)
async def settask_command(interaction: discord.Interaction, user: discord.Member, task: str, deadline: str):
    """Assigns a task to a user with a specific deadline."""
    if not is_authorized(interaction.user.name):
        return await interaction.response.send_message("🚫 Only authorized staff can assign tasks.", ephemeral=True)

    try:
        deadline_dt = datetime.strptime(deadline, '%Y-%m-%d %H:%M')
    except ValueError:
        return await interaction.response.send_message(
            "❌ Invalid deadline format. Please use **YYYY-MM-DD HH:MM** (e.g., 2025-10-31 18:00 UTC).",
            ephemeral=True
        )

    user_id = user.id
    TASK_REMINDERS.setdefault(user_id, []).append({
        'task': task,
        'deadline': deadline_dt,
        'original_setter': interaction.user.name
    })

    await interaction.response.send_message(
        f"✅ Task assigned: **{user.mention}** must complete '{task}' by **{deadline_dt.strftime('%Y-%m-%d %H:%M UTC')}**.",
        ephemeral=False
    )


@bot.tree.command(name="completetask", description="[STAFF ONLY] Mark a task as complete for a user.")
@discord.app_commands.describe(
    user="The user who completed the task.",
    task_index="The number of the task to mark as complete (starting from 1)."
)
async def completetask_command(interaction: discord.Interaction, user: discord.Member, task_index: int):
    """Marks a task as complete."""
    if not is_authorized(interaction.user.name):
        return await interaction.response.send_message("🚫 Only authorized staff can manage tasks.", ephemeral=True)

    user_id = user.id
    if user_id not in TASK_REMINDERS or not TASK_REMINDERS[user_id]:
        return await interaction.response.send_message(f"❌ {user.name} has no outstanding tasks.", ephemeral=True)

    try:
        task_to_remove = TASK_REMINDERS[user_id].pop(task_index - 1)
        
        if not TASK_REMINDERS[user_id]:
            del TASK_REMINDERS[user_id]
            
        await interaction.response.send_message(
            f"✅ Task **'{task_to_remove['task']}'** for {user.mention} marked as **COMPLETE**!",
            ephemeral=False
        )
    except IndexError:
        await interaction.response.send_message("❌ Invalid task number. Use `/viewtasks` to see the list.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)


@bot.tree.command(name="extendedtask", description="[STAFF ONLY] Extend the deadline for a user's task.")
@discord.app_commands.describe(
    user="The user whose task deadline is extended.",
    task_index="The number of the task to extend (starting from 1).",
    new_deadline="New deadline (YYYY-MM-DD HH:MM format, UTC)."
)
async def extendedtask_command(interaction: discord.Interaction, user: discord.Member, task_index: int, new_deadline: str):
    """Extends the deadline of an existing task."""
    if not is_authorized(interaction.user.name):
        return await interaction.response.send_message("🚫 Only authorized staff can manage tasks.", ephemeral=True)

    user_id = user.id
    if user_id not in TASK_REMINDERS or not TASK_REMINDERS[user_id]:
        return await interaction.response.send_message(f"❌ {user.name} has no outstanding tasks.", ephemeral=True)

    try:
        new_deadline_dt = datetime.strptime(new_deadline, '%Y-%m-%d %H:%M')
        
        task_item = TASK_REMINDERS[user_id][task_index - 1]
        task_item['deadline'] = new_deadline_dt
        
        await interaction.response.send_message(
            f"🔄 Deadline for task **'{task_item['task']}'** for {user.mention} extended to **{new_deadline_dt.strftime('%Y-%m-%d %H:%M UTC')}**.",
            ephemeral=False
        )
    except ValueError:
        await interaction.response.send_message(
            "❌ Invalid deadline format. Please use **YYYY-MM-DD HH:MM** (e.g., 2025-10-31 18:00 UTC).",
            ephemeral=True
        )
    except IndexError:
        await interaction.response.send_message("❌ Invalid task number. Use `/viewtasks` to see the list.", ephemeral=True)


@bot.tree.command(name="incompletetask", description="[STAFF ONLY] Mark a task as incomplete/failed for a user.")
@discord.app_commands.describe(
    user="The user whose task is incomplete.",
    task_index="The number of the task to mark as failed (starting from 1)."
)
async def incompletetask_command(interaction: discord.Interaction, user: discord.Member, task_index: int):
    """Marks a task as incomplete/failed."""
    if not is_authorized(interaction.user.name):
        return await interaction.response.send_message("🚫 Only authorized staff can manage tasks.", ephemeral=True)

    user_id = user.id
    if user_id not in TASK_REMINDERS or not TASK_REMINDERS[user_id]:
        return await interaction.response.send_message(f"❌ {user.name} has no outstanding tasks.", ephemeral=True)

    try:
        task_item = TASK_REMINDERS[user_id].pop(task_index - 1)
        
        if not TASK_REMINDERS[user_id]:
            del TASK_REMINDERS[user_id]
            
        await interaction.response.send_message(
            f"🔴 Task **'{task_item['task']}'** for {user.mention} marked as **INCOMPLETE/FAILED**. Please review with the staff member who assigned it.",
            ephemeral=False
        )
    except IndexError:
        await interaction.response.send_message("❌ Invalid task number. Use `/viewtasks` to see the list.", ephemeral=True)


@bot.tree.command(name="forwardedtask", description="[STAFF ONLY] Forward an assigned task to a new user.")
@discord.app_commands.describe(
    current_user="The user the task is currently assigned to.",
    task_index="The number of the task to forward (starting from 1).",
    new_user="The new user to assign the task to."
)
async def forwardedtask_command(interaction: discord.Interaction, current_user: discord.Member, task_index: int, new_user: discord.Member):
    """Forwards an existing task to a new user."""
    if not is_authorized(interaction.user.name):
        return await interaction.response.send_message("🚫 Only authorized staff can manage tasks.", ephemeral=True)

    current_user_id = current_user.id
    new_user_id = new_user.id

    if current_user_id not in TASK_REMINDERS or not TASK_REMINDERS[current_user_id]:
        return await interaction.response.send_message(f"❌ {current_user.name} has no outstanding tasks to forward.", ephemeral=True)

    try:
        task_to_forward = TASK_REMINDERS[current_user_id].pop(task_index - 1)
        
        if not TASK_REMINDERS[current_user_id]:
            del TASK_REMINDERS[current_user_id]
            
        # Assign to new user
        TASK_REMINDERS.setdefault(new_user_id, []).append(task_to_forward)

        await interaction.response.send_message(
            f"➡️ Task **'{task_to_forward['task']}'** successfully forwarded from {current_user.mention} to **{new_user.mention}**.",
            ephemeral=False
        )
    except IndexError:
        await interaction.response.send_message("❌ Invalid task number. Use `/viewtasks` to see the list.", ephemeral=True)
        

# --- Founder Only Commands ---

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
        footer_text = f"Authorized Message by {author_username}" 
        
        # Select one of the two banner images randomly if none is provided
        final_image_url = image_url if image_url else random.choice(BANNER_IMAGES)
        
        embed = discord.Embed(
            title=f"📣 {title}",
            description=message,
            color=discord.Color.blue()
        )
        
        # Set the image (banner) before the footer/text
        embed.set_image(url=final_image_url) 
        embed.set_footer(text=footer_text)
        
        await interaction.response.send_message("Announcement pending! Posting now...", ephemeral=True) 
        
        # Check for role pings and add the actual role mention if specified
        ping_content = ""
        if "@everyone" in message.lower():
            ping_content += "@everyone "

        public_message = await interaction.channel.send(ping_content, embed=embed) 

        # Add reactions
        await add_announcement_reactions(public_message)
    else:
        await interaction.response.send_message(
            f"🚫 Access Denied. Only authorized staff ({', '.join(ANNOUNCEMENT_AUTHORS)}) can use this command.",
            ephemeral=True
        )
        

@bot.tree.command(name="revampallusernames", description="[FOUNDER ONLY] Revamp all server members' nicknames.")
async def revampallusernames_command(interaction: discord.Interaction):
    """Mocks revamping all nicknames for server organization."""
    if not is_founder(interaction.user.name):
        return await interaction.response.send_message("🚫 Only the founder can use this command.", ephemeral=True)
    
    # Mock response for a long-running/sensitive task
    await interaction.response.send_message(
        "🛠️ Initiating server-wide nickname revamp. This process will organize all visible names into a standard format. This may take a moment...",
        ephemeral=False
    )
    # In a real bot, you'd iterate through members and apply a naming scheme (e.g., "[Role] Username")


@bot.tree.command(name="verifyallmembers", description="[STAFF ONLY] Check all members for Roblox Group membership status.")
async def verifyallmembers_command(interaction: discord.Interaction):
    """Mocks re-checking all members' Roblox verification status."""
    if not is_authorized(interaction.user.name):
        return await interaction.response.send_message("🚫 Only authorized staff can use this command.", ephemeral=True)

    await interaction.response.send_message(
        "🔎 Starting batch verification process for all members against the Roblox Group. Results will be posted in a staff-only channel once complete (MOCK).",
        ephemeral=True
    )

# --- START THE BOT ---
if __name__ == "__main__":
    if not DISCORD_TOKEN or not GEMINI_API_KEY or not CLIENT_ID:
        print("\n--- CRITICAL ERROR: REQUIRED ENVIRONMENT VARIABLES MISSING ---")
        print("Please ensure DISCORD_TOKEN, GEMINI_API_KEY, and CLIENT_ID are set.")
    else:
        # Start the web server in a separate thread to keep Render happy
        web_server_thread = threading.Thread(target=run_web_server)
        web_server_thread.daemon = True 
        web_server_thread.start()
        
        # Run the Discord bot
        bot.run(DISCORD_TOKEN)
