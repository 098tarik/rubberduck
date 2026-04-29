"""Abstract tool interfaces used by the assistant."""

import abc
from typing import Any


class Tool(abc.ABC):
    """Abstract base class for tools exposed to the assistant."""

    name: str
    description: str

    @abc.abstractmethod
    async def call(self, **kwargs: Any) -> Any:
        """Execute the tool and return its result."""
        raise NotImplementedError
