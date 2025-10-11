import discord
from discord.ext import commands, tasks
import aiohttp
import os
from datetime import time
import asyncio
from dotenv import load_dotenv

# Load environment variables from a local .env file if it exists (for local testing)
load_dotenv()

# --- Configuration ---
# 1. These must be set as environment variables (secrets) in your Render dashboard.
# 2. For local testing, put them in a .env file.
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
# The CLIENT_ID is required for registering slash commands
CLIENT_ID = os.getenv('CLIENT_ID') 

# Ensure message content and server member intents are enabled in your Discord Developer Portal
intents = discord.Intents.default()
intents.message_content = True 
intents.members = True 
intents.guilds = True

# We use commands.Bot for slash command registration and task scheduling
# Setting command_prefix to a low-use character since we primarily use slash commands
bot = commands.Bot(command_prefix='!', intents=intents)

# Configuration storage for daily posts (NOTE: This is NOT persistent storage. 
# Settings will be lost when the bot restarts.
DAILY_POST_SETTINGS = {
    'enabled': False,
    'channel_id': None,
    # Set the time for the daily post (e.g., 10:00 AM UTC)
    'post_time': time(hour=10, minute=0, tzinfo=None) 
}

# List of authorized users for announcements (case-sensitive Discord usernames)
ANNOUNCEMENT_AUTHORS = ['niamaru87', 'lionelclementofficial']

# --- Gemini API Functions ---

async def generate_response(prompt: str):
    """Generates a text response using the Gemini API."""
    if not GEMINI_API_KEY:
        return "Error: Gemini API key not configured on the server."

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent?key={GEMINI_API_KEY}"

    # System instruction guiding the AI to act as the studio's support agent
    system_instruction = (
        "You are Lagoona, the official, helpful, and friendly customer/tech support and "
        "community agent for 'The Studio'. Your purpose is to provide concise and accurate "
        "answers about the studio, its products, and community. Keep your answers brief and encouraging."
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "systemInstruction": {"parts": [{"text": system_instruction}]},
    }
    
    # Use aiohttp for asynchronous HTTP requests
    async with aiohttp.ClientSession() as session:
        try:
            # Implement simple retry mechanism with exponential backoff
            for i in range(3): 
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        text = data.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', 'The AI is currently unable to answer this question.')
                        return text
                    elif response.status == 429: # Too many requests (Rate limit)
                        await asyncio.sleep(2 ** i) # Exponential backoff
                        continue
                    else:
                        print(f"Gemini API Error Status: {response.status}")
                        return f"API Error: Could not reach the AI support system (Status: {response.status})."
            return "The AI support system is busy right now. Please try again later."
        except aiohttp.ClientConnectorError:
            return "Error: The AI service could not be connected to."
        except Exception as e:
            print(f"Unexpected error during API call: {e}")
            return "An unexpected error occurred while processing your request."


# --- Bot Events ---

@bot.event
async def on_ready():
    """Confirms the bot is logged in and starts scheduled tasks."""
    print(f'Logged in as {bot.user.name} ({bot.user.id})')
    
    if CLIENT_ID:
        # Use the application command tree to sync slash commands globally
        try:
            synced = await bot.tree.sync()
            print(f"Synced {len(synced)} command(s) globally.")
        except Exception as e:
            print(f"Failed to sync commands: {e}")
            
    # Start the daily post check loop
    if not daily_post_task.is_running():
        daily_post_task.start()

@bot.event
async def on_message(message):
    """Listens for the activation keyword 'Lagoona' and general questions."""
    # Ignore messages from the bot itself
    if message.author == bot.user:
        return

    # Check for the activation keyword 'Lagoona' (case-insensitive)
    if 'lagoona' in message.content.lower():
        await message.channel.send(f"Activating support for {message.author.mention}. Please wait while Lagoona processes your request...")
        prompt = f"The user asked: '{message.content}'. Please respond by first acknowledging the keyword Lagoona and then offering support assistance."
        response_text = await generate_response(prompt)
        # Edit the previous message instead of sending a new one, but for simplicity, sending a new one.
        await message.channel.send(response_text)
    
    # Process commands (This line is necessary if you are mixing prefix commands and events)
    await bot.process_commands(message) 

# --- Slash Commands ---

# Helper function to check authorization
def is_authorized(username: str) -> bool:
    """Checks if a username is in the authorized list (case-insensitive)."""
    return username.lower() in [name.lower() for name in ANNOUNCEMENT_AUTHORS]

@bot.tree.command(name="announcement", description="Post an important studio announcement to the channel.")
@discord.app_commands.describe(message="The message content for the announcement.")
async def announcement_command(interaction: discord.Interaction, message: str):
    """
    Allows only authorized users to post an announcement.
    """
    author_username = interaction.user.name 

    if is_authorized(author_username):
        # Use an embed for a clean, official announcement look
        embed = discord.Embed(
            title="📣 Studio Announcement",
            description=message,
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Posted by {interaction.user.display_name}")
        
        # Respond to the user privately
        await interaction.response.send_message("Announcement successful! Posting now...", ephemeral=True) 
        
        # Post the public announcement
        await interaction.channel.send("@everyone", embed=embed) 
    else:
        await interaction.response.send_message(
            f"🚫 Access Denied. Only authorized users ({', '.join(ANNOUNCEMENT_AUTHORS)}) can use this command.",
            ephemeral=True
        )

@bot.tree.command(name="setdailyposts", description="Enable or disable the daily post task and set its channel.")
@discord.app_commands.describe(
    action="Enable or disable the daily post.",
    channel="The channel where the daily post should be sent." # FIX: Removed ": discord.TextChannel" from here
)
async def set_daily_posts_command(interaction: discord.Interaction, action: str, channel: discord.TextChannel):
    """
    Sets the channel and state for the daily scheduled post.
    """
    action = action.lower()
    
    # Simple permission check for management command (only administrators can run it)
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("You must be an administrator to manage daily posts.", ephemeral=True)

    if action == "enabled":
        if channel.type != discord.ChannelType.text:
             return await interaction.response.send_message("The channel must be a text channel.", ephemeral=True)
             
        DAILY_POST_SETTINGS['enabled'] = True
        DAILY_POST_SETTINGS['channel_id'] = channel.id

        await interaction.response.send_message(
            f"✅ Daily posts are now **enabled** and will be sent to {channel.mention} every day at approximately {DAILY_POST_SETTINGS['post_time']} UTC.",
            ephemeral=True
        )
    elif action == "disabled":
        DAILY_POST_SETTINGS['enabled'] = False
        DAILY_POST_SETTINGS['channel_id'] = None # Clear channel on disable

        await interaction.response.send_message(
            "❌ Daily posts are now **disabled**.",
            ephemeral=True
        )
    else:
         await interaction.response.send_message(
            "Invalid action. Please use `/setdailyposts enabled <channel>` or `/setdailyposts disabled <channel>`.",
            ephemeral=True
        )

# --- Scheduled Task ---

@tasks.loop(time=DAILY_POST_SETTINGS['post_time'])
async def daily_post_task():
    """Sends a friendly post to the configured channel daily."""
    
    if not DAILY_POST_SETTINGS['enabled'] or not DAILY_POST_SETTINGS['channel_id']:
        return

    try:
        # bot.get_channel is preferred for channel fetching from ID
        channel = bot.get_channel(DAILY_POST_SETTINGS['channel_id'])
        if channel:
            # Generate a dynamic and engaging daily post using the AI
            daily_prompt = "Generate a short, friendly, and engaging daily post for a Discord community about a creative studio. The post should encourage community interaction or share a positive thought."
            post_content = await generate_response(daily_prompt)

            await channel.send(f"☀️ **Daily Studio Check-in!**\n\n{post_content}\n\n*Have a wonderful day!*")
        else:
            print(f"Error: Channel with ID {DAILY_POST_SETTINGS['channel_id']} not found. Disabling daily posts.")
            DAILY_POST_SETTINGS['enabled'] = False 
            
    except Exception as e:
        print(f"Error sending daily post: {e}")

# Run the bot
if __name__ == "__main__":
    if not DISCORD_TOKEN or not GEMINI_API_KEY or not CLIENT_ID:
        print("\n--- CRITICAL ERROR: REQUIRED ENVIRONMENT VARIABLES MISSING ---")
        print("Please ensure DISCORD_TOKEN, GEMINI_API_KEY, and CLIENT_ID are set in your Render environment variables or in a local .env file.")
        print("Bot will not run without these variables.")
    else:
        # This will run the bot if the required environment variables are found
        bot.run(DISCORD_TOKEN)
