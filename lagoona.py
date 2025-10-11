import discord
from discord.ext import commands, tasks
import aiohttp
import os
import asyncio
from datetime import time
from dotenv import load_dotenv
from fuzzywuzzy import fuzz # For text matching/moderation checks

# Load environment variables from a local .env file if it exists (for local testing)
load_dotenv()

# --- CONFIGURATION & KNOWLEDGE BASE ---
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
CLIENT_ID = os.getenv('CLIENT_ID') 

# Define the Stargame Studio knowledge base for the AI
STUDIO_KNOWLEDGE = (
    "Stargame Studio is a youth-powered ROBLOX development studio focused on creating immersive games (like Rampage Royale), "
    "UGC, 2D fashion, and artwork. We champion human artistry over AI art. "
    "Compensation: Active developers typically receive up to 10,000 Robux per project, plus a 2% revenue split. "
    "Payment methods for commissions are flexible (USD, ROBUX, revenue sharing). "
    "Rules: Be respectful, no harassment, follow directives from Owner (lionelclementofficial) and Co-Owner (niamaru87). "
    "Grounds for Termination: Violation of TOS (Stargame, Roblox, Discord), inappropriate conduct, insubordination, non-cooperation, prolonged inactivity, and unprofessional departure. "
    "Appeals are generally not available. "
    "Roadmap: Late 2025 includes Relax Hangout and Veccera Cafe release. 2026 starts development on The Outbreak (Adventure/Horror). "
)

# List of authorized users for announcements (case-insensitive checks are done later)
ANNOUNCEMENT_AUTHORS = ['niamaru87', 'lionelclementofficial']

# Security-related known good domains (for link verification)
STARGAME_DOMAINS = ["stargamestudio.com", "roblox.com/groups/stargame", "discord.gg/stargame"]

# Moderation State (Non-persistent, will reset on bot restart)
# Store moderation strikes (user_id: strike_count)
MOD_STRIKES = {}

# Moderation thresholds
STRIKE_WARN = 1
STRIKE_MUTE = 3 # Warning then a temporary mute
STRIKE_KICK = 5 # Final warning then a kick

# --- BOT SETUP ---
intents = discord.Intents.default()
intents.message_content = True 
intents.members = True # REQUIRED for welcome messages and moderation checks
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Configuration storage for daily posts (Non-persistent)
DAILY_POST_SETTINGS = {
    'enabled': False,
    'channel_id': None,
    'post_time': time(hour=10, minute=0, tzinfo=None) 
}


# --- GEMINI API FUNCTION ---

async def generate_response(prompt: str, knowledge_base: str):
    """Generates a text response using the Gemini API, grounded in Studio knowledge."""
    if not GEMINI_API_KEY:
        return "Error: Gemini API key not configured on the server."

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent?key={GEMINI_API_KEY}"

    # System instruction tailored for Stargame support
    system_instruction = (
        "You are Lagoona, the official, helpful, and friendly customer/tech support and "
        "community agent for 'Stargame Studio'. Your purpose is to provide concise, friendly, and accurate "
        "answers based ONLY on the provided knowledge context. If the question is simple or about "
        "Discord mechanics (/help, etc.), you can answer without the context. "
        "Stargame Studio Knowledge Context: " + knowledge_base
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "systemInstruction": {"parts": [{"text": system_instruction}]},
    }
    
    # Use aiohttp for asynchronous HTTP requests
    async with aiohttp.ClientSession() as session:
        try:
            for i in range(3): 
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
            return "Lagoona is too busy right now. Please try again later."
        except Exception:
            return "An unexpected error occurred while processing your request."


# --- HELPER FUNCTIONS ---

def is_authorized(username: str) -> bool:
    """Checks if a username is in the authorized list (case-insensitive)."""
    return username.lower() in [name.lower() for name in ANNOUNCEMENT_AUTHORS]

def is_excessive_caps(content: str) -> bool:
    """Detects if message content has excessive capitalization."""
    if len(content) < 10: # Ignore short messages
        return False
    
    # Count uppercase letters
    uppercase_count = sum(1 for char in content if char.isupper() and char.isalpha())
    # Count total alphabetical letters
    alpha_count = sum(1 for char in content if char.isalpha())
    
    # If less than 5 letters, skip check
    if alpha_count < 5:
        return False
        
    # Check if more than 60% of letters are uppercase
    return (uppercase_count / alpha_count) > 0.60

def is_gif_post(message: discord.Message) -> bool:
    """Checks if a message is a standalone GIF link or embed."""
    # Common GIF formats/domains
    gif_keywords = ['tenor.com', 'giphy.com', '.gif']
    content_lower = message.content.lower()

    # Check content for GIF links
    if any(k in content_lower for k in gif_keywords):
        return True
    
    # Check embeds (e.g., if a GIF was uploaded directly and embedded)
    if message.embeds:
        for embed in message.embeds:
            if embed.type == 'gifv':
                return True
    return False

async def apply_moderation_action(member: discord.Member, channel: discord.TextChannel, reason: str, action: str = 'warn'):
    """Applies moderation actions based on strike count."""
    user_id = member.id
    
    # Initialize or increment strike count
    MOD_STRIKES[user_id] = MOD_STRIKES.get(user_id, 0) + 1
    strikes = MOD_STRIKES[user_id]
    
    mod_message = ""

    if action == 'warn' and strikes <= STRIKE_WARN:
        mod_message = f"🚨 **WARNING** {member.mention}: Please adhere to server rules. Your action ({reason}) has resulted in **{strikes} strike(s)**. Further violations will result in a Mute or Kick."
        await channel.send(mod_message)
    elif strikes == STRIKE_MUTE:
        # NOTE: Muting requires setting up a "Muted" role with denied Send Messages permissions
        # For simplicity, we'll send a message indicating a mute, but the role management is complex.
        mod_message = f"🔇 **MUTE** {member.mention}: You have reached **{strikes} strikes**. You are muted for inappropriate conduct ({reason})."
        # Actual mute logic (requires setup): await member.timeout(timedelta(minutes=15), reason=reason)
        await channel.send(mod_message)
    elif strikes >= STRIKE_KICK:
        try:
            mod_message = f"👋 **KICK** {member.mention}: You have reached the maximum **{strikes} strikes** for repeated violations ({reason}). You are being kicked as per Stargame Studio TOS."
            await channel.send(mod_message)
            await member.kick(reason=f"Automated moderation for repeated violations: {reason}")
            del MOD_STRIKES[user_id] # Clear strikes after kick
        except discord.Forbidden:
            mod_message += "\n(Error: I do not have permissions to kick this user.)"
            await channel.send(mod_message)
    else:
        # Default warning for strikes between thresholds
        mod_message = f"⚠️ **NOTICE** {member.mention}: Strike count updated to **{strikes}** for {reason}. You are close to being muted/kicked."
        await channel.send(mod_message)


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


@bot.event
async def on_member_join(member):
    """Automatically greets new members."""
    # Get the system channel or a designated welcome channel (replace 'welcome-channel-id' if necessary)
    welcome_channel = member.guild.system_channel
    
    if welcome_channel:
        welcome_message = (
            f"🌟 Welcome, {member.mention}, to **Stargame Studio**! We're thrilled to have you join our community. "
            f"Dream it, commission it, we build it! Check out the rules, and if you need any support, "
            f"just mention **Lagoona** or use the `/help` command! Have fun!"
        )
        await welcome_channel.send(welcome_message)


@bot.event
async def on_message(message):
    """Handles keyword response and automated moderation."""
    if message.author.bot:
        return

    content = message.content.lower()
    
    # 1. Moderation: Check for TOS violations
    is_violation = False
    reason = None
    
    # Check for excessive caps (TOS violation: 'explicitly inappropriate server wise')
    if is_excessive_caps(message.content):
        is_violation = True
        reason = "Excessive capitalization (Screaming)."

    # Check for GIF posting (TOS violation: 'posts gifs' -> Inappropriate Conduct)
    if is_gif_post(message):
        # NOTE: Only trigger moderation if the user is repeatedly posting GIFs. 
        # For simplicity, we apply a strike immediately.
        is_violation = True
        reason = "Posting unsolicited GIFs."

    if is_violation:
        await message.delete() # Remove the violating message
        await apply_moderation_action(message.author, message.channel, reason, action='warn')
        return # Stop processing to prevent keyword reply

    # 2. Lagoona Keyword Response
    if 'lagoona' in content:
        await message.channel.send(f"Activating support for {message.author.mention}. Please wait while Lagoona processes your request...")
        
        # Friendly and interactive prompt for the AI
        prompt = (
            f"The user said: '{message.content}'. "
            "Please respond in a friendly, interactive, and enthusiastic tone, similar to the screenshot provided. "
            "Acknowledge the call, introduce yourself as Lagoona, and then answer the question or offer assistance "
            "based on the Stargame Studio Knowledge Context provided."
        )
        
        response_text = await generate_response(prompt, STUDIO_KNOWLEDGE)
        
        # Reply with the interactive style
        await message.channel.send(f"Hello, {message.author.mention}! {response_text}")

    await bot.process_commands(message) 

# --- SLASH COMMANDS ---

# Helper function to check authorization
def is_authorized(username: str) -> bool:
    """Checks if a username is in the authorized list (case-insensitive)."""
    return username.lower() in [name.lower() for name in ANNOUNCEMENT_AUTHORS]

@bot.tree.command(name="announcement", description="Post an important studio announcement to the channel.")
@discord.app_commands.describe(message="The message content for the announcement.")
async def announcement_command(interaction: discord.Interaction, message: str):
    """Allows only authorized users to post an announcement."""
    author_username = interaction.user.name 

    if is_authorized(author_username):
        embed = discord.Embed(
            title="📣 Stargame Studio Announcement",
            description=message,
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Posted by {interaction.user.display_name}")
        
        await interaction.response.send_message("Announcement successful! Posting now...", ephemeral=True) 
        await interaction.channel.send("@everyone", embed=embed) 
    else:
        await interaction.response.send_message(
            f"🚫 Access Denied. Only authorized staff ({', '.join(ANNOUNCEMENT_AUTHORS)}) can use this command.",
            ephemeral=True
        )

@bot.tree.command(name="help", description="Get a list of commands or ask Lagoona a general question.")
@discord.app_commands.describe(topic="Ask Lagoona a simple question (e.g., 'What is Rampage Royale?')")
async def help_command(interaction: discord.Interaction, topic: str = None):
    """
    Provides bot information or uses the AI to answer a simple question.
    """
    await interaction.response.defer() # Acknowledge the interaction while the AI processes

    if topic:
        # Use AI to answer a simple question from the knowledge base
        prompt = f"The user asked for help on: '{topic}'. Provide a friendly, concise answer based on the studio knowledge."
        response_text = await generate_response(prompt, STUDIO_KNOWLEDGE)
        await interaction.followup.send(f"Hey there! Here's what Lagoona found on **{topic}**:\n\n{response_text}")
    else:
        # Default help message (non-AI)
        embed = discord.Embed(
            title="⭐️ Stargame Studio Support Bot - Lagoona",
            description="I'm here to help you manage the community and answer your questions!",
            color=discord.Color.gold()
        )
        embed.add_field(name="/help [topic]", value="Ask me a question about the studio (e.g., `/help compensation`).", inline=False)
        embed.add_field(name="Keyword Trigger", value="Mention **Lagoona** in any message for live support.", inline=False)
        embed.add_field(name="/ticket [issue]", value="Open a private support ticket.", inline=False)
        embed.add_field(name="/verify", value="Initiate Roblox account verification (required for some roles).", inline=False)
        embed.add_field(name="/link_check [url]", value="Verify if a link is officially associated with Stargame Studio.", inline=False)
        
        if is_authorized(interaction.user.name):
            embed.add_field(name="Staff Commands", value="`/announcement`, `/setdailyposts`", inline=False)

        await interaction.followup.send(embed=embed)


@bot.tree.command(name="link_check", description="Verify if a link is officially associated with Stargame Studio.")
@discord.app_commands.describe(url="The URL you want to check for legitimacy.")
async def link_check_command(interaction: discord.Interaction, url: str):
    """Checks if a URL belongs to a trusted Stargame Studio domain."""
    await interaction.response.defer(ephemeral=True)
    
    try:
        # Simple domain extraction
        import urllib.parse
        parsed_url = urllib.parse.urlparse(url)
        domain = parsed_url.netloc
        if domain.startswith('www.'):
            domain = domain[4:]

        is_safe = False
        for safe_domain in STARGAME_DOMAINS:
            if safe_domain in domain:
                is_safe = True
                break
        
        if is_safe:
            message = f"✅ **Link Verified!** The domain `{domain}` is recognized as an official Stargame Studio or trusted partner link (like Roblox/Discord)."
        else:
            message = f"⚠️ **Caution!** The domain `{domain}` is **NOT** listed as an official Stargame Studio domain. Proceed with caution and verify the source!"

    except Exception:
        message = "Could not parse the URL. Please ensure it's a valid link starting with http:// or https://."

    await interaction.followup.send(message, ephemeral=True)


@bot.tree.command(name="ticket", description="Create a new support ticket.")
@discord.app_commands.describe(issue="A brief description of your issue or inquiry.")
async def ticket_command(interaction: discord.Interaction, issue: str):
    """
    Creates a private channel/thread for support staff to manage.
    """
    # Create a private thread for the ticket
    try:
        # Use an existing support channel ID if available, otherwise use the current channel
        support_channel = interaction.guild.get_channel(interaction.channel_id) 
        
        # Create a private thread (requires Manage Threads permission)
        thread = await support_channel.create_thread(
            name=f"ticket-{interaction.user.name[:10]}-{interaction.user.discriminator}",
            type=discord.ChannelType.private_thread,
            reason=f"Support ticket created by {interaction.user.name}"
        )

        await thread.send(
            f"**New Ticket from:** {interaction.user.mention}\n"
            f"**Issue:** {issue}\n"
            f"Staff, please assist. {interaction.guild.owner.mention} and Co-Owner {ANNOUNCEMENT_AUTHORS[1]} notified." # Placeholder for notifying staff roles
        )
        
        await interaction.response.send_message(
            f"✅ **Ticket Created!** Your support ticket has been opened in the private thread: {thread.mention}. A staff member will assist you shortly.",
            ephemeral=True
        )

    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ **Error:** I don't have the necessary permissions (e.g., `Manage Threads`) to create a ticket channel. Please contact an admin.",
            ephemeral=True
        )
    except Exception as e:
        await interaction.response.send_message(
            f"❌ **Error:** Failed to create ticket. Details: {e}",
            ephemeral=True
        )

@bot.tree.command(name="verify", description="Start the Roblox account verification process.")
async def verify_command(interaction: discord.Interaction):
    """
    Initiates a secure verification flow (simulated here, requires external database for full implementation).
    """
    # NOTE: Full Roblox verification requires an external verification server/database.
    # This command initiates the conversation flow.

    embed = discord.Embed(
        title="🔒 Stargame Studio Roblox Verification",
        description=(
            "To link your Roblox account securely, you need to follow these steps:\n\n"
            "1. **Visit our verification portal** (simulated link: `https://verify.stargamestudio.com/`).\n"
            "2. **Log in with your Roblox account.**\n"
            "3. **Paste the unique code shown there** into this channel.\n\n"
            "⚠️ **Do not share your Roblox password or any personal information!**"
        ),
        color=discord.Color.dark_green()
    )
    
    await interaction.response.send_message(
        content=f"Hey {interaction.user.mention}, starting your verification!",
        embed=embed,
        ephemeral=True
    )

# --- SCHEDULED TASK (Kept from previous version) ---

@tasks.loop(time=DAILY_POST_SETTINGS['post_time'])
async def daily_post_task():
    """Sends a friendly post to the configured channel daily."""
    if not DAILY_POST_SETTINGS['enabled'] or not DAILY_POST_SETTINGS['channel_id']:
        return

    try:
        channel = bot.get_channel(DAILY_POST_SETTINGS['channel_id'])
        if channel:
            daily_prompt = "Generate a short, friendly, and engaging daily post for a Discord community about a creative studio. The post should encourage community interaction or share a positive thought."
            post_content = await generate_response(daily_prompt, STUDIO_KNOWLEDGE)

            await channel.send(f"☀️ **Daily Studio Check-in!**\n\n{post_content}\n\n*Have a wonderful day!*")
        else:
            print(f"Error: Channel with ID {DAILY_POST_SETTINGS['channel_id']} not found. Disabling daily posts.")
            DAILY_POST_SETTINGS['enabled'] = False 
            
    except Exception as e:
        print(f"Error sending daily post: {e}")


@bot.tree.command(name="setdailyposts", description="Enable or disable the daily post task and set its channel.")
@discord.app_commands.describe(
    action="Enable or disable the daily post.",
    channel="The channel where the daily post should be sent."
)
async def set_daily_posts_command(interaction: discord.Interaction, action: str, channel: discord.TextChannel):
    """Sets the channel and state for the daily scheduled post."""
    action = action.lower()
    
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
        DAILY_POST_SETTINGS['channel_id'] = None 

        await interaction.response.send_message(
            "❌ Daily posts are now **disabled**.",
            ephemeral=True
        )
    else:
         await interaction.response.send_message(
            "Invalid action. Please use `/setdailyposts enabled <channel>` or `/setdailyposts disabled <channel>`.",
            ephemeral=True
        )

# --- START THE BOT ---
if __name__ == "__main__":
    if not DISCORD_TOKEN or not GEMINI_API_KEY or not CLIENT_ID:
        print("\n--- CRITICAL ERROR: REQUIRED ENVIRONMENT VARIABLES MISSING ---")
        print("Please ensure DISCORD_TOKEN, GEMINI_API_KEY, and CLIENT_ID are set in your Render environment variables or in a local .env file.")
    else:
        bot.run(DISCORD_TOKEN)
