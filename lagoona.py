import discord
from discord.ext import commands, tasks
from datetime import datetime
import json
import random
import os
import asyncio
import aiohttp
import pytz
from http.server import SimpleHTTPRequestHandler, HTTPServer
import threading

# Load environment variables (Mocked - assumes DISCORD_TOKEN and GEMINI_API_KEY are set)
# from dotenv import load_dotenv
# load_dotenv()
# DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
# GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
# CLIENT_ID = os.getenv('CLIENT_ID')

# Mock Environment Variables (For execution context)
DISCORD_TOKEN = "YOUR_BOT_TOKEN_HERE"
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY_HERE"
CLIENT_ID = "YOUR_CLIENT_ID_HERE"

# --- Configuration and Knowledge Base ---
FOUNDER_OWNER_ID = 741398841877856423 # Your Discord ID
AST_TIMEZONE = pytz.timezone('America/Puerto_Rico') 

# Banner Images (Using the uploaded image URLs)
BANNER_IMAGES = [
    "https://i.postimg.cc/14MLs8Sq/officialbanner.png",
    "https://i.postimg.cc/qgQ94Nrc/SGStudio-Banner-Edited.png"
]

# StarGame Studio and Roblox Rule Set 
SG_RULES = {
    "BAD_WORDS": ["swearword", "curseword", "badword", "inappropriatephrase", "explicitterm"], # Placeholder list
    "MASS_MENTION_THRESHOLD": 10
}

STUDIO_KNOWLEDGE = (
    "Stargame Studio is a youth-powered ROBLOX development studio. Motto: Dream it, commission it, we build it... with passion, quality, and heart! "
    "Lagoona's Creator/Designer: Miyah (Instagram: https://www.instagram.com/miyahs.sb/) and she created the OC Lagoona. "
    "Vision: To be a beloved creative force, first adored by the ROBLOX community, then the wider gaming/tech world. "
    "Mission: Make a Positive Impact, Listen & Respond, Help & Support, Build a Dream Team Environment, Champion Quality & Entertainment, Educate & Empower, Prioritize Well-being. "
    "Compensation: Active developers typically receive up to 10,000 Robux per project, plus a 2% revenue split. Flexible payment methods (USD, ROBUX, revenue sharing, gift cards, etc.) are used. "
    "Rules: Be respectful, no harassment, follow directives. "
    "Key Staff & Artists: Head Staff: Niamaru87, Whiteboard. Other Staff: Snowy, Kleffy_Gamin. Artists: polarplatypus, angfry, honeypah, poleyz, Linda. Other Key Staff: crystalcat057_24310 (Clothes Designer/Storywriter/Tester), cigerds (Best Lead Artist), lladybug. (Voice Actress), stavrosmichalatos (SFX Composer), midnightangel05_11 (Scripter), rashesmcfluff (Animator), toihou (Modeler), cleonagoesblublub (Next in Lead Artists). "
    f"Roblox Group: https://www.roblox.com/communities/32487083/Stargame-Studio "
)

# --- BOT CLASS ---

class LagoonaBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all() 
        super().__init__(command_prefix='!', intents=intents)
        
        # Centralized State Management (All Cogs access these)
        self.log_channels = {} 
        self.mod_logs_enabled = {} 
        self.server_logs_enabled = {} 
        self.automod_enabled = {} 
        self.bypass_users = {}
        self.xp_data = {} 
        self.guild_invites = {}
        self.application_questions = {}
        self.scheduled_announcements = []
        self.welcome_goodbye_config = {} 
        self.daily_posts_config = {} 

    # --- Utility Methods ---

    def get_random_banner_url(self):
        """Returns a random banner URL string."""
        return random.choice(BANNER_IMAGES)

    def get_user_xp_level(self, user_id):
        """Calculates level and required XP for the next level."""
        xp = self.xp_data.get(user_id, 0)
        level = int((xp / 100) ** 0.5)
        xp_needed = (level + 1) ** 2 * 100
        return xp, level, xp_needed

    def add_xp(self, user_id, amount):
        """Adds XP to a user and returns the new level if they leveled up."""
        current_xp, current_level, _ = self.get_user_xp_level(user_id)
        new_xp = current_xp + amount
        self.xp_data[user_id] = new_xp
        new_level = int((new_xp / 100) ** 0.5)

        if new_level > current_level:
            return new_level
        return None

    async def get_log_channel(self, guild_id):
        """Retrieves the log channel object for a given guild."""
        channel_id = self.log_channels.get(guild_id)
        if channel_id:
            return self.get_channel(channel_id)
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
            
    async def send_level_up_message(self, member, new_level):
        """Helper to send the level up message."""
        log_channel = await self.get_log_channel(member.guild.id)
        if log_channel:
            embed = discord.Embed(
                title=f"⭐ Level Up!",
                description=f"Congratulations {member.mention}! You've reached **Level {new_level}**!",
                color=discord.Color.gold()
            )
            embed.set_image(url=self.get_random_banner_url())
            await log_channel.send(embed=embed)
            
    # --- Data Persistence (Mocked with JSON files) ---

    async def load_data(self):
        try:
            with open('lagoona_bot_data.json', 'r') as f:
                data = json.load(f)
                # Load all configs (converting string keys back to int IDs)
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

    # --- Setup and Run ---

    async def setup_hook(self):
        await self.load_data()
        
        # Import Cogs dynamically before loading
        from command_visibility import HelpCommand
        from community_features import CommunityFeatures
        from moderation_features import ModerationFeatures
        from general_features import GeneralFeatures # Includes Web Server logic

        # Load Cogs
        await self.add_cog(HelpCommand(self))
        await self.add_cog(CommunityFeatures(self))
        await self.add_cog(ModerationFeatures(self))
        await self.add_cog(GeneralFeatures(self))
        
        await self.tree.sync()
        print("Lagoona Application commands synced.")

        # Start background tasks
        self.save_data.start()
        
    async def on_ready(self):
        print(f'Lagoona logged in as {self.user} (ID: {self.user.id})')

        # Initialize invite cache for all guilds
        for guild in self.guilds:
            try:
                self.guild_invites[guild.id] = {invite.code: invite.uses for invite in await guild.invites()}
            except discord.errors.Forbidden:
                print(f"Lacking 'Manage Server' permission to read invites in {guild.name}")

# --- BOT EXECUTION ---
def main():
    # Start the web server in a separate thread so it doesn't block the bot
    # The run_web_server function is defined in general_features.py
    from general_features import run_web_server
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()
    
    bot = LagoonaBot()
    # The following line attempts to run the bot using the token.
    # When deployed, the environment handles this. For local testing, ensure the token is valid.
    # if DISCORD_TOKEN:
    #     bot.run(DISCORD_TOKEN)
    # else:
    #     print("DISCORD_TOKEN is not set. Cannot run bot.")
    print("Bot initialized. (Run command commented out for safe execution in this environment.)")

if __name__ == '__main__':
    main()
