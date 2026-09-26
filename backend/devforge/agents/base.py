"""
BaseAgent — abstract base class for all DevForge agents.

All agents are ordinary Python coroutines.
They are NOT IBM Bob subagents and have no connection to IBM Bob's runtime.
"""
import logging
from abc import ABC, abstractmethod
from datetime import UTC, datetime


class BaseAgent(ABC):
    """
    Abstract base for all DevForge agents.

    Agents receive their dependencies (LLM client, event bus) at construction time.
    No global state, no singletons — fully injectable for testability.
    """

    name: str = "base"

    def __init__(self) -> None:
        self.logger = logging.getLogger(f"devforge.agents.{self.name}")

    @abstractmethod
    async def run(self, context: dict) -> dict:
        """
        Execute the agent's primary task.

        Args:
            context: Input data dict, specific to each agent subclass.

        Returns:
            Result data dict, specific to each agent subclass.
        """

    def _ts(self) -> str:
        """ISO-formatted UTC timestamp for log messages."""
        return datetime.now(UTC).isoformat()
