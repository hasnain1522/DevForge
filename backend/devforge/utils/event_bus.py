"""
EventBus — connects agents to the SSE endpoint via in-process async queues.

Phase 1: full structure in place, ready for Phase 3 SSE integration.
"""
import asyncio
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime

logger = logging.getLogger(__name__)


@dataclass
class SubtaskLogEvent:
    """
    A single log event emitted by an agent during mission execution.
    This is the SSE payload format defined in DATA_MODEL.md.
    """
    execution_run_id: str
    agent_type: str          # implementer | tester | documenter | orchestrator
    event_type: str          # started | progress | completed | failed
    message: str
    target_file: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_sse_dict(self) -> dict:
        """Serialise for SSE transport."""
        return {
            "execution_run_id": self.execution_run_id,
            "agent_type": self.agent_type,
            "event_type": self.event_type,
            "message": self.message,
            "target_file": self.target_file,
            "timestamp": self.timestamp.isoformat(),
        }


class EventBus:
    """
    In-process async event bus.

    Agents publish SubtaskLogEvents; the SSE endpoint subscribes per run_id.
    Events are also persisted to the subtask_logs table (Phase 3).

    Phase 1: queue management in place. DB persistence wired in Phase 3.
    """

    def __init__(self) -> None:
        self._queues: dict[str, asyncio.Queue[SubtaskLogEvent | None]] = {}

    def _ensure_queue(self, run_id: str) -> asyncio.Queue[SubtaskLogEvent | None]:
        if run_id not in self._queues:
            self._queues[run_id] = asyncio.Queue()
        return self._queues[run_id]

    async def publish(self, run_id: str, event: SubtaskLogEvent) -> None:
        """
        Publish an event for a specific execution run.

        Phase 3 will also persist the event to the subtask_logs table.
        """
        queue = self._ensure_queue(run_id)
        await queue.put(event)
        logger.debug("EventBus: published %s/%s for run %s", event.agent_type, event.event_type, run_id)

    async def complete(self, run_id: str) -> None:
        """Signal that the execution run is finished (sentinel None)."""
        queue = self._ensure_queue(run_id)
        await queue.put(None)

    async def subscribe(self, run_id: str) -> AsyncIterator[SubtaskLogEvent]:
        """
        Yield events for a specific execution run until completion.
        Used by the SSE endpoint (Phase 3).
        """
        queue = self._ensure_queue(run_id)
        while True:
            event = await queue.get()
            if event is None:
                break
            yield event

    def cleanup(self, run_id: str) -> None:
        """Remove the queue for a completed run."""
        self._queues.pop(run_id, None)


# Application-level singleton — imported by agents and API routes
event_bus = EventBus()
