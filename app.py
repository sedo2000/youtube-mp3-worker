import os
import re
import secrets
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, HttpUrl
from starlette.background import BackgroundTask

app = FastAPI(title="YouTube MP3 Worker", version="1.0.0")
API_TOKEN = os.environ.get("API_TOKEN", "")
MAX_DURATION_SECONDS = int(os.environ.get("MAX_DURATION_SECONDS", "900"))
MAX_FILE_SIZE_BYTES = int(os.environ.get("MAX_FILE_SIZE_BYTES", str(50 * 1024 * 1024)))


class ConvertRequest(BaseModel):
    url: HttpUrl


def allowed_youtube_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower().rstrip(".")
    return host in {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be", "www.youtu.be"}


def cleanup(path: str) -> None:
    try:
        Path(path).unlink(missing_ok=True)
        Path(path).parent.rmdir()
    except OSError:
        pass


@app.get("/health")
def health():
    return {"ok": True, "service": "youtube-mp3-worker"}


@app.post("/convert")
def convert(payload: ConvertRequest, authorization: str | None = Header(default=None)):
    if not API_TOKEN:
        raise HTTPException(status_code=503, detail="Service is not configured")
    supplied = authorization.removeprefix("Bearer ").strip() if authorization else ""
    if not secrets.compare_digest(supplied, API_TOKEN):
        raise HTTPException(status_code=401, detail="Unauthorized")

    url = str(payload.url)
    if not allowed_youtube_url(url):
        raise HTTPException(status_code=400, detail="Only YouTube URLs are supported")

    workdir = tempfile.mkdtemp(prefix="ytmp3-")
    output_template = str(Path(workdir) / "audio.%(ext)s")
    command = [
        "yt-dlp",
        "--no-playlist",
        "--no-warnings",
        "--restrict-filenames",
        "--max-filesize", str(MAX_FILE_SIZE_BYTES),
        "--match-filter", f"duration <= {MAX_DURATION_SECONDS}",
        "-f", "bestaudio/best",
        "-x",
        "--audio-format", "mp3",
        "--audio-quality", "5",
        "-o", output_template,
        "--",
        url,
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=240, check=False)
        if result.returncode != 0:
            try:
                Path(workdir).rmdir()
            except OSError:
                pass
            detail = (result.stderr or result.stdout or "Unable to convert this video")[-1200:]
            raise HTTPException(status_code=422, detail=detail)
        files = list(Path(workdir).glob("*.mp3"))
        if not files:
            raise HTTPException(status_code=422, detail="Conversion did not produce an MP3 file")
        mp3 = files[0]
        if mp3.stat().st_size > MAX_FILE_SIZE_BYTES:
            raise HTTPException(status_code=413, detail="The resulting MP3 is too large")
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", mp3.stem).strip("._-") or "audio"
        return FileResponse(
            path=str(mp3),
            media_type="audio/mpeg",
            filename=f"{safe_name}.mp3",
            background=BackgroundTask(cleanup, str(mp3)),
        )
    except subprocess.TimeoutExpired:
        try:
            for item in Path(workdir).iterdir():
                item.unlink(missing_ok=True)
            Path(workdir).rmdir()
        except OSError:
            pass
        raise HTTPException(status_code=504, detail="Conversion timed out")
    except HTTPException:
        raise
    except Exception:
        try:
            for item in Path(workdir).iterdir():
                item.unlink(missing_ok=True)
            Path(workdir).rmdir()
        except OSError:
            pass
        raise HTTPException(status_code=500, detail="Conversion failed")
