# cogs/voice_commands.py
import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import yt_dlp
import logging

logger = logging.getLogger("voice")

# Suppress yt_dlp console spam
yt_dlp.utils.bug_reports_message = lambda: ""

class YTDLSource(discord.PCMVolumeTransformer):
    YTDL_OPTIONS = {
        "format": "bestaudio/best",
        "quiet": True,
        "nocheckcertificate": True,
        "ignoreerrors": True,
        "no_warnings": True,
        "default_search": "auto",
        "source_address": "0.0.0.0"
    }
    FFMPEG_OPTIONS = {
        "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
        "options": "-vn"
    }

    ytdl = yt_dlp.YoutubeDL(YTDLSource.YTDL_OPTIONS)

    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get("title")
        self.url = data.get("url")

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: cls.ytdl.extract_info(url, download=not stream))
        if "entries" in data:
            data = data["entries"][0]

        filename = data["url"] if stream else cls.ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **cls.FFMPEG_OPTIONS), data=data)


class VoiceCog(commands.Cog):
    """Handles voice channel join/leave and music playback"""

    def __init__(self, bot):
        self.bot = bot

    # --- Slash commands ---

    @app_commands.command(name="join", description="Join your current voice channel.")
    async def join(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not interaction.user.voice:
            await interaction.followup.send("You need to be in a voice channel first!", ephemeral=True)
            return

        channel = interaction.user.voice.channel
        if interaction.guild.voice_client is not None:
            await interaction.guild.voice_client.move_to(channel)
        else:
            await channel.connect()

        await interaction.followup.send(f"🎧 Joined **{channel.name}**!", ephemeral=True)

    @app_commands.command(name="leave", description="Disconnect Lagoona from voice.")
    async def leave(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if not vc:
            await interaction.response.send_message("I'm not connected to any voice channel!", ephemeral=True)
            return
        await vc.disconnect()
        await interaction.response.send_message("👋 Left the voice channel!", ephemeral=True)

    @app_commands.command(name="play", description="Play an audio or YouTube URL.")
    async def play(self, interaction: discord.Interaction, url: str):
        await interaction.response.defer(ephemeral=True)
        vc = interaction.guild.voice_client
        if not vc:
            if not interaction.user.voice:
                await interaction.followup.send("You need to be in a voice channel first!", ephemeral=True)
                return
            channel = interaction.user.voice.channel
            vc = await channel.connect()

        try:
            player = await YTDLSource.from_url(url, loop=self.bot.loop, stream=True)
            vc.play(player, after=lambda e: logger.error(e) if e else None)
            await interaction.followup.send(f"▶️ Now playing: **{player.title}**", ephemeral=False)
        except Exception as e:
            logger.exception("Error playing audio: %s", e)
            await interaction.followup.send("❌ Failed to play audio.", ephemeral=True)

    @app_commands.command(name="pause", description="Pause current audio.")
    async def pause(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if not vc or not vc.is_playing():
            await interaction.response.send_message("Nothing is playing.", ephemeral=True)
            return
        vc.pause()
        await interaction.response.send_message("⏸️ Paused playback.", ephemeral=True)

    @app_commands.command(name="resume", description="Resume playback.")
    async def resume(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if not vc or not vc.is_paused():
            await interaction.response.send_message("Nothing is paused.", ephemeral=True)
            return
        vc.resume()
        await interaction.response.send_message("▶️ Resumed playback.", ephemeral=True)

    @app_commands.command(name="stop", description="Stop playback and clear queue.")
    async def stop(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if not vc or not vc.is_playing():
            await interaction.response.send_message("Nothing is playing.", ephemeral=True)
            return
        vc.stop()
        await interaction.response.send_message("⏹️ Stopped playback.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(VoiceCog(bot))
