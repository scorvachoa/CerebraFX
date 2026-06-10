import os
from pathlib import Path

from dotenv import load_dotenv

from key_rotator import indexed_gemini_keys

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")


class Config:
    _raw = os.getenv("GEMINI_API_KEYS", "")
    GEMINI_API_KEYS = [k.strip() for k in _raw.split(",") if k.strip()]

    if not GEMINI_API_KEYS:
        GEMINI_API_KEYS = indexed_gemini_keys()

    ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
    ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
    ELEVENLABS_MODEL_ID = os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")

    DIRS = {
        "output": BASE_DIR / "output",
        "audio": BASE_DIR / "audio",
        "scenes": BASE_DIR / "scenes",
        "videos": BASE_DIR / "videos",
        "templates": BASE_DIR / "templates",
    }

    WIDTH = 1080
    HEIGHT = 1920
    FPS = 24

    @classmethod
    def ensure_dirs(cls):
        for d in cls.DIRS.values():
            d.mkdir(parents=True, exist_ok=True)
