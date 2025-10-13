# utils/image_store.py
import random
import os
from pathlib import Path
from typing import Optional, Tuple
import discord

class ImageStore:
    """
    Simple helper to pick images from a static folder and return discord.File or public URL.
    """
    def __init__(self, static_dir: str = "static/banners", base_url: Optional[str] = None):
        self.static_dir = Path(static_dir)
        self.static_dir.mkdir(parents=True, exist_ok=True)
        self.base_url = base_url  # e.g., https://<your-render-domain>/static/banners/

    def list_images(self):
        return [p for p in self.static_dir.iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".gif")]

    def pick_attachment(self) -> Optional[Tuple[discord.File, str]]:
        imgs = self.list_images()
        if not imgs:
            return None
        chosen = random.choice(imgs)
        file = discord.File(fp=str(chosen), filename=chosen.name)
        return file, chosen.name

    def pick_url(self) -> Optional[str]:
        if not self.base_url:
            return None
        imgs = self.list_images()
        if not imgs:
            return None
        chosen = random.choice(imgs)
        return f"{self.base_url.rstrip('/')}/{chosen.name}"
