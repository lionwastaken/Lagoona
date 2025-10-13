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
                            await setter.send(f"⚠️ **DEADLINE ALERT:** Task '{task