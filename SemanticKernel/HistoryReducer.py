import logging
import sys

if sys.version < "3.11":
    from typing_extensions import Self  # pragma: no cover
else:
    from typing import Self  # type: ignore # pragma: no cover
if sys.version < "3.12":
    from typing_extensions import override  # pragma: no cover
else:
    from typing import override  # type: ignore  # pragma: no cover

from typing import List
from semantic_kernel.contents import ChatHistoryReducer
from semantic_kernel.contents.utils.author_role import AuthorRole
from semantic_kernel.utils.feature_stage_decorator import experimental
from semantic_kernel.contents.history_reducer.chat_history_reducer_utils import (
    extract_range,
    locate_safe_reduction_index,
)


from pydantic import Field


@experimental
class CustomChatHistory(ChatHistoryReducer):
    target_count: int = Field(..., gt=0, description="Target message count.")
    threshold_count: int = Field(
        default=0, ge=0, description="Threshold count to avoid orphaning messages."
    )
    auto_reduce: bool = Field(
        default=False,
        description="Whether to automatically reduce the chat history, this happens when using add_message_async.",
    )

    @override
    async def reduce(self) -> Self | None:
        history = self.messages
        if len(history) <= self.target_count + (self.threshold_count or 0):
            # No need to reduce
            return None

        new_history = [m for m in history if m.role != AuthorRole.TOOL]

        truncation_index = locate_safe_reduction_index(
            new_history, self.target_count, self.threshold_count
        )
        if truncation_index is None:
            return None
        truncated_list = extract_range(history, start=truncation_index)
        self.messages = truncated_list
        if not any(m.role == AuthorRole.SYSTEM for m in history):
            history.add_system_message(self.system_message)

        self.messages = truncated_list
        return self

    def __eq__(self, other: object) -> bool:
        """Compare equality based on truncation settings.

        (We don't factor in the actual ChatHistory messages themselves.)

        Returns:
            True if the other object is a ChatHistoryTruncationReducer with the same truncation settings.
        """
        if not isinstance(other, CustomChatHistory):
            return False
        return (
            self.threshold_count == other.threshold_count
            and self.target_count == other.target_count
        )

    def __hash__(self) -> int:
        """Return a hash code based on truncation settings.

        Returns:
            A hash code based on the truncation settings.
        """
        return hash((self.__class__.__name__, self.threshold_count, self.target_count))
