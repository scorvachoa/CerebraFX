import os
import uuid
import json
import asyncio
from pathlib import Path
from enum import Enum
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import BASE_DIR, Config
from web.services import generate_script, generate_full_video


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    Config.ensure_dirs()
    yield


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


class GenerateRequest(BaseModel):
    topic: str


@app.post("/api/generate-script")
async def api_generate_script(req: ScriptRequest):
    try:
        script = await generate_script(req.topic)
        return {"title": script["title"], "scenes": script["scenes"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/generate-video")
async def api_generate_video(req: GenerateRequest):
    task_id = str(uuid.uuid4())
    tasks[task_id] = {
        "status": TaskStatus.PENDING,
        "progress": 0,
        "message": "Iniciando...",
        "result": None,
        "topic": req.topic,
    }

    asyncio.create_task(_run_video_pipeline(task_id, req.topic))

    return {"task_id": task_id}


async def _run_video_pipeline(task_id: str, topic: str):
    async def progress(step: str, pct: int, msg: str):
        tasks[task_id].update({
            "status": step,
            "progress": pct,
            "message": msg,
        })

    try:
        tasks[task_id]["status"] = TaskStatus.SCRIPT
        final_path = await generate_full_video(topic, progress_callback=progress)

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
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("web.server:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    start()
