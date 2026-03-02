"""Async helpers for OpenPrints (e.g. shutdown-aware sleep)."""

from __future__ import annotations

import asyncio


async def stop_aware_sleep(event: asyncio.Event, timeout: float) -> None:
    """
    Sleep for up to `timeout` seconds, but wake early if `event` is set.
    """
    try:
        await asyncio.wait_for(event.wait(), timeout=timeout)
    except asyncio.TimeoutError:
        pass
