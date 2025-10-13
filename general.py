import discord
from discord import Embed
from discord.ext import commands
from datetime import datetime, timedelta
import random
import asyncio
from http.server import SimpleHTTPRequestHandler, HTTPServer
import os

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

class GeneralFeatures(commands.Cog):
    """Handles core bot events, automod processing, XP granting, and ping responses."""

    def __init__(self, bot):
        self.bot = bot
        # Responses Lagoona can choose from when pinged
        self.ping_messages = [
            "Hi there! How can I assist the Stargame Studio team today? Run `/help` to see my commands.",
            "Lagoona at your service! Let me know what you need.",
            "You pinged the massive Community Manager! Ready for a command or a quick chat.",
            "I heard that! Use `/help` for a full list of my features."
        ]
        
        # Responses for role pings
        self.role_ping_messages = [
            "I see a key role was pinged! If this was an announcement, I've got it logged. Need help?",
            "Role mentioned! Just ensuring the correct attention is given.",
            "Acknowledging the role mention. Running `/help` shows what I can do for the team."
        ]

    # --- Events ---

    async def on_member_join(self, member):
        guild = member.guild

        # 1. Invite Tracker (Log who invited whom)
        if guild.id in self.bot.guild_invites:
            try:
                invites_after_join = await guild.invites()
                new_invite = None
                old_invites = self.bot.guild_invites[guild.id]
                
                # Find the invite that increased in uses
                for invite in invites_after_join:
                    if invite.uses > old_invites.get(invite.code, 0):
                        new_invite = invite
                        break
                
                self.bot.guild_invites[guild.id] = {invite.code: invite.uses for invite in invites_after_join}

                invite_message = "I couldn't track who invited this member (Missing permissions)."
                if new_invite and new_invite.inviter:
                    invite_message = f"**Invited By:** {new_invite.inviter.mention} (`{new_invite.inviter.name}`)\n**Invite Code:** `{new_invite.code}` (Uses: `{new_invite.uses}`)"
                
                # Log the invite event
                invite_embed = Embed(
                    title="👤 Member Joined and Invite Tracked",
                    description=f"{member.mention} has joined the server.",
                    color=discord.Color.blue(),
                    timestamp=datetime.now(self.bot.AST_TIMEZONE)
                )
                invite_embed.add_field(name="Details", value=invite_message, inline=False)
                invite_embed.set_footer(text=f"User ID: {member.id}")
                await self.bot.log_event(guild, invite_embed, 'app_invite') 

            except discord.errors.Forbidden:
                print(f"Cannot track invites in {guild.name}.")
        
        # 2. Welcome Message
        config = self.bot.welcome_goodbye_config.get(guild.id, {})
        if config.get('type') == 'welcome':
            channel = self.bot.get_channel(config.get('channel_id'))
            if channel:
                embed = Embed(
                    title=f"WELCOME TO STARGAME STUDIO, {member.name}!",
                    description=config.get('message', 'Hope you enjoy your stay!'),
                    color=discord.Color.from_rgb(10, 10, 50)
                )
                embed.set_image(url=self.bot.get_random_banner_url())
                await channel.send(member.mention, embed=embed)

    async def on_member_remove(self, member):
        guild = member.guild
        
        # 1. Goodbye Message
        config = self.bot.welcome_goodbye_config.get(guild.id, {})
        if config.get('type') == 'goodbye':
            channel = self.bot.get_channel(config.get('channel_id'))
            if channel:
                embed = Embed(
                    title=f"GOODBYE, {member.name}...",
                    description=config.get('message', 'Sad to see you go.'),
                    color=discord.Color.dark_red()
                )
                embed.set_image(url=self.bot.get_random_banner_url())
                await channel.send(embed=embed)

        # 2. Update invite cache (removed use tracking)
        if guild.id in self.bot.guild_invites:
            try:
                invites_after_leave = await guild.invites()
                self.bot.guild_invites[guild.id] = {invite.code: invite.uses for invite in invites_after_leave}
            except discord.errors.Forbidden:
                pass

    async def on_message(self, message):
        # Ignore bot messages or DMs
        if message.author.bot or not message.guild:
            return

        guild = message.guild
        member = message.author

        # --- 1. Ping and Role Response Check ---
        
        # Check for direct bot mention (e.g., @Lagoona)
        if self.bot.user in message.mentions:
            response = random.choice(self.ping_messages)
            embed = Embed(description=response, color=discord.Color.teal())
            await message.channel.send(f"{message.author.mention}", embed=embed)
            return

        # Check for any of the bot's owned roles being mentioned
        bot_member = message.guild.get_member(self.bot.user.id)
        if bot_member:
            for role in bot_member.roles:
                if role.mention in message.content:
                    response = random.choice(self.role_ping_messages)
                    embed = Embed(description=response, color=discord.Color.light_grey())
                    # Send a subtle acknowledgement, deleting after a short time
                    await message.channel.send(embed=embed, delete_after=10)
                    return

        # --- 2. Automod Check (and Bypass) ---
        
        is_bypassed = member.id in self.bot.bypass_users.get(guild.id, [])

        if not is_bypassed and self.bot.automod_enabled.get(guild.id, True):
             # Run the strict automod logic
             is_deleted = await self.process_automod(message)
             if is_deleted:
                 return # Stop processing commands or XP if message was deleted
        
        # --- 3. XP Granting ---
        # Grant XP if the message is not a command and was not deleted by automod
        if not message.content.startswith(self.bot.command_prefix):
            xp_amount = random.randint(15, 25)
            new_level = self.bot.add_xp(member.id, xp_amount)
            
            if new_level is not None:
                await self.bot.send_level_up_message(member, new_level)

        # Process any standard or slash commands
        await self.bot.process_commands(message)

    async def process_automod(self, message):
        """Strictly processes messages against SG/Discord/Roblox rules."""
        guild = message.guild
        member = message.author
        content = message.content.lower()
        deleted = False

        # 1. Bad words equals mute or warn
        is_bad_word = any(word in content for word in self.bot.SG_RULES['BAD_WORDS'])
        
        if is_bad_word:
            try:
                await message.delete()
                deleted = True
            except:
                pass
            
            mute_time = timedelta(minutes=10)
            reason = "AUTOMOD: Use of inappropriate language (SG/Discord/Roblox Rule Violation)."
            
            try:
                await member.timeout(mute_time, reason=reason)
                log_embed = Embed(title="🔇 User Muted (Bad Word)", description=f"**User:** {member.mention}\n**Action:** 10 Minute Timeout\n**Reason:** {reason}\n**Message Snippet:** `{message.content[:50]}...`", color=discord.Color.orange())
                await member.send(f"You have been automatically muted in **{guild.name}** for 10 minutes due to rule-breaking language. Please review the rules.", silent=True)
                await self.bot.log_event(guild, log_embed, 'mod')
            except discord.errors.Forbidden:
                print("Lacking permissions to mute user.")
            return deleted

        # 2. Raiding / Massive Ping equals temporary shutdown and ban
        if len(message.mentions) >= self.bot.SG_RULES['MASS_MENTION_THRESHOLD'] and len(message.content) < 100:
            
            ban_reason = "AUTOMOD: Instant Ban - Attempted server raiding/mass mention spam."
            
            try:
                await message.delete()
                deleted = True
                await member.ban(reason=ban_reason)
            except discord.errors.Forbidden:
                print("Lacking permissions to handle raid attempt.")
                return deleted

            # Temporary Server Lockdown
            locked_channels = []
            for channel in guild.channels:
                if isinstance(channel, discord.TextChannel) and channel.permissions_for(guild.default_role).send_messages:
                    try:
                        await channel.set_permissions(guild.default_role, send_messages=False, reason="AUTOMOD: Server Lockdown due to raid attempt.")
                        locked_channels.append(channel.mention)
                    except discord.errors.Forbidden:
                        pass
            
            # Log and Report
            log_embed = Embed(title="🚨 RAID ATTEMPT DETECTED & SERVER LOCKED 🚨", description=f"**Perpetrator:** {member.mention} (`{member.id}`)\n**Action Taken:** Instant Ban & Server Lockdown", color=discord.Color.red())
            await self.bot.log_event(guild, log_embed, 'mod')

            # Schedule Server Unlock (Non-blocking async wait)
            await asyncio.sleep(300) # Wait 5 minutes before unlocking
            for channel in guild.channels:
                if channel.mention in locked_channels:
                    try:
                        await channel.set_permissions(guild.default_role, send_messages=True, reason="AUTOMOD: Server Unlock - Raid threat subsided.")
                    except discord.errors.Forbidden:
                        pass
            
            unlock_embed = Embed(title="✅ Server Unlocked", description="The server has been automatically unlocked after the raid threat subsided.", color=discord.Color.green())
            await self.bot.log_event(guild, unlock_embed, 'mod')
            return deleted
            
        return deleted

async def setup(bot):
    await bot.add_cog(GeneralFeatures(bot))
