"""Server-Sent Events utilities for agent step streaming."""
import asyncio
import json
import logging
from collections.abc import AsyncGenerator

logger = logging.getLogger(__name__)

# In-memory event queues keyed by session_id
_session_queues: dict[str, asyncio.Queue] = {}


def get_queue(session_id: str) -> asyncio.Queue:
    """Get or create an event queue for a session."""
    if session_id not in _session_queues:
        _session_queues[session_id] = asyncio.Queue(maxsize=100)
    return _session_queues[session_id]


async def publish_event(session_id: str, event_type: str, content: str) -> None:
    """Publish an event to a session's SSE queue."""
    queue = get_queue(session_id)
    try:
        await queue.put({"type": event_type, "content": content})
    except asyncio.QueueFull:
        logger.warning(f"[sse] Queue full for session {session_id}, dropping event")


async def event_stream(session_id: str) -> AsyncGenerator[str, None]:
    """Async generator that yields SSE-formatted strings from the session queue."""
    queue = get_queue(session_id)
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
                if event.get("type") == "complete":
                    yield f"data: {json.dumps(event)}\n\n"
                    break
                yield f"data: {json.dumps(event)}\n\n"
            except asyncio.TimeoutError:
                yield 'data: {"type": "ping"}\n\n'  # keep-alive
    finally:
        _session_queues.pop(session_id, None)
