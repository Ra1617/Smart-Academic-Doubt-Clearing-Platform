"""
Supabase Storage service for image uploads.
Uses the supabase-py client with service role key.
"""
import uuid
from typing import Optional
from supabase import create_client, Client
from fastapi import UploadFile, HTTPException

from app.core.config import settings


def get_supabase() -> Client:
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)


async def upload_image(file: UploadFile, folder: str = "doubts") -> dict:
    """Upload image to Supabase Storage and return path + public URL."""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files are allowed")

    max_size = 5 * 1024 * 1024  # 5MB
    content = await file.read()
    if len(content) > max_size:
        raise HTTPException(status_code=400, detail="Image size must be under 5MB")

    ext = file.filename.split(".")[-1] if file.filename else "jpg"
    storage_path = f"{folder}/{uuid.uuid4()}.{ext}"

    sb = get_supabase()
    try:
        sb.storage.from_(settings.SUPABASE_STORAGE_BUCKET).upload(
            path=storage_path,
            file=content,
            file_options={"content-type": file.content_type},
        )
        public_url = sb.storage.from_(settings.SUPABASE_STORAGE_BUCKET).get_public_url(storage_path)
        return {
            "storage_path": storage_path,
            "public_url": public_url,
            "file_name": file.filename,
            "file_size": len(content),
            "mime_type": file.content_type,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


def delete_image(storage_path: str):
    """Delete an image from Supabase Storage."""
    try:
        sb = get_supabase()
        sb.storage.from_(settings.SUPABASE_STORAGE_BUCKET).remove([storage_path])
    except Exception as e:
        print(f"[Storage] Delete error: {e}")
