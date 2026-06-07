"""
Server-Sent Events (SSE) utilities for real-time agent step streaming.

Provides pub-sub mechanism for streaming agent execution events to frontend
clients. Each session gets an in-memory queue for event buffering. Events are
published by agent nodes and consumed by SSE endpoint generators.

Key functions:
- get_queue: Get or create event queue for a session
- publish_event: Publish event to session's queue (producer side)
- event_stream: Async generator yielding SSE-formatted events (consumer side)

Lifecycle: Queue created on first event, auto-cleaned after stream completes.
Keep-alive pings every 30s prevent connection timeout during long operations.
"""

import asyncio
import json
import logging
from collections.abc import AsyncGenerator

logger = logging.getLogger(__name__)

# In-memory event queues keyed by session_id (max 100 events per queue)
_session_queues: dict[str, asyncio.Queue] = {}


def get_queue(session_id: str) -> asyncio.Queue:
    """
    Get or create event queue for a session.

    Lazy initialization: creates queue on first access with max size of 100
    events. Used by both publishers (agent nodes) and consumers (SSE endpoint).

    Args:
        session_id: Unique session identifier (typically use_case_id or run_id)

    Returns:
        Async queue for buffering events
    """
    if session_id not in _session_queues:
        _session_queues[session_id] = asyncio.Queue(maxsize=100)
    return _session_queues[session_id]


async def publish_event(session_id: str, event_type: str, content: str) -> None:
    """
    Publish event to session's SSE queue (producer side).

    Called by agent nodes to broadcast execution progress. If queue is full,
    drops event with warning (prevents memory buildup from slow consumers).

    Args:
        session_id: Session identifier
        event_type: Event type string (e.g., "node_start", "node_complete", "complete")
        content: Event content/message
    """
    queue = get_queue(session_id)
    try:
        await queue.put({"type": event_type, "content": content})
    except asyncio.QueueFull:
        logger.warning(f"[sse] Queue full for session {session_id}, dropping event")


async def event_stream(session_id: str) -> AsyncGenerator[str, None]:
    """
    Async generator yielding SSE-formatted event strings (consumer side).

    Streams events from session queue to client. Implements keep-alive pings
    every 30s to prevent connection timeout during long-running operations.
    Automatically cleans up queue when stream completes or client disconnects.

    Args:
        session_id: Session identifier to stream events for

    Yields:
        SSE-formatted strings: "data: {json}\n\n"

    Flow:
    1. Wait up to 30s for next event
    2. If event received: yield it (break on "complete" type)
    3. If timeout: yield keep-alive ping to maintain connection
    4. On completion/error: cleanup queue from memory
    """
    queue = get_queue(session_id)
    try:
        while True:
            try:
                # Wait for next event with 30s timeout
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
                # Yield event in SSE format
                yield f"data: {json.dumps(event)}\n\n"
                # Break stream on completion event
                if event.get("type") == "complete":
                    break
            except TimeoutError:
                # Send keep-alive ping to prevent connection timeout
                yield 'data: {"type": "ping"}\n\n'
    finally:
        # Cleanup: remove queue from memory when stream ends
        _session_queues.pop(session_id, None)
