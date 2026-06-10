import asyncio
import json
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

_executor = ThreadPoolExecutor(max_workers=2)


def _generate_script_sync(topic: str, category: str = "general") -> dict:
    from main import generate_script
    return generate_script(topic, category)


def _generate_audio_sync(text: str, suffix: str = "") -> Path:
    from main import generate_audio
    return generate_audio(text, suffix)


def _get_audio_duration_sync(path: Path) -> float:
    from main import get_audio_duration
    return get_audio_duration(path)


def _generate_html_sync(script: dict, duration: float, suffix: str = "") -> Path:
    from main import generate_html
    return generate_html(script, duration, suffix)


def _render_video_sync(html_path: Path, duration: float, suffix: str = "") -> Path:
    from main import render_video
    return render_video(html_path, duration, suffix)


def _create_final_video_sync(video_path: Path, audio_path: Path, suffix: str = "") -> Path:
    from main import create_final_video
    return create_final_video(video_path, audio_path, suffix)


async def generate_preview(scene: dict) -> str:
    template = (Path(__file__).parent.parent / "templates" / "preview.html").read_text(encoding="utf-8")
    scene_json = json.dumps(scene, ensure_ascii=False).replace("</", "<\\/")
    duration = 8.0
    html = template.replace("{{SCENE}}", scene_json).replace("{{DURATION}}", str(duration))
    return html


async def generate_script(topic: str, category: str = "general") -> dict:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _generate_script_sync, topic, category)


async def generate_full_video(topic: str, task_id: str = "", script: dict | None = None, category: str = "general", progress_callback=None) -> Path:
    loop = asyncio.get_event_loop()
    suffix = task_id[:8] if task_id else ""

    if script is None:
        if progress_callback:
            await progress_callback("script", 0, "Generando guion con Gemini...")
        script = await loop.run_in_executor(_executor, _generate_script_sync, topic, category)
    else:
        if progress_callback:
            await progress_callback("script", 0, "Usando guion existente...")

    full_text = ". ".join(s["narration"] if "narration" in s else s["text"] for s in script["scenes"])

    if progress_callback:
        await progress_callback("script", 100, "Guion listo")
        await progress_callback("audio", 0, f"Generando audio ({len(full_text)} caracteres)...")
    audio_path = await loop.run_in_executor(_executor, _generate_audio_sync, full_text, suffix)

    if progress_callback:
        await progress_callback("audio", 50, "Audio generado, obteniendo duración...")
    duration = await loop.run_in_executor(_executor, _get_audio_duration_sync, audio_path)

    if progress_callback:
        await progress_callback("audio", 100, f"Duración: {duration:.1f}s")
        await progress_callback("html", 0, "Generando HTML de escenas...")
    html_path = await loop.run_in_executor(_executor, _generate_html_sync, script, duration, suffix)

    if progress_callback:
        await progress_callback("html", 100, "HTML listo")
        await progress_callback("video", 0, "Renderizando video con Playwright...")
    t0 = time.time()
    video_path = await loop.run_in_executor(_executor, _render_video_sync, html_path, duration, suffix)

    if progress_callback:
        await progress_callback("video", 70, f"Video crudo listo ({time.time()-t0:.1f}s)")
        await progress_callback("final", 0, "Combinando video + audio + música...")
    final_path = await loop.run_in_executor(_executor, _create_final_video_sync, video_path, audio_path, suffix)

    if progress_callback:
        await progress_callback("final", 100, "Video final listo")

    return final_path
