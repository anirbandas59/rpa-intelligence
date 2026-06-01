"""
LangGraph checkpointer for agent state persistence.
Enables resume of interrupted runs across server restarts.
"""
import logging

logger = logging.getLogger(__name__)

_checkpointer = None


async def get_checkpointer():
    """Get or create the singleton checkpointer."""
    global _checkpointer
    if _checkpointer is None:
        # Try async SQLite first (preferred for production)
        try:
            from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
            from pathlib import Path
            checkpoint_db = str(Path(__file__).parent.parent / "checkpoints.db")
            _checkpointer = AsyncSqliteSaver.from_conn_string(checkpoint_db)
            logger.info(f"LangGraph checkpointer initialized with AsyncSqliteSaver at {checkpoint_db}")
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
                logger.error("No checkpointer available. Install langgraph[sqlite] or use MemorySaver.")
                raise

    return _checkpointer
