"""Conversation routes for authenticated users."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.db.session import get_db
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.schemas.conversation import (
    ConversationCreate,
    ConversationListOut,
    ConversationOut,
    ConversationUpdate,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


def _get_conversation_or_404(db: Session, conversation_id: int, user_id: int) -> Conversation:
    conversation = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id, Conversation.user_id == user_id)
        .first()
    )
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conversation


@router.get("", response_model=ConversationListOut)
def list_conversations(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None, min_length=1, max_length=255),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    query = db.query(Conversation).filter(Conversation.user_id == current_user.id)

    normalized_search = (search or "").strip()
    if normalized_search:
        query = query.filter(Conversation.title.ilike(f"%{normalized_search}%"))

    total = query.count()
    items = (
        query.order_by(Conversation.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return ConversationListOut(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
def create_conversation(
    payload: ConversationCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    title = payload.title.strip() or "New conversation"
    conversation = Conversation(user_id=current_user.id, title=title)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


@router.get("/{conversation_id}", response_model=ConversationOut)
def get_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return _get_conversation_or_404(db, conversation_id, current_user.id)


@router.patch("/{conversation_id}", response_model=ConversationOut)
def update_conversation(
    conversation_id: int,
    payload: ConversationUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    conversation = _get_conversation_or_404(db, conversation_id, current_user.id)
    conversation.title = payload.title.strip()
    db.commit()
    db.refresh(conversation)
    return conversation


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    conversation = _get_conversation_or_404(db, conversation_id, current_user.id)
    db.delete(conversation)
    db.commit()
    return None


@router.post(
    "/{conversation_id}/branch", response_model=ConversationOut, status_code=status.HTTP_201_CREATED
)
def branch_conversation(
    conversation_id: int,
    from_message_id: int | None = Query(default=None, ge=1),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    source = _get_conversation_or_404(db, conversation_id, current_user.id)
    source_messages = (
        db.query(Message)
        .filter(Message.conversation_id == source.id)
        .order_by(Message.created_at.asc(), Message.id.asc())
        .all()
    )

    if not source_messages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot branch an empty conversation",
        )

    if from_message_id is not None:
        cutoff_index = next(
            (index for index, item in enumerate(source_messages) if item.id == from_message_id),
            None,
        )
        if cutoff_index is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message not found in source conversation",
            )
        source_messages = source_messages[: cutoff_index + 1]

    branch_title = f"{source.title} (branch)"[:255]
    branch = Conversation(user_id=current_user.id, title=branch_title)
    db.add(branch)
    db.commit()
    db.refresh(branch)

    clones = [
        Message(
            conversation_id=branch.id,
            role=item.role,
            content=item.content,
            status=item.status,
        )
        for item in source_messages
    ]
    db.add_all(clones)
    db.commit()
    db.refresh(branch)
    return branch
