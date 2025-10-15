# cogs/smart_autoresponder.py
import discord, aiohttp, asyncio, os, logging, random, re

from discord.ext import commands

logger = logging.getLogger("smart_autoresponder")

# --- random banner images for Lagoona's embeds / cards ---
BANNERS = [
    "https://example.com/lagoona_banner1.png",   # replace with your first image URL
    "https://example.com/lagoona_banner2.png",   # replace with your second image URL
]

# --- topics to avoid ---
BANNED_TOPICS = ("politic", "religion", "church", "bible", "islam", "christian",
                 "atheis", "football", "soccer", "nba", "cricket", "hockey")


# -------------------------------------------------
async def call_llm(prompt: str) -> str:
    """Query Gemini or ChatGPT with restricted topic scope."""
    gemini = os.getenv("GEMINI_API_KEY")
    openai = os.getenv("CHATGPT_API_KEY")
    try:
        async with aiohttp.ClientSession() as s:
            if gemini:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={gemini}"
                body = {"contents": [{
                    "parts": [{
                        "text": (
                            "You are Lagoona, a lively Roblox Studio assistant. "
                            "Answer only technical, creative-studio, or Roblox-related questions. "
                            "If the user asks about politics, religion, or sports, "
                            "say 'That’s outside the studio’s scope 🌊 let's keep it on Roblox topics!' "
                            f"User: {prompt}"
                        )
                    }]
                }]}
                async with s.post(url, json=body) as r:
                    d = await r.json()
                    return (
                        d.get("candidates", [{}])[0]
                        .get("content", {})
                        .get("parts", [{}])[0]
                        .get("text", "🌊 Hmm, can you rephrase that?")
                    )

            elif openai:
                url = "https://api.openai.com/v1/chat/completions"
                headers = {"Authorization": f"Bearer {openai}"}
                payload = {
                    "model": "gpt-3.5-turbo",
                    "messages": [
                        {"role": "system",
                         "content": (
                             "You are Lagoona, a lively Roblox Studio assistant. "
                             "Only discuss scripting, building, design, or studio questions. "
                             "Avoid politics, religion, or sports. "
                             "Politely redirect off-topic chats. "
                             "Use cheerful, short answers with emojis sometimes."
                         )},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.9,
                }
                async with s.post(url, headers=headers, json=payload) as r:
                    d = await r.json()
                    if "choices" in d:
                        return d["choices"][0]["message"]["content"].strip()
                    return "🌊 My thoughts got swept away—try again?"
        return "LLM key not configured."
    except Exception as e:
        logger.exception("LLM error: %s", e)
        return "💫 The waves are noisy—try again later!"
# -------------------------------------------------


class SmartResponder(commands.Cog):
    """Automatically reacts in announcement channels and chats anywhere Lagoona is mentioned."""

    def __init__(self, bot):
        self.bot = bot

    # --- REACT and SKIP in announcement channels ---
    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
    if after.author == self.bot.user and after.embeds:
        if before.embeds == after.embeds:
            return

        # 1️⃣ announcement / news channels
   if getattr(msg.channel, "is_news", lambda: False)():
    for emoji in ("⭐", "💛", "🫶"):
        try:
            await msg.add_reaction(emoji)
            await asyncio.sleep(0.4)   # small pause to avoid 429s
        except Exception:
            pass
    return

        # 2️⃣ normal chat: react if Lagoona mentioned by name or ping
        content_lower = msg.content.lower()

        if (self.bot.user and (self.bot.user.mentioned_in(msg) or "lagoona" in content_lower)):
            # avoid off-topic replies
            if any(t in content_lower for t in BANNED_TOPICS):
                await msg.reply("That’s outside the studio’s scope 🌊 let's keep it on Roblox topics!")
                return

            async with msg.channel.typing():
                reply_text = await call_llm(msg.content)
                await asyncio.sleep(0.3)

            # create lively embed with random banner
            embed = discord.Embed(
                title="🌊 Lagoona",
                description=reply_text,
                color=discord.Color.blurple()
            )
            embed.set_image(url=random.choice(BANNERS))

            try:
                await msg.reply(embed=embed, mention_author=False)
            except Exception as e:
                logger.warning("Embed reply failed: %s", e)

    # --- Replace Lagoona's own announcement cards with random banner image ---
    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if after.author == self.bot.user and after.embeds:
            for embed in after.embeds:
                embed.set_image(url=random.choice(BANNERS))
            try:
                await after.edit(embeds=after.embeds)
            except Exception:
                pass


async def setup(bot: commands.Bot):
    await bot.add_cog(SmartResponder(bot))
