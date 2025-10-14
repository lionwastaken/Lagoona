# cogs/autoresponder.py
import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import asyncio
import logging
import os
import json
import re

logger = logging.getLogger("autoresponder")

# In-memory toggle (you can later store this in a DB or JSON)
auto_enabled = set()

# --- Helper: call Gemini or ChatGPT API ---
async def call_llm_api(prompt: str) -> str:
    """Send text to Gemini or ChatGPT depending on which key is available."""
    gemini_key = os.environ.get("GEMINI_API_KEY")
    openai_key = os.environ.get("CHATGPT_API_KEY")

    try:
        async with aiohttp.ClientSession() as session:
            # --- Gemini ---
            if gemini_key:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={gemini_key}"
                payload = {"contents": [{"parts": [{"text": prompt}]}]}
                async with session.post(url, json=payload) as resp:
                    data = await resp.json()
                    text = (
                        data.get("candidates", [{}])[0]
                        .get("content", {})
                        .get("parts", [{}])[0]
                        .get("text", "I’m not sure what to say 🌊")
                    )
                    return text.strip()

            # --- ChatGPT (OpenAI) ---
            elif openai_key:
                url = "https://api.openai.com/v1/chat/completions"
                headers = {"Authorization": f"Bearer {openai_key}"}
                payload = {
                    "model": "gpt-3.5-turbo",
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are Lagoona, a cheerful ocean-themed Discord assistant. "
                                "Keep answers friendly, concise, and avoid profanity. "
                                "If someone swears, respond calmly or playfully correct them."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.8,
                }
                async with session.post(url, headers=headers, json=payload) as resp:
                    data = await resp.json()
                    if "choices" in data:
                        return data["choices"][0]["message"]["content"].strip()
                    else:
                        logger.warning("OpenAI response: %s", data)
                        return "I'm having a little trouble thinking right now 🌀"

            else:
                return "No LLM API key configured in environment."

    except Exception as e:
        logger.exception("LLM API error: %s", e)
        return "Oops, my brain hit a wave—try again later 🌊"


# --- Cog ---
class AutoResponder(commands.Cog):
    """Automatically chats in channels when enabled."""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="autorespond", description="Toggle Lagoona's auto-chat mode in this channel.")
    @app_commands.describe(mode="Choose 'on' or 'off'")
    async def autorespond(self, interaction: discord.Interaction, mode: str):
        mode = mode.lower()
        channel_id = interaction.channel.id

        if mode == "on":
            auto_enabled.add(channel_id)
            await interaction.response.send_message("💬 Auto-respond mode **enabled** in this channel!", ephemeral=True)
        elif mode == "off":
            auto_enabled.discard(channel_id)
            await interaction.response.send_message("🔕 Auto-respond mode **disabled**.", ephemeral=True)
        else:
            await interaction.response.send_message("Please use `/autorespond on` or `/autorespond off`.", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore bots & DMs
        if message.author.bot or not message.guild:
            return

        # Only respond in enabled channels
        if message.channel.id not in auto_enabled:
            return

        # Optional: ignore very short or command-like messages
        if len(message.content.strip()) < 2 or message.content.startswith("/"):
            return

        # Avoid replying to herself
        if message.author == self.bot.user:
            return

        # Clean content (you can strip mentions, emojis, etc.)
        text = re.sub(r"<@!?(\d+)>", "", message.content).strip()

        # Create typing effect & call LLM
        async with message.channel.typing():
            reply = await call_llm_api(text)
            await asyncio.sleep(0.5)

        # Send reply tagging user
        try:
            await message.reply(f"{message.author.mention} {reply}")
        except discord.HTTPException as e:
            logger.exception("Failed to send auto-response: %s", e)


async def setup(bot: commands.Bot):
    await bot.add_cog(AutoResponder(bot))
