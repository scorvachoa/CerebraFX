import os
import uuid
import json
import asyncio
import time
from pathlib import Path
from enum import Enum
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import BASE_DIR, Config
from web.services import generate_script, generate_full_video, generate_preview


class TaskStatus(str, Enum):
    PENDING = "pending"
    SCRIPT = "script"
    AUDIO = "audio"
    HTML = "html"
    VIDEO = "video"
    FINAL = "final"
    COMPLETED = "completed"
    FAILED = "failed"


tasks: dict[str, dict] = {}
batches: dict[str, dict] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    Config.ensure_dirs()
    loop = asyncio.get_running_loop()
    loop.set_exception_handler(_silence_reset)
    yield


def _silence_reset(loop, context):
    exc = context.get("exception")
    if isinstance(exc, ConnectionResetError):
        return
    loop.default_exception_handler(context)

app = FastAPI(
    title="CerebraFX Studio",
    description="Generador de videos educativos de matemáticas",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ScriptRequest(BaseModel):
    topic: str
    category: str = "general"


class GenerateRequest(BaseModel):
    topic: str
    category: str = "general"
    script: dict | None = None
    brand: dict | None = None


@app.post("/api/generate-script")
async def api_generate_script(req: ScriptRequest):
    try:
        script = await generate_script(req.topic, req.category)
        return {"title": script["title"], "scenes": script["scenes"], "category": req.category}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class PreviewRequest(BaseModel):
    scene: dict
    brand: dict | None = None


class BatchRequest(BaseModel):
    topics: list[str]


@app.post("/api/preview-scene")
async def api_preview_scene(req: PreviewRequest):
    try:
        html = await generate_preview(req.scene, req.brand)
        return HTMLResponse(content=html)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/generate-batch")
async def api_generate_batch(req: BatchRequest):
    batch_id = str(uuid.uuid4())[:8]
    topics = [t.strip() for t in req.topics if t.strip()]
    if not topics:
        raise HTTPException(status_code=400, detail="Lista de temas vacía")

    _cleanup_old_tasks()

    task_infos = []
    for topic in topics:
        task_id = str(uuid.uuid4())
        tasks[task_id] = {
            "status": TaskStatus.PENDING,
            "progress": 0,
            "message": "En cola...",
            "result": None,
            "topic": topic,
            "created_at": time.time(),
        }
        task_infos.append({"topic": topic, "task_id": task_id})

    batches[batch_id] = {
        "tasks": task_infos,
        "status": "running",
        "created_at": time.time(),
    }

    asyncio.create_task(_run_batch_pipeline(batch_id, topics, task_infos))

    return {"batch_id": batch_id, "tasks": task_infos}


@app.get("/api/batch-status/{batch_id}")
async def api_batch_status(batch_id: str):
    batch = batches.get(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    task_statuses = []
    for t in batch["tasks"]:
        task = tasks.get(t["task_id"], {})
        task_statuses.append({
            "topic": t["topic"],
            "task_id": t["task_id"],
            "status": task.get("status", "unknown"),
            "progress": task.get("progress", 0),
            "message": task.get("message", ""),
            "result": task.get("result"),
        })

    all_done = all(s["status"] in ("completed", "failed") for s in task_statuses)

    return {
        "batch_id": batch_id,
        "status": "completed" if all_done else "running",
        "total": len(task_statuses),
        "completed": sum(1 for s in task_statuses if s["status"] == "completed"),
        "failed": sum(1 for s in task_statuses if s["status"] == "failed"),
        "tasks": task_statuses,
    }


@app.post("/api/generate-video")
async def api_generate_video(req: GenerateRequest):
    task_id = str(uuid.uuid4())

    _cleanup_old_tasks()

    tasks[task_id] = {
        "status": TaskStatus.PENDING,
        "progress": 0,
        "message": "Iniciando...",
        "result": None,
        "topic": req.topic,
        "created_at": time.time(),
    }

    asyncio.create_task(_run_video_pipeline(task_id, req.topic, req.script, req.category, req.brand))

    return {"task_id": task_id}


def _cleanup_old_tasks(max_age: float = 3600):
    now = time.time()
    expired = [
        tid for tid, t in list(tasks.items())
        if t.get("status") in (TaskStatus.COMPLETED, TaskStatus.FAILED)
        and now - t.get("created_at", 0) > max_age
    ]
    for tid in expired:
        del tasks[tid]


async def _run_batch_pipeline(batch_id: str, topics: list[str], task_infos: list[dict]):
    for i, (topic, info) in enumerate(zip(topics, task_infos)):
        await _run_video_pipeline(info["task_id"], topic)
    batches[batch_id]["status"] = "completed"


async def _run_video_pipeline(task_id: str, topic: str, script: dict | None = None, category: str = "general", brand: dict | None = None):
    async def progress(step: str, pct: int, msg: str):
        tasks[task_id].update({
            "status": step,
            "progress": pct,
            "message": msg,
        })

    try:
        tasks[task_id]["status"] = TaskStatus.SCRIPT
        final_path = await generate_full_video(topic, task_id=task_id, script=script, category=category, brand=brand, progress_callback=progress)

        tasks[task_id].update({
            "status": TaskStatus.COMPLETED,
            "progress": 100,
            "message": "Video listo",
            "result": str(final_path),
        })
    except Exception as e:
        tasks[task_id].update({
            "status": TaskStatus.FAILED,
            "message": str(e),
        })


@app.get("/api/status/{task_id}")
async def api_get_status(task_id: str):
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.get("/api/download/{task_id}")
async def api_download(task_id: str):
    task = tasks.get(task_id)
    if not task or task["status"] != TaskStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Video not ready")
    path = Path(task["result"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        path,
        media_type="video/mp4",
        filename=f"CerebraFX_{task_id[:8]}.mp4",
    )


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def root():
    index = Path(__file__).parent / "templates" / "index.html"
    return index.read_text(encoding="utf-8")


def start():
    from config import Config
    Config.ensure_dirs()
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run("web.server:app", host="127.0.0.1", port=port, reload=False)


if __name__ == "__main__":
    start()
