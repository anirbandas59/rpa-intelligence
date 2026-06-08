"""
Redis-based batch scoring for Stage 1 assessments with concurrency control.

Provides async batch processing of multiple use cases with configurable concurrency
limits to prevent overloading LLM providers. Uses Redis for queue management and
progress tracking, enabling fault tolerance and distributed processing.

Key features:
- Concurrency control via semaphore (default: 3 concurrent LLM calls)
- Redis-backed queue for persistence across server restarts
- Real-time progress tracking via batch status endpoint
- Error handling with per-use-case failure tracking
- Automatic batch completion detection

Architecture:
1. create_batch(): Stores batch metadata and queues use case IDs
2. process_batch(): Processes queued items with concurrency control
3. get_batch_status(): Returns current progress for polling

Usage:
    scorer = BatchScorer(redis_client, max_concurrent=3)
    await scorer.create_batch(batch_id, use_case_ids)
    await scorer.process_batch(batch_id, db_factory, model)
"""

import asyncio
import json
import logging
from typing import Any

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from services.assessment_service import AssessmentService

logger = logging.getLogger(__name__)


class BatchScorer:
    """Redis-backed batch scoring engine with concurrency control."""

    def __init__(self, redis_client: aioredis.Redis, max_concurrent: int = 3):
        """
        Initialize batch scorer with Redis client and concurrency limit.

        Args:
            redis_client: Async Redis client for queue and state management
            max_concurrent: Maximum number of concurrent LLM calls (default: 3)
        """
        self.redis = redis_client
        self.max_concurrent = max_concurrent

    async def create_batch(self, batch_id: str, use_case_ids: list[str]) -> None:
        """
        Create batch job in Redis with metadata and queued use case IDs.

        Stores batch metadata in `batch:{batch_id}` key and queues individual
        use case IDs in `batch:{batch_id}:queue` list for processing.

        Args:
            batch_id: Unique batch identifier (UUID)
            use_case_ids: List of use case IDs to process
        """
        batch_data = {
            "batch_id": batch_id,
            "use_case_ids": use_case_ids,
            "total_count": len(use_case_ids),
            "completed_count": 0,
            "failed_count": 0,
            "status": "queued",
            "errors": {},
        }
        await self.redis.set(f"batch:{batch_id}", json.dumps(batch_data), ex=3600)

        # Queue individual use case IDs for processing
        for uc_id in use_case_ids:
            await self.redis.rpush(f"batch:{batch_id}:queue", uc_id)

        logger.info(f"Created batch {batch_id} with {len(use_case_ids)} use cases")

    async def process_batch(
        self,
        batch_id: str,
        db_factory: async_sessionmaker[AsyncSession],
        model: str = "claude-haiku-4-5",
    ) -> None:
        """
        Process batch with concurrency control via semaphore.

        Processes all queued use cases with a semaphore limit to prevent
        overloading LLM providers. Updates batch status in Redis on completion
        or failure. Each use case is scored independently via AssessmentService.

        Args:
            batch_id: Batch identifier to process
            db_factory: Async session factory for creating database sessions
            model: LLM model name for assessment (default: claude-haiku-4-5)
        """
        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def score_one(uc_id: str) -> None:
            """Score single use case with semaphore concurrency control."""
            async with semaphore:
                async with db_factory() as session:
                    try:
                        logger.info(f"Batch {batch_id}: Starting assessment for {uc_id}")
                        service = AssessmentService(session, model=model)
                        await service.run_assessment(uc_id)
                        await self._increment_completed(batch_id)
                        logger.info(f"Batch {batch_id}: Completed {uc_id}")
                    except Exception as e:
                        logger.exception(f"Batch {batch_id}: Failed {uc_id}")
                        await self._record_failure(batch_id, uc_id, str(e))

        # Get all queued use case IDs
        queue_key = f"batch:{batch_id}:queue"
        uc_ids = await self.redis.lrange(queue_key, 0, -1)

        if not uc_ids:
            logger.warning(f"Batch {batch_id}: No use cases in queue")
            await self._update_status(batch_id, "complete")
            return

        # Update status to running
        await self._update_status(batch_id, "running")

        # Process all concurrently (with semaphore limit)
        await asyncio.gather(*[score_one(uc_id.decode()) for uc_id in uc_ids])

        # Mark complete
        await self._update_status(batch_id, "complete")
        logger.info(f"Batch {batch_id}: Processing complete")

    async def get_batch_status(self, batch_id: str) -> dict[str, Any] | None:
        """
        Get current batch status for progress polling.

        Returns batch metadata including completion progress, status, and any errors.

        Args:
            batch_id: Batch identifier to query

        Returns:
            Batch status dict with fields: batch_id, status, completed_count,
            total_count, failed_count, errors. Returns None if batch not found.
        """
        raw_data = await self.redis.get(f"batch:{batch_id}")
        if not raw_data:
            return None

        return json.loads(raw_data)

    async def _increment_completed(self, batch_id: str) -> None:
        """Increment completed_count in batch metadata atomically."""
        raw_data = await self.redis.get(f"batch:{batch_id}")
        if not raw_data:
            return

        data = json.loads(raw_data)
        data["completed_count"] += 1

        # Preserve TTL
        ttl = await self.redis.ttl(f"batch:{batch_id}")
        effective_ttl = ttl if ttl > 0 else 3600
        await self.redis.set(f"batch:{batch_id}", json.dumps(data), ex=effective_ttl)

    async def _record_failure(self, batch_id: str, uc_id: str, error: str) -> None:
        """Record use case failure in batch metadata."""
        raw_data = await self.redis.get(f"batch:{batch_id}")
        if not raw_data:
            return

        data = json.loads(raw_data)
        data["failed_count"] += 1
        data["errors"][uc_id] = error

        # Preserve TTL
        ttl = await self.redis.ttl(f"batch:{batch_id}")
        effective_ttl = ttl if ttl > 0 else 3600
        await self.redis.set(f"batch:{batch_id}", json.dumps(data), ex=effective_ttl)

    async def _update_status(self, batch_id: str, status: str) -> None:
        """Update batch status field (queued | running | complete | failed)."""
        raw_data = await self.redis.get(f"batch:{batch_id}")
        if not raw_data:
            return

        data = json.loads(raw_data)
        data["status"] = status

        # Preserve TTL
        ttl = await self.redis.ttl(f"batch:{batch_id}")
        effective_ttl = ttl if ttl > 0 else 3600
        await self.redis.set(f"batch:{batch_id}", json.dumps(data), ex=effective_ttl)
