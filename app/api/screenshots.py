import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app import settings

router = APIRouter()

_SAFE_FILENAME = re.compile(r"^[A-Za-z0-9_.\-]+\.png$")


@router.get("/api/screenshots/{run_id}/{filename}")
def get_screenshot(run_id: int, filename: str):
    if not _SAFE_FILENAME.match(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")

    path = Path(settings.DATA_DIR) / "screenshots" / str(run_id) / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Screenshot not found")

    return FileResponse(str(path), media_type="image/png")
