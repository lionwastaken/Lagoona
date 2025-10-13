import discord
from discord import app_commands, Embed
from discord.ext import commands, tasks
from datetime import datetime
import pytz

class CommunityFeatures(commands.Cog):
    """Handles XP, Welcome/Goodbye, Daily Posts, and the Application System."""

    def __init__(self, bot):
        self.bot = bot
        self.xp_leaderboard_post.start()
        self.check_daily_posts.start()

    def cog_unload(self):
        self.xp_leaderboard_post.cancel()
        self.check_daily_posts.cancel()

    # --- Commands ---
    
    @app_commands.command(name="setwelcomegoodbye", description="Set up or disable welcome and goodbye messages in a channel.")
    @app_commands.describe(type="Type of message (welcome or goodbye).", message="The message content to display.", channel="The channel for the message.")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_welcome_goodbye(self, interaction: discord.Interaction, type: str, message: str, channel: discord.TextChannel):
        type = type.lower()
        if type not in ['welcome', 'goodbye']:
            return await interaction.response.send_message("Invalid type. Choose 'welcome' or 'goodbye'.", ephemeral=True)

        guild_id = interaction.guild_id
        
        self.bot.welcome_goodbye_config[guild_id] = {
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

        self.bot.daily_posts_config[interaction.guild_id] = {
            'channel_id': channel.id,
            'role_id': role.id,
            'time_ast': time_ast
        }
        
        await interaction.response.send_message(
            f"Daily post for **{role.name}** is set up in {channel.mention} at **{time_ast} AST**!",
            ephemeral=True
        )
    
    # --- Application System Classes and Command ---

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
                # Forward to the guild owner/manager
                await self.manager.send(f"**New Stargame Studio Application Submitted!**\n\n{summary_text}")
                await interaction.response.send_message("✅ Your application has been submitted successfully! The manager has been notified with all your answers.", ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"❌ Failed to send the application to the manager. Error: {e}", ephemeral=True)


    @app_commands.command(name="completeSGApplication", description="Start or configure the Stargame Studio application process (10 questions max).")
    @app_commands.describe(action="Start the application or set the questions (manager only).")
    async def completesgapplication(self, interaction: discord.Interaction, action: str):
        guild_id = interaction.guild_id
        action = action.lower()
        
        if action == 'setquestions':
            if not interaction.user.guild_permissions.manage_guild:
                return await interaction.response.send_message("Only members with 'Manage Server' permissions can set application questions.", ephemeral=True)
            
            modal = self.ApplicationQuestionModal(self.bot, guild_id)
            await interaction.response.send_modal(modal)
            return

        elif action == 'start':
            questions = self.bot.application_questions.get(guild_id)
            if not questions:
                return await interaction.response.send_message("The manager has not yet set the application questions. Please ask a manager to use `/completeSGApplication setquestions`.", ephemeral=True)

            manager = interaction.guild.owner # Guild owner is the default recipient
            
            modal = self.ApplicationResponseModal(self.bot, questions, manager)
            await interaction.response.send_modal(modal)
            return

        else:
            await interaction.response.send_message("Invalid action. Use `start` or `setquestions`.", ephemeral=True)
            
    # --- Background Tasks ---

    @tasks.loop(minutes=1)
    async def check_daily_posts(self):
        now_ast = datetime.now(self.bot.AST_TIMEZONE)
        current_time_str = now_ast.strftime('%H:%M')
        
        for guild_id, config in self.bot.daily_posts_config.items():
            if config.get('time_ast') == current_time_str:
                guild = self.bot.get_guild(guild_id)
                channel = self.bot.get_channel(config.get('channel_id'))
                role = guild.get_role(config.get('role_id')) if guild else None
                
                if channel and role:
                    try:
                        post_content = "This is your scheduled daily reminder and role ping! Stay productive, Stargame Studio! ⭐"
                        
                        embed = Embed(
                            title="⭐ Daily Studio Ping & Link",
                            description=f"{post_content}\n\n[**Click Here for the Group Link**](https://www.roblox.com/groups/0000000/Stargame-Studio-Placeholder)",
                            color=discord.Color.from_rgb(255, 200, 50)
                        )
                        embed.set_image(url=self.bot.get_random_banner_url())
                        
                        await channel.send(role.mention, embed=embed)
                    except Exception as e:
                        print(f"Failed to send daily post in {guild_id}: {e}")

    @tasks.loop(weeks=1)
    async def xp_leaderboard_post(self):
        await self.bot.wait_until_ready()
        
        for guild in self.bot.guilds:
            log_channel = await self.bot.get_log_channel(guild.id)
            if not log_channel or not self.bot.server_logs_enabled.get(guild.id, False):
                continue

            sorted_xp = sorted(
                [(user_id, xp) for user_id, xp in self.bot.xp_data.items()],
                key=lambda item: item[1],
                reverse=True
            )
            
            top_10 = sorted_xp[:10]
            leaderboard_text = ""
            for i, (user_id, xp) in enumerate(top_10):
                member = guild.get_member(user_id)
                if member:
                    xp_total, level, _ = self.bot.get_user_xp_level(user_id)
                    leaderboard_text += f"**{i+1}.** {member.mention} - **Level {level}** ({xp_total} XP)\n"
            
            if leaderboard_text:
                embed = Embed(
                    title="🏆 Weekly XP Leaderboard Top 10",
                    description=leaderboard_text,
                    color=discord.Color.orange(),
                    timestamp=datetime.now(pytz.utc)
                )
                embed.set_image(url=self.bot.get_random_banner_url())
                await log_channel.send(embed=embed)


async def setup(bot):
    await bot.add_cog(CommunityFeatures(bot))
