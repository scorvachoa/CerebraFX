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
    # Voz "gancho": enérgica para la primera escena / hooks. Vacía = misma voz para todo.
    ELEVENLABS_HOOK_VOICE_ID = os.getenv("ELEVENLABS_HOOK_VOICE_ID", "")

    # Motor TTS: auto = ElevenLabs (si hay key) -> edge-tts -> gTTS.
    # Puede forzarse con: elevenlabs | edge | gtts
    TTS_ENGINE = os.getenv("TTS_ENGINE", "auto").strip().lower()
    TTS_WORKERS = int(os.getenv("TTS_WORKERS", "6"))
    # Voces de edge-tts (Microsoft neural, mucho más rápido que gTTS)
    EDGE_TTS_VOICE = os.getenv("EDGE_TTS_VOICE", "es-MX-DaliaNeural")
    EDGE_TTS_HOOK_VOICE = os.getenv("EDGE_TTS_HOOK_VOICE", "es-MX-JorgeNeural")

    DIRS = {
        "output": BASE_DIR / "output",
        "audio": BASE_DIR / "audio",
        "scenes": BASE_DIR / "scenes",
        "videos": BASE_DIR / "videos",
        "templates": BASE_DIR / "templates",
    }

    WIDTH = 1080
    HEIGHT = 1920
    FPS = int(os.getenv("FPS", "24"))

    # Escala de renderizado (1.0 = resolución completa). Bájala para previews rápidos.
    RENDER_SCALE = float(os.getenv("RENDER_SCALE", "1.0"))

    # Temporización por escena (segundos)
    SCENE_LEAD = float(os.getenv("SCENE_LEAD", "0.35"))    # pausa antes de la narración
    SCENE_TAIL = float(os.getenv("SCENE_TAIL", "0.45"))    # margen después de la narración
    MIN_SCENE = float(os.getenv("MIN_SCENE", "2.5"))       # duración mínima de escena

    # Pantalla de cierre
    END_SCREEN = float(os.getenv("END_SCREEN", "4.0"))     # duración de la pantalla final

    # Marca por defecto (sobreescribible por video desde el editor)
    BRAND_NAME = os.getenv("BRAND_NAME", "CerebraFX")
    BRAND_TAGLINE = os.getenv("BRAND_TAGLINE", "Matemáticas claras, cada día")
    BRAND_COLOR = os.getenv("BRAND_COLOR", "#6c63ff")
    BRAND_CHANNEL = os.getenv("BRAND_CHANNEL", "@CerebraFX")
    BRAND_SUBSCRIBE_TEXT = os.getenv("BRAND_SUBSCRIBE_TEXT", "Suscríbete")

    @classmethod
    def ensure_dirs(cls):
        for d in cls.DIRS.values():
            d.mkdir(parents=True, exist_ok=True)
