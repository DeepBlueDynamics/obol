import base64
import mimetypes
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status, Response
from fastapi.responses import StreamingResponse
import io
from typing import Optional
from pydantic import BaseModel
from ..storage import storage
from ..models import AttachmentMetadata
from ..auth import get_current_identity, AuthIdentity

router = APIRouter(prefix="/api/v1/attachments", tags=["attachments"])

class Base64AttachmentUpload(BaseModel):
    filename: str
    content_base64: str
    content_type: Optional[str] = None
    metadata: dict = {}

@router.post("", response_model=AttachmentMetadata)
async def upload_attachment_multipart(
    file: UploadFile = File(...),
    auth: AuthIdentity = Depends(get_current_identity)
):
    """Upload a multimodal attachment (PDF, image, audio, etc.) via multipart form."""
    content_bytes = await file.read()
    content_type = file.content_type
    if not content_type or content_type == "application/octet-stream":
        guessed, _ = mimetypes.guess_type(file.filename or "")
        content_type = guessed or "application/octet-stream"

    meta = storage.save_attachment(
        filename=file.filename or "attachment.bin",
        content_bytes=content_bytes,
        content_type=content_type,
        uploader_principal=auth.principal,
        metadata={"uploaded_by_user": auth.user_id}
    )
    return meta

@router.post("/base64", response_model=AttachmentMetadata)
async def upload_attachment_base64(
    payload: Base64AttachmentUpload,
    auth: AuthIdentity = Depends(get_current_identity)
):
    """Upload a multimodal attachment via base64 JSON payload (for MCP tools/agents)."""
    try:
        content_bytes = base64.b64decode(payload.content_base64)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid base64 payload: {str(e)}"
        )

    content_type = payload.content_type
    if not content_type:
        guessed, _ = mimetypes.guess_type(payload.filename)
        content_type = guessed or "application/octet-stream"

    meta = storage.save_attachment(
        filename=payload.filename,
        content_bytes=content_bytes,
        content_type=content_type,
        uploader_principal=auth.principal,
        metadata=payload.metadata
    )
    return meta

@router.get("/{id_or_hash}", response_model=AttachmentMetadata)
async def get_attachment_metadata(id_or_hash: str):
    """Retrieve metadata for an attachment by UUID or SHA-256 digest."""
    meta = storage.get_attachment_metadata(id_or_hash)
    if not meta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment not found"
        )
    return meta

@router.get("/{id_or_hash}/download")
async def download_attachment(id_or_hash: str):
    """Download the raw multimodal attachment bytes (PDF, image, audio)."""
    meta = storage.get_attachment_metadata(id_or_hash)
    content_bytes = storage.get_attachment_bytes(id_or_hash)
    if not content_bytes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment data not found"
        )

    content_type = meta.content_type if meta else "application/octet-stream"
    filename = meta.filename if meta else "download.bin"

    return StreamingResponse(
        io.BytesIO(content_bytes),
        media_type=content_type,
        headers={"Content-Disposition": f'inline; filename="{filename}"'}
    )
