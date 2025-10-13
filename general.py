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
    """Handles core bot events, automod processing, XP granting, LLM-powered responses, and ping responses."""

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
        # This will hold your studio context for LLM grounding (pre-loading in main bot file)
        self.studio_context = self.bot.get_studio_context()
        # {guild_id: bool} to track if auto-speaking is enabled
        self.autospeak_enabled = {} 
        # {guild_id: channel_id} to track the LLM's primary channel (optional but useful)
        self.llm_channel_id = {} 

    # --- Commands (using '/' prefix as requested) ---

    @commands.command(name='autospeak', help='Toggle or set the dedicated channel for Lagoona\'s LLM-powered responses.')
    @commands.has_permissions(administrator=True)
    async def autospeak(self, ctx, action: str, channel: discord.TextChannel = None):
        """
        Command: /autospeak enable [#channel] | /autospeak disable
        Toggles Lagoona's automatic response feature using the Gemini API.
        """
        guild_id = ctx.guild.id
        action = action.lower()

        if action == 'enable':
            self.autospeak_enabled[guild_id] = True
            
            if channel:
                self.llm_channel_id[guild_id] = channel.id
                await ctx.send(f"✅ **Auto-Speaking ENABLED** and set to channel: {channel.mention}. Lagoona will now answer general questions in this channel using her studio knowledge.")
            else:
                self.llm_channel_id.pop(guild_id, None) # Clear designated channel if enabling globally
                await ctx.send("✅ **Auto-Speaking ENABLED** globally. Lagoona will answer general questions in any channel using her studio knowledge.")
        
        elif action == 'disable':
            self.autospeak_enabled[guild_id] = False
            self.llm_channel_id.pop(guild_id, None)
            await ctx.send("❌ **Auto-Speaking DISABLED**. Lagoona will now only respond when explicitly pinged or via slash commands.")
        
        else:
            await ctx.send("❓ Invalid action. Please use `/autospeak enable [#channel]` or `/autospeak disable`.")

    @commands.command(name='automod', help='Toggle AutoMod based on Discord/SG/Roblox rules.')
    @commands.has_permissions(administrator=True)
    async def automod_toggle(self, ctx, action: str):
        """
        Command: /automod enable | /automod disable
        Toggles the comprehensive auto-moderation system.
        """
        guild_id = ctx.guild.id
        action = action.lower()

        if action == 'enable':
            self.bot.automod_enabled[guild_id] = True
            await ctx.send("✅ **AutoMod ENABLED**. Lagoona is now actively monitoring for rule violations, raids, mass-pings, and alternative accounts.")
        
        elif action == 'disable':
            self.bot.automod_enabled[guild_id] = False
            await ctx.send("❌ **AutoMod DISABLED**. Please be aware that the server is now less protected against major threats.")
        
        else:
            await ctx.send("❓ Invalid action. Please use `/automod enable` or `/automod disable`.")


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
                # Ensure randomized banner is used for welcome message
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
                # Ensure randomized banner is used for goodbye message
                embed.set_image(url=self.bot.get_random_banner_url())
                await channel.send(embed=embed)

        # 2. Update invite cache (removed use tracking)
        if guild.id in self.bot.guild_invites:
            try:
                invites_after_leave = await guild.invites()
                self.bot.guild_invites[guild.id] = {invite.code: invite.uses for invite in invites_after_leave}
            except discord.errors.Forbidden:
                pass
                
    # New event to ensure randomized image for *any* announcement/embed sent by Lagoona
    @commands.Cog.listener()
    async def on_send_announcement(self, channel, content=None, embed=None):
        """
        Custom listener for announcement events to ensure a randomized banner is added. 
        Requires the main bot file to call bot.dispatch('send_announcement', channel, content, embed)
        """
        if embed and not embed.image.url:
            # Only add a random banner if the embed doesn't already have one
            # This ensures images are randomized per announcement
            embed.set_image(url=self.bot.get_random_banner_url())
        
        if channel:
            await channel.send(content if content is not None else "", embed=embed)


    async def on_message(self, message):
        # Ignore bot messages or DMs
        if message.author.bot or not message.guild:
            return

        guild = message.guild
        member = message.author
        
        # --- 1. Automod Check (Order is crucial for security) ---
        
        is_bypassed = member.id in self.bot.bypass_users.get(guild.id, [])
        is_deleted = False 
        
        if not is_bypassed and self.bot.automod_enabled.get(guild.id, True):
             # Run the strict automod logic
             is_deleted = await self.process_automod(message)
             if is_deleted:
                 return # Stop all further processing if the message was deleted
        
        # --- 2. Ping Response Check ---
        
        is_bot_pinged = self.bot.user in message.mentions
        if is_bot_pinged:
            # If pinged, provide a conversational ping response
            response = random.choice(self.ping_messages)
            embed = Embed(description=response, color=discord.Color.teal())
            await message.channel.send(f"{message.author.mention}", embed=embed)
            # Continue to check XP and process command/LLM
        
        # Check for any of the bot's owned roles being mentioned
        bot_member = message.guild.get_member(self.bot.user.id)
        if bot_member:
            for role in bot_member.roles:
                if role.mention in message.content:
                    response = random.choice(self.role_ping_messages)
                    embed = Embed(description=response, color=discord.Color.light_grey())
                    # Send a subtle acknowledgement, deleting after a short time
                    await message.channel.send(embed=embed, delete_after=10)
                    # Continue to check XP and process command/LLM

        # --- 3. Command and XP Granting ---
        # Process any standard or slash commands first
        await self.bot.process_commands(message)

        # Grant XP if the message is NOT a command (i.e., it didn't start with the prefix) and was not deleted
        if not message.content.startswith(self.bot.command_prefix) and not is_deleted:
            xp_amount = random.randint(15, 25)
            new_level = self.bot.add_xp(member.id, xp_amount)
            
            if new_level is not None:
                await self.bot.send_level_up_message(member, new_level)

            # --- 4. Gemini API Response (Answering questions anywhere) ---
            # If auto-speaking is enabled, and the message wasn't a command/deleted, see if it's a question for the LLM.
            if self.autospeak_enabled.get(guild.id, False) or is_bot_pinged:
                
                designated_channel_id = self.llm_channel_id.get(guild.id)
                
                # If a designated channel is set, only respond there (unless pinged)
                if designated_channel_id is None or designated_channel_id == message.channel.id or is_bot_pinged:
                    await self.process_llm_response(message)


    async def process_llm_response(self, message):
        """
        Processes messages using the Gemini API, ensuring Lagoona answers questions 
        even if not pinged (if auto-speak is enabled).
        """
        
        # Use a more relaxed heuristic now that we have /autospeak control
        content = message.content.strip()
        is_a_potential_query = len(content) >= 15 and not content.startswith(('http', 'www', 'discord.gg'))
        
        # If the bot was pinged, we should always try to respond unless the message is trivial
        if self.bot.user not in message.mentions and not is_a_potential_query:
            return # Ignore non-pinged, non-substantive messages
            
        # Set up a brief "typing" indicator to show the bot is thinking
        async with message.channel.typing():
            try:
                # Call the external method (assumed to be on the bot object) which uses the Gemini API
                response_text = await self.bot.call_gemini_api(
                    prompt=content,
                    studio_context=self.studio_context
                )

                if response_text:
                    embed = Embed(
                        description=response_text, 
                        color=discord.Color.blurple()
                    )
                    embed.set_footer(text="Powered by Gemini for Stargame Studio knowledge.")
                    await message.channel.send(embed=embed)
                    
            except Exception as e:
                # Log any errors quietly and don't respond to the user
                print(f"Gemini API call failed for message '{content[:30]}...': {e}")
                
    async def process_automod(self, message):
        """
        Strictly processes messages against SG/Discord/Roblox rules, including mass pings, 
        raids, alternate accounts, swear words, and bad content.
        """
        guild = message.guild
        member = message.author
        content = message.content.lower()
        deleted = False
        
        # Heuristic for new account/alt account (joined within the last 5 minutes)
        is_new_member = (datetime.now(self.bot.AST_TIMEZONE) - member.joined_at) < timedelta(minutes=5)

        # 1. Bad words / Swear words / Bad Content / Invite Link check
        is_bad_content = any(word in content for word in self.bot.SG_RULES['BAD_WORDS'])
        has_invite_link = any(invite in content for invite in ['discord.gg/', 'discordapp.com/invite/', 'dsc.gg/'])
        
        if is_bad_content or has_invite_link:
            try:
                await message.delete()
                deleted = True
            except:
                pass
            
            mute_time = timedelta(minutes=30)
            reason = "AUTOMOD: Use of inappropriate content or unauthorized invite links (SG/Discord/Roblox Rule Violation)."
            
            try:
                # Timeout member (Discord term for temporary mute)
                await member.timeout(mute_time, reason=reason)
                log_embed = Embed(title="🔇 User Muted (Bad Content/Invite)", description=f"**User:** {member.mention}\n**Action:** 30 Minute Timeout\n**Reason:** {reason}\n**Channel:** {message.channel.mention}", color=discord.Color.orange())
                await member.send(f"You have been automatically muted in **{guild.name}** for 30 minutes due to rule-breaking content. Please review the rules.", silent=True)
                await self.bot.log_event(guild, log_embed, 'mod')
            except discord.errors.Forbidden:
                print("Lacking permissions to mute user.")
            return deleted

        # 2. Raiding / Massive Ping / Spam Detection
        is_mass_ping = len(message.mentions) >= self.bot.SG_RULES['MASS_MENTION_THRESHOLD'] and len(message.content) < 100
        
        # Aggressive check: mass ping OR (new member spamming long messages)
        is_spamming = is_mass_ping or (is_new_member and len(message.content) > 100 and message.channel.last_message.author != member)
        
        if is_spamming:
            
            ban_reason = "AUTOMOD: Instant Ban - Attempted server raiding/mass mention spam or suspected alternative account/bot spam."
            
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
            log_embed = Embed(title="🚨 RAID/SPAM ATTEMPT DETECTED & SERVER LOCKED 🚨", description=f"**Perpetrator:** {member.mention} (`{member.id}`)\n**New Account:** {'Yes' if is_new_member else 'No'}\n**Action Taken:** Instant Ban & Server Lockdown", color=discord.Color.red())
            await self.bot.log_event(guild, log_embed, 'mod')

            # Schedule Server Unlock (Non-blocking async wait)
            await asyncio.sleep(300) # Wait 5 minutes before unlocking
            for channel in guild.channels:
                if isinstance(channel, discord.TextChannel):
                    try:
                        # Only unlock if the channel's default role permissions were set to deny sending
                        default_perms = channel.overwrites_for(guild.default_role)
                        if default_perms.send_messages is False:
                             await channel.set_permissions(guild.default_role, send_messages=True, reason="AUTOMOD: Server Unlock - Raid threat subsided.")
                    except discord.errors.Forbidden:
                        pass
            
            unlock_embed = Embed(title="✅ Server Unlocked", description="The server has been automatically unlocked after the raid threat subsided.", color=discord.Color.green())
            await self.bot.log_event(guild, unlock_embed, 'mod')
            return deleted
            
        return deleted

async def setup(bot):
    await bot.add_cog(GeneralFeatures(bot))
