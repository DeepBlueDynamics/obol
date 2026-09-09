from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from ..models import MessageCreate, MessageRecord, AttachmentMetadata
from ..storage import storage
from ..auth import get_current_identity, AuthIdentity

router = APIRouter(prefix="/api/v1/messages", tags=["messages"])

@router.post("", response_model=MessageRecord)
async def send_message(
    payload: MessageCreate,
    auth: AuthIdentity = Depends(get_current_identity)
):
    """Send an inter-agent message with text and optional multimodal attachments."""
    # Resolve attachment metadata for all referenced IDs
    resolved_attachments: List[AttachmentMetadata] = []
    for att_id in payload.attachment_ids:
        meta = storage.get_attachment_metadata(att_id)
        if meta:
            resolved_attachments.append(meta)

    message = MessageRecord(
        sender_principal=auth.principal,
        recipient=payload.recipient,
        channel=payload.channel or "general",
        subject=payload.subject,
        content=payload.content,
        attachments=resolved_attachments,
        reply_to_id=payload.reply_to_id,
        metadata=payload.metadata
    )

    saved = storage.save_message(message)
    return saved

@router.get("", response_model=List[MessageRecord])
async def list_messages(
    recipient: Optional[str] = Query(None, description="Filter by recipient principal or 'broadcast'"),
    channel: Optional[str] = Query(None, description="Filter by channel name"),
    sender: Optional[str] = Query(None, description="Filter by sender principal"),
    limit: int = Query(50, ge=1, le=200),
    auth: AuthIdentity = Depends(get_current_identity)
):
    """Retrieve messages for the requesting agent or channel."""
    target_recipient = recipient
    # If no recipient specified, default to messages for the current principal or broadcast
    if not target_recipient and not channel:
        target_recipient = auth.principal

    return storage.list_messages(
        recipient=target_recipient,
        channel=channel,
        sender=sender,
        limit=limit
    )

@router.get("/{message_id}", response_model=MessageRecord)
async def get_message(message_id: str):
    """Get message details by ID."""
    all_msgs = storage.list_messages(limit=1000)
    for m in all_msgs:
        if m.id == message_id:
            return m
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Message not found"
    )
