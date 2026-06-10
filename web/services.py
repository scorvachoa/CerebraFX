import asyncio
import json
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

_executor = ThreadPoolExecutor(max_workers=2)


def _generate_script_sync(topic: str) -> dict:
    from main import generate_script
    return generate_script(topic)


def _generate_audio_sync(text: str) -> Path:
    from main import generate_audio
    return generate_audio(text)


def _get_audio_duration_sync(path: Path) -> float:
    from main import get_audio_duration
    return get_audio_duration(path)


def _generate_html_sync(script: dict, duration: float) -> Path:
    from main import generate_html
    return generate_html(script, duration)


def _render_video_sync(html_path: Path, duration: float) -> Path:
    from main import render_video
    return render_video(html_path, duration)


def _create_final_video_sync(video_path: Path, audio_path: Path) -> Path:
    from main import create_final_video
    return create_final_video(video_path, audio_path)


async def generate_script(topic: str) -> dict:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _generate_script_sync, topic)


async def generate_full_video(topic: str, progress_callback=None) -> Path:
    loop = asyncio.get_event_loop()

    if progress_callback:
        await progress_callback("script", 0, "Generando guion con Gemini...")
    script = await loop.run_in_executor(_executor, _generate_script_sync, topic)

    full_text = ". ".join(s.get("narration") or s["text"] for s in script["scenes"])

    if progress_callback:
        await progress_callback("script", 100, "Guion listo")
        await progress_callback("audio", 0, f"Generando audio ({len(full_text)} caracteres)...")
    audio_path = await loop.run_in_executor(_executor, _generate_audio_sync, full_text)

    if progress_callback:
        await progress_callback("audio", 50, "Audio generado, obteniendo duración...")
    duration = await loop.run_in_executor(_executor, _get_audio_duration_sync, audio_path)

    if progress_callback:
        await progress_callback("audio", 100, f"Duración: {duration:.1f}s")
        await progress_callback("html", 0, "Generando HTML de escenas...")
    html_path = await loop.run_in_executor(_executor, _generate_html_sync, script, duration)

    if progress_callback:
        await progress_callback("html", 100, "HTML listo")
        await progress_callback("video", 0, "Renderizando video con Playwright...")
    t0 = time.time()
    video_path = await loop.run_in_executor(_executor, _render_video_sync, html_path, duration)

    if progress_callback:
        await progress_callback("video", 70, f"Video crudo listo ({time.time()-t0:.1f}s)")
        await progress_callback("final", 0, "Combinando video + audio + música...")
    final_path = await loop.run_in_executor(_executor, _create_final_video_sync, video_path, audio_path)

    if progress_callback:
        await progress_callback("final", 100, "Video final listo")

    return final_path
