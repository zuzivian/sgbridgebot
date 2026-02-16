import asyncio

import pytest
from telegram.error import TimedOut

from sgbridgebot import retry_utils


def test_retry_on_timeout_rejects_invalid_max_attempts():
    async def callback():
        return "ok"

    with pytest.raises(ValueError, match="at least 1"):
        asyncio.run(retry_utils.retry_on_timeout("send", callback, max_attempts=0))


def test_retry_on_timeout_retries_then_returns_value(monkeypatch):
    attempts = {"count": 0}
    sleeps = []

    async def callback():
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise TimedOut("timeout")
        return "done"

    async def fake_sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr(retry_utils.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(retry_utils.random, "uniform", lambda _a, _b: 0)

    result = asyncio.run(
        retry_utils.retry_on_timeout(
            "send_message",
            callback,
            max_attempts=4,
            backoff_base=0.25,
            backoff_cap=1.0,
        )
    )

    assert result == "done"
    assert attempts["count"] == 3
    assert sleeps == [0.25, 0.5]


def test_retry_on_timeout_raises_after_max_attempts(monkeypatch):
    async def always_timeout():
        raise TimedOut("still timing out")

    sleeps = []

    async def fake_sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr(retry_utils.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(retry_utils.random, "uniform", lambda _a, _b: 0)

    with pytest.raises(TimedOut):
        asyncio.run(
            retry_utils.retry_on_timeout(
                "edit_message",
                always_timeout,
                max_attempts=3,
                backoff_base=0.1,
                backoff_cap=0.5,
            )
        )

    assert sleeps == [0.1, 0.2]


def test_retry_on_timeout_does_not_swallow_non_timeout_exceptions():
    class BoomError(RuntimeError):
        pass

    async def callback():
        raise BoomError("boom")

    with pytest.raises(BoomError, match="boom"):
        asyncio.run(retry_utils.retry_on_timeout("op", callback, max_attempts=3))
