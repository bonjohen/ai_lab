"""Chat API route — SSE streaming.

Design doc reference: §16 (submit chat, stream response).
"""

import json

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from app.models.chat import ChatRequest
from app.services.chat import ChatService

router = APIRouter(tags=["chat"])


@router.post("/chat")
async def chat(body: ChatRequest, request: Request):
    service = ChatService(request.app.state.config, request.app.state.db)

    async def event_generator():
        async for event in service.handle_chat(body):
            yield {"event": event.type.value, "data": json.dumps(event.model_dump(exclude_none=True))}

    return EventSourceResponse(event_generator())
