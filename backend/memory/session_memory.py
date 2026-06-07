"""
LangGraph checkpointer for agent state persistence and resumption.

Provides singleton checkpointer instance for LangGraph StateGraph agents to persist
state across interruptions and server restarts. Supports both AsyncSqliteSaver
(preferred for production) and MemorySaver (fallback for development).

Key features:
- Singleton pattern: get_checkpointer() returns same instance across calls
- AsyncSqliteSaver: Persists checkpoints to checkpoints.db SQLite file
- MemorySaver fallback: In-memory persistence when SQLite unavailable
- Graceful degradation: Logs warnings when falling back to in-memory mode

Usage:
    from memory.session_memory import get_checkpointer
    checkpointer = await get_checkpointer()
    graph = StateGraph(...).compile(checkpointer=checkpointer)

Checkpoint lifecycle:
1. Agent nodes save state after each step via checkpointer.aput()
2. If agent interrupted (server restart, error), state persists in checkpoints.db
3. Next run can resume from last checkpoint via thread_id lookup
"""

import logging

logger = logging.getLogger(__name__)

_checkpointer = None


async def get_checkpointer():
    """
    Get or create singleton LangGraph checkpointer instance.

    Lazy initialization: creates checkpointer on first call, returns same instance
    on subsequent calls. Tries AsyncSqliteSaver first, falls back to MemorySaver
    if SQLite backend unavailable.

    Returns:
        AsyncSqliteSaver or MemorySaver instance for StateGraph compilation

    Raises:
        ImportError: If neither AsyncSqliteSaver nor MemorySaver available

    Persistence modes:
    - AsyncSqliteSaver: Checkpoints persist in checkpoints.db (survives restarts)
    - MemorySaver: In-memory only (lost on restart, logged as warning)
    """
    global _checkpointer
    if _checkpointer is None:
        # Try async SQLite first (preferred for production)
        try:
            from pathlib import Path

            from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

            checkpoint_db = str(Path(__file__).parent.parent / "checkpoints.db")
            _checkpointer = AsyncSqliteSaver.from_conn_string(checkpoint_db)
            logger.info(
                f"LangGraph checkpointer initialized with AsyncSqliteSaver at {checkpoint_db}"
            )
        except ImportError:
            # Fall back to in-memory MemorySaver
            try:
                from langgraph.checkpoint.memory import MemorySaver

                _checkpointer = MemorySaver()
                logger.warning(
                    "AsyncSqliteSaver not available, using in-memory MemorySaver. "
                    "State will not persist across server restarts."
                )
            except ImportError:
                logger.error(
                    "No checkpointer available. Install langgraph[sqlite] or use MemorySaver."
                )
                raise

    return _checkpointer
