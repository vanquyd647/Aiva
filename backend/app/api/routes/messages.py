"""Message routes for authenticated users."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.db.session import get_db
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.schemas.message import MessageCreate, MessageListOut, MessageOut, MessageUpdate

router = APIRouter(prefix="/messages", tags=["messages"])


def _get_conversation_or_404(db: Session, conversation_id: int, user_id: int) -> Conversation:
    conversation = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id, Conversation.user_id == user_id)
        .first()
    )
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conversation


def _get_message_or_404(db: Session, message_id: int, user_id: int) -> Message:
    message = (
        db.query(Message)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .filter(Message.id == message_id, Conversation.user_id == user_id)
        .first()
    )
    if not message:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    return message


@router.get("", response_model=MessageListOut)
def list_messages(
    conversation_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _get_conversation_or_404(db, conversation_id, current_user.id)

    query = db.query(Message).filter(Message.conversation_id == conversation_id)
    total = query.count()
    items = (
        query.order_by(Message.created_at.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return MessageListOut(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=MessageOut, status_code=status.HTTP_201_CREATED)
def create_message(
    payload: MessageCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _get_conversation_or_404(db, payload.conversation_id, current_user.id)

    message = Message(
        conversation_id=payload.conversation_id,
        role=payload.role,
        content=payload.content,
        status=payload.status,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


@router.patch("/{message_id}", response_model=MessageOut)
def update_message(
    message_id: int,
    payload: MessageUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    message = _get_message_or_404(db, message_id, current_user.id)
    update_data = payload.model_dump(exclude_unset=True, exclude_none=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one field is required",
        )

    if "content" in update_data:
        message.content = update_data["content"]
    if "status" in update_data:
        message.status = update_data["status"]

    db.commit()
    db.refresh(message)
    return message


@router.delete("/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_message(
    message_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    message = _get_message_or_404(db, message_id, current_user.id)
    db.delete(message)
    db.commit()
    return None
