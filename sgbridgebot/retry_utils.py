import asyncio
import logging
import random

from telegram.error import TimedOut


LOGGER = logging.getLogger(__name__)


async def retry_on_timeout(
    operation_name,
    callback,
    *,
    chat_id=None,
    message_id=None,
    retry_log_message=None,
    max_attempts=4,
    backoff_base=0.5,
    backoff_cap=2.0,
):
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    last_exception = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await callback()
        except TimedOut as exc:
            last_exception = exc
            if attempt >= max_attempts:
                break

            backoff = min(backoff_base * (2 ** (attempt - 1)), backoff_cap)
            jitter = random.uniform(0, backoff / 2) if backoff > 0 else 0
            delay = min(backoff + jitter, backoff_cap)
            log_message = retry_log_message or "Retrying %s after timeout"
            LOGGER.warning(
                "%s (operation=%s, chat_id=%s, message_id=%s, attempt=%s/%s, sleep=%.2fs)",
                log_message,
                operation_name,
                chat_id,
                message_id,
                attempt,
                max_attempts - 1,
                delay,
            )
            await asyncio.sleep(delay)

    if last_exception is None:
        raise RuntimeError("retry_on_timeout exhausted without capturing TimedOut")
    raise last_exception
