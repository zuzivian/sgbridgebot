import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar('T')


async def retry_async(
    action: Callable[[], Awaitable[T]],
    retry_on: tuple[type[BaseException], ...],
    delay_s: float,
    on_retry: Callable[[BaseException], None] | None = None,
) -> T:
    """Retry an async action indefinitely for the provided exception types."""
    while True:
        try:
            return await action()
        except retry_on as exc:
            if on_retry is not None:
                on_retry(exc)
            await asyncio.sleep(delay_s)
