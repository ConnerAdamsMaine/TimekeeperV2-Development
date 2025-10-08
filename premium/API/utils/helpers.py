# premium/API/utils/helpers.py
# ============================================================================
# Utility functions for Premium API
# ============================================================================

import asyncio
from flask import current_app
from typing import Any, Coroutine


def run_async(coro: Coroutine) -> Any:
    """Helper to run async functions in Flask"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def get_bot():
    """Get bot instance from Flask app config"""
    return current_app.config.get('BOT')


async def get_tracker_and_clock():
    """Get tracker and clock instances from bot"""
    from ...Utils.timekeeper import get_shared_role_tracker
    
    bot = get_bot()
    if bot:
        return await get_shared_role_tracker(bot)
    
    # Fallback to shared tracker without bot
    from ...Utils.timekeeper import get_shared_tracker
    return await get_shared_tracker()