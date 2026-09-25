import os
import uuid
import asyncio
from pathlib import Path

import yt_dlp
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from pydantic import BaseModel

app = FastAPI()

DOWNLOAD_DIR = Path("/tmp/mediasave")
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)


class DownloadRequest(BaseModel):
    url: str
    quality: str = "480"


@app.get("/")
async def home():
    return {
        "status": "MediaSave downloader is running"
    }


@app.post("/download")
async def download_video(data: DownloadRequest):
    url = data.url.strip()

    if "instagram.com" not in url:
        raise HTTPException(
            status_code=400,
            detail="Instagram URL required"
        )

    file_id = uuid.uuid4().hex

    output = (
        DOWNLOAD_DIR /
        f"{file_id}.%(ext)s"
    )

    quality = data.quality

    height = {
        "360": 360,
        "480": 480,
        "720": 720
    }.get(quality, 480)

    options = {
        "outtmpl": str(output),
        "format": (
            f"best[height<={height}][ext=mp4]/"
            f"best[height<={height}]/best"
        ),
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }

    try:
        loop = asyncio.get_running_loop()

        def run():
            with yt_dlp.YoutubeDL(options) as ydl:
                ydl.download([url])

        await loop.run_in_executor(
            None,
            run
        )

        files = list(
            DOWNLOAD_DIR.glob(
                f"{file_id}.*"
            )
        )

        if not files:
            raise Exception(
                "Video file was not created"
            )

        file_path = files[0]

        return {
            "ok": True,
            "file": f"/file/{file_id}",
            "filename": file_path.name
        }

    except Exception as e:

        # Қате кезінде осы видеоға тиесілі
        # уақытша файлдарды өшіру
        for file in DOWNLOAD_DIR.glob(
            f"{file_id}.*"
        ):
            try:
                file.unlink()
            except Exception:
                pass

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@app.get("/file/{file_id}")
async def get_file(file_id: str):

    files = list(
        DOWNLOAD_DIR.glob(
            f"{file_id}.*"
        )
    )

    if not files:
        raise HTTPException(
            status_code=404,
            detail="File not found"
        )

    file_path = files[0]

    # Telegram файлды толық алып болғаннан кейін
    # Render серверіндегі файл автоматты өшеді
    cleanup = BackgroundTask(
        delete_file,
        file_path
    )

    return FileResponse(
        file_path,
        media_type="video/mp4",
        filename=file_path.name,
        background=cleanup
    )


def delete_file(file_path: Path):
    try:
        if file_path.exists():
            file_path.unlink()
            print(
                f"Deleted temporary file: {file_path.name}"
            )
    except Exception as e:
        print(
            f"Failed to delete file: {e}"
        )


if __name__ == "__main__":
    import uvicorn

    port = int(
        os.environ.get(
            "PORT",
            "10000"
        )
    )

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port
)
