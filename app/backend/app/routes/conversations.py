"""Conversation API routes.

Design doc reference: §16 — conversation CRUD and fork.
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.persistence.repositories import ConversationRepository, MessageRepository

router = APIRouter(tags=["conversations"])


class CreateConversationRequest(BaseModel):
    source_id: str
    title: str | None = None


class ForkConversationRequest(BaseModel):
    new_source_id: str


@router.post("/conversations")
async def create_conversation(body: CreateConversationRequest, request: Request):
    repo = ConversationRepository(request.app.state.db)
    # Validate source exists
    config = request.app.state.config
    if body.source_id not in config.sources:
        raise HTTPException(status_code=400, detail=f"Source '{body.source_id}' not found")
    return await repo.create(source_id=body.source_id, title=body.title)


@router.get("/conversations")
async def list_conversations(request: Request):
    repo = ConversationRepository(request.app.state.db)
    return await repo.list_all()


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, request: Request):
    repo = ConversationRepository(request.app.state.db)
    conv = await repo.get_with_messages(conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@router.post("/conversations/{conversation_id}/fork")
async def fork_conversation(
    conversation_id: str, body: ForkConversationRequest, request: Request
):
    config = request.app.state.config
    if body.new_source_id not in config.sources:
        raise HTTPException(status_code=400, detail=f"Source '{body.new_source_id}' not found")

    repo = ConversationRepository(request.app.state.db)
    forked = await repo.fork(conversation_id, body.new_source_id)
    if forked is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return forked
