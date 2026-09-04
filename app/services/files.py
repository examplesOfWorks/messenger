import aiofiles
from fastapi import HTTPException, UploadFile
from pathlib import Path
from uuid import uuid4

PATH_TO_IMAGES = Path("media/users")
PATH_TO_IMAGES.mkdir(exist_ok=True)

async def upload_image(file: UploadFile, user_id: int):
    if file.content_type not in {
        "image/jpeg",
        "image/png"
    }:
        raise HTTPException(
            status_code=400,
            detail="Файл должен быть JPEG или PNG"
        )
    
    extention = "jpg" if file.content_type == "image/jpeg" else "png"
    filename = f"{uuid4()}.{extention}"

    user_path = PATH_TO_IMAGES / str(user_id)
    user_path.mkdir(parents=True, exist_ok=True)

    path = user_path / filename

    contents = await file.read()

    async with aiofiles.open(path, "wb") as buffer:
        await buffer.write(contents)

    return filename


def delete_image(filename: str, user_id: int):
    path = PATH_TO_IMAGES / str(user_id) / filename
    
    if path.exists():
        path.unlink()