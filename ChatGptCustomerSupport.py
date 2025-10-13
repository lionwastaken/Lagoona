import os
import openai
from typing import Optional, Dict

class OpenAILLMService:
    """
    A service class to manage interactive, grounded customer support chats
    using the OpenAI API (ChatGPT).

    It enforces a friendly, realistic persona and uses provided studio context
    for reliable, up-to-date information.
    """

    def __init__(self, studio_context: str):
        """
        Initializes the OpenAI client and sets the studio context for grounding.
        
        Args:
            studio_context: A comprehensive string containing all necessary
                            Stargame Studio policies, roadmap, and rules.
        """
        # The key is expected in the environment variable CHATGPT_API_KEY
        api_key = os.getenv("CHATGPT_API_KEY")
        if not api_key:
            raise ValueError("CHATGPT_API_KEY environment variable not set.")
        
        # Initialize the OpenAI client
        self.client = openai.OpenAI(api_key=api_key)
        
        # Store the studio context
        self.studio_context = studio_context

        # Define the model to use for chat
        self.model = "gpt-3.5-turbo" # Excellent balance of speed and quality for support

    def _get_system_prompt(self) -> str:
        """
        Constructs the system prompt to define the bot's persona and mandate
        for using the studio context.
        """
        # Note: We enforce the "Lagoona" persona and style (short, realistic, friendly)
        return (
            "You are Lagoona, the official Community Manager and Assistant for Stargame Studio. "
            "Your role is to provide customer support and answer questions about the studio. "
            "Your responses MUST be **interactive, short (max 3 sentences), friendly, and realistic** for a community chat environment. "
            "You are an expert on all studio information provided in the CONTEXT below. "
            "Always prioritize the CONTEXT over general knowledge to ensure reliability and accuracy. "
            "If the answer is not in the context, politely state that you do not have that specific information yet."
            "Your creator is miyahs.sb on Discord!"
            "\n\n--- CONTEXT: ---\n"
            f"{self.studio_context}"
            "\n--- END OF CONTEXT ---"
        )

    async def get_customer_support_response(self, user_prompt: str, user_id: str) -> Optional[str]:
        """
        Sends a query to the OpenAI API and returns a generated response.
        
        Args:
            user_prompt: The user's question or statement.
            user_id: The ID of the user (used for log tracking/context management).
            
        Returns:
            The generated response text, or None if the API call fails.
        """
        # Note: We simulate an async call using asyncio.to_thread for the synchronous openai client
        # This prevents blocking the main bot thread.
        try:
            # We use the system prompt to establish rules and inject the context
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7, # Allows for slight variation while staying factual
                max_tokens=150 # Enforce short, concise responses
            )

            # Extract the response text
            return response.choices[0].message.content.strip()

        except openai.APIError as e:
            print(f"OpenAI API Error for user {user_id}: {e}")
            return "I apologize, but I'm having trouble connecting to my knowledge base right now. Please try asking again in a moment!"
        except Exception as e:
            print(f"An unexpected error occurred in LLM service for user {user_id}: {e}")
            return None


# --- Comprehensive Stargame Studio Context ---
# This combines all the reliable information from your documents for grounding the LLM.

STARGAME_STUDIO_CONTEXT = """
**Studio Overview:**
Stargame Studio is a youth-powered creative force dedicated to turning ROBLOX community ideas into stunning realities. We specialize in immersive experiences (like our flagship project, Rampage Royale), UGC accessories, 2D clothing, and original artwork. Our team is driven by friendship, open communication, and teamwork. Our core mission is to empower young talent and foster a positive, collaborative environment.

**Artist Initiative:**
Stargame Studio champions the resurgence of original human artistry (digital and traditional) over AI-generated art. Clients can browse a diverse portfolio and directly commission a preferred Stargame Studio artist.

**Compensation Details:**
* **Active Developers/Designers/Creators:** Usually up to 10,000 Robux per project.
* **Absent or Commission Only Members:** May receive up to 2,000 Robux (absent) or 450 Robux (commission) or whatever amount offered at the time.
* **Payment Type:** We **DO NOT** use external payments (USD, Giftcards, Nitro). All payments are in Robux.
* **Revenue Split:** Developers get a 2% revenue split on the project they work on.
* **Credits/Portfolio Use:** All projects include credits. Developers may post their work on their portfolio or social media once it has been **publicly announced by staff or lionelclementofficial**.

**Studio Rules:**
Rules are simple: be respectful to everyone, do not harass, humiliate, or intent harm publicly or privately, and be explicitly appropriate server-wise and otherwise. Treat others fairly and nicely.

**Project Timeline:**
Developers are usually given up to 2 weeks or more or less on a project, depending on complexity.

**Developer Credits:**
QA Testers: Gtnocayt, Bling, crystalcat057_24310, scorpio_9406
Scripters: matiasgrief, midnightangel05_11
Music Composers and or SFX: thatnutcase, stavrosmichalatos
Artists: cigerds, poleyz, cleonagoesblublub, shelley_bourie._., luvlinda., cornletttozo, 0.koala.0, four_diel_59931, honeypah, polarplatypus, cosmocat823, angfries
More devs will come soon!

**Studio Roadmap:**
* **Late 2025:**
    * Relax Hangout is expected to finish by late October and re-released by month-end or early November.
    * Everyday Shorts/Reels are expected to be set up and published daily from November 2025 to January 2026.
    * Veccera Cafe is expected to be finished and released somewhere from now until December 2025.
* **2026:**
    * New studio icons will be designed (the current banner by Poleyz remains for a while).
    * Relax Hangout and Veccera Cafe will receive small updates.
    * Development will begin on a new game: **The Outbreak (Adventure and Horror)**.
    * We expect to establish leaders for every role: Scripters, Builders, Modelers, UI Designers, Lighting Supervisor, VFX Designer, SFX/Music Composer, and VA Supervisor.
"""

# Example of how you would initialize this service in your main bot file:
# 
# import asyncio
# from openai_llm_service import OpenAILLMService, STARGAME_STUDIO_CONTEXT
#
# # Assuming this is in your main bot setup:
# try:
#     # 1. Initialize the service once
#     openai_service = OpenAILLMService(studio_context=STARGAME_STUDIO_CONTEXT)
# except ValueError as e:
#     print(f"Could not initialize OpenAI service: {e}")
#
# # 2. Usage example inside a command or on_message event:
# # 
# # async def handle_customer_query(self, message):
# #     user_prompt = message.content
# #     user_id = str(message.author.id)
# #     
# #     response = await openai_service.get_customer_support_response(
# #         user_prompt=user_prompt,
# #         user_id=user_id
# #     )
# #     if response:
# #         await message.channel.send(response)
