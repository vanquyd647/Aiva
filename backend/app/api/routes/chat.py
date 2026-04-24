"""Chat streaming routes."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.db.session import get_db
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.schemas.chat import ChatStreamRequest
from app.services.chat_stream import stream_chat_text
from app.services.governance import (
    estimate_tokens,
    record_usage_event,
    user_usage_summary,
    will_exceed_quota,
)
from app.services.web_search import search_web

router = APIRouter(prefix="/chat", tags=["chat"])


def _sse_event(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _build_citation_context(citations: list[dict]) -> str:
    lines = [
        "Web references below are supplementary context.",
        "If used, cite with [1], [2], ... and avoid fabricating unsupported claims.",
    ]
    for index, item in enumerate(citations, start=1):
        title = str(item.get("title", "")).strip() or "Untitled"
        url = str(item.get("url", "")).strip()
        snippet = str(item.get("snippet", "")).strip()
        lines.append(f"[{index}] {title} - {url}")
        if snippet:
            lines.append(f"Snippet: {snippet}")
    return "\n".join(lines)


def _apply_thinking_prompt(system_prompt: str, enable_thinking: bool) -> str:
    if not enable_thinking:
        return system_prompt
    if "<|think|>" in system_prompt:
        return system_prompt
    if not system_prompt.strip():
        return "<|think|>"
    return f"<|think|>\n{system_prompt}"


@router.post("/stream")
def chat_stream(
    payload: ChatStreamRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    system_prompt = _apply_thinking_prompt(payload.system_prompt, payload.enable_thinking)

    cfg = {
        "model": payload.model,
        "temperature": payload.temperature,
        "top_p": payload.top_p,
        "top_k": payload.top_k,
        "max_output_tokens": payload.max_output_tokens,
        "candidate_count": payload.candidate_count,
        "stop_sequences": payload.stop_sequences,
        "seed": payload.seed,
        "presence_penalty": payload.presence_penalty,
        "frequency_penalty": payload.frequency_penalty,
        "system_prompt": system_prompt,
        "response_mime_type": payload.response_mime_type,
        "response_schema": payload.response_schema,
        "response_json_schema": payload.response_json_schema,
        "tools": [item.model_dump() for item in payload.tools],
        "function_calling_mode": payload.function_calling_mode,
        "allowed_function_names": payload.allowed_function_names,
        "stream_function_call_arguments": payload.stream_function_call_arguments,
        "include_server_side_tool_invocations": payload.include_server_side_tool_invocations,
        "include_thoughts": payload.include_thoughts,
        "thinking_budget_tokens": payload.thinking_budget_tokens,
        "thinking_level": payload.thinking_level,
        "media_resolution": payload.media_resolution,
        "safety_settings": [item.model_dump() for item in payload.safety_settings],
    }
    messages = [item.model_dump() for item in payload.messages]

    last_user_message: dict | None = None
    for msg in reversed(messages):
        if msg.get("role") == "user":
            last_user_message = msg
            break

    if last_user_message is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one user message is required",
        )

    last_user_text = str(last_user_message.get("text", "")).strip()
    last_user_attachments = last_user_message.get("attachments") or []
    if not last_user_text and not last_user_attachments:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The latest user message must include text or attachments",
        )

    persisted_user_content = last_user_text
    if not persisted_user_content and last_user_attachments:
        persisted_user_content = f"[Attachment-only input: {len(last_user_attachments)} item(s)]"

    usage_snapshot = user_usage_summary(db, user_id=current_user.id, role=current_user.role)
    if will_exceed_quota(usage_snapshot):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Usage quota exceeded for current window",
        )

    citations: list[dict] = []
    if payload.enable_web_search:
        citations = search_web(query=last_user_text, limit=payload.web_search_max_results)
        record_usage_event(
            db,
            user_id=current_user.id,
            metric="web_search_queries",
            quantity=1,
            source="chat",
            metadata={
                "query": last_user_text[:160],
                "results": len(citations),
            },
        )
        if citations:
            messages.append(
                {
                    "role": "system",
                    "text": _build_citation_context(citations),
                }
            )

    if payload.conversation_id is not None:
        conversation = (
            db.query(Conversation)
            .filter(
                Conversation.id == payload.conversation_id,
                Conversation.user_id == current_user.id,
            )
            .first()
        )
        if conversation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )
    else:
        title_source = (payload.conversation_title or last_user_text).strip()
        conversation = Conversation(
            user_id=current_user.id,
            title=title_source[:255] or "New conversation",
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    user_message = Message(
        conversation_id=conversation.id,
        role="user",
        content=persisted_user_content,
        status="final",
    )
    db.add(user_message)
    db.commit()
    db.refresh(user_message)

    def event_stream():
        full_text = ""
        tool_calls: list[dict] = []
        prompt_token_estimate = sum(
            estimate_tokens(str(item.get("text", "")))
            for item in messages
            if item.get("role") == "user"
        )
        yield _sse_event(
            "meta",
            {
                "model": payload.model,
                "conversation_id": conversation.id,
                "user_message_id": user_message.id,
            },
        )
        try:
            for stream_item in stream_chat_text(messages=messages, cfg=cfg):
                if isinstance(stream_item, str):
                    full_text += stream_item
                    yield _sse_event("chunk", {"text": stream_item})
                    continue

                if isinstance(stream_item, dict) and stream_item.get("type") == "tool_call":
                    tool_calls.append(stream_item)
                    yield _sse_event("tool_call", stream_item)

            assistant_content = full_text
            if not assistant_content and tool_calls:
                assistant_content = json.dumps({"tool_calls": tool_calls}, ensure_ascii=False)

            assistant_message = Message(
                conversation_id=conversation.id,
                role="assistant",
                content=assistant_content,
                status="final",
            )
            db.add(assistant_message)
            db.commit()
            db.refresh(assistant_message)

            completion_token_estimate = estimate_tokens(full_text)
            record_usage_event(
                db,
                user_id=current_user.id,
                metric="chat_messages",
                quantity=1,
                source="chat",
                metadata={
                    "conversation_id": conversation.id,
                    "assistant_message_id": assistant_message.id,
                },
            )
            record_usage_event(
                db,
                user_id=current_user.id,
                metric="chat_tokens",
                quantity=prompt_token_estimate + completion_token_estimate,
                source="chat",
                metadata={"conversation_id": conversation.id, "model": payload.model},
            )

            yield _sse_event(
                "done",
                {
                    "text": full_text,
                    "conversation_id": conversation.id,
                    "assistant_message_id": assistant_message.id,
                    "citations": citations,
                    "tool_calls": tool_calls,
                },
            )
        except Exception as exc:
            yield _sse_event(
                "error",
                {
                    "message": str(exc),
                    "conversation_id": conversation.id,
                },
            )

    headers = {
        "Cache-Control": "no-store",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    }
    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=headers)
