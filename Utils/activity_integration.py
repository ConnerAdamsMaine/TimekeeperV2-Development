# ============================================================================
# TimekeeperV2 - Premium Time Tracking System
# Copyright © 2025 404ConnerNotFound. All Rights Reserved.
# ============================================================================
#
# This source code is proprietary and confidential software.
# 
# PERMITTED:
#   - View and study the code for educational purposes
#   - Reference in technical discussions with attribution
#   - Report bugs and security issues
#
# PROHIBITED:
#   - Running, executing, or deploying this software yourself
#   - Hosting your own instance of this bot
#   - Removing or bypassing the hardware validation (DRM)
#   - Modifying for production use
#   - Distributing, selling, or sublicensing
#   - Any use that competes with the official service
#
# USAGE: To use TimekeeperV2, invite the official bot from:
#        https://timekeeper.404connernotfound.dev
#
# This code is provided for transparency only. Self-hosting is strictly
# prohibited and violates the license terms. Hardware validation is an
# integral part of this software and protected as a technological measure.
#
# NO WARRANTY: Provided "AS IS" without warranty of any kind.
# NO LIABILITY: Author not liable for any damages from unauthorized use.
#
# Full license terms: LICENSE.md (TK-RRL v2.0)
# Contact: licensing@404connernotfound.dev
# ============================================================================


import logging
from typing import Optional, Dict, Any
import discord 

logger = logging.getLogger(__name__)


async def log_clock_in_activity(bot, guild_id: int, user_id: int, category: str):
    """Log a clock in event to the activity channel"""
    try:
        # Get activity log cog
        activity_cog = bot.get_cog("ActivityLogCog")
        if not activity_cog:
            return
        
        # Get guild and user
        guild = bot.get_guild(guild_id)
        if not guild:
            return
        
        user = guild.get_member(user_id)
        if not user:
            return
        
        # Log the activity
        await activity_cog.log_activity(
            guild_id=guild_id,
            event_type="clock_in",
            user=user,
            details={'category': category}
        )
        
    except Exception as e:
        logger.error(f"Error logging clock in activity: {e}")


async def log_clock_out_activity(
    bot,
    guild_id: int,
    user_id: int,
    category: str,
    duration_seconds: int,
    duration_formatted: str,
    force: bool = False,
    admin_id: Optional[int] = None,
    reason: Optional[str] = None
):
    """Log a clock out event to the activity channel"""
    try:
        # Get activity log cog
        activity_cog = bot.get_cog("ActivityLogCog")
        if not activity_cog:
            return
        
        # Get guild and user
        guild = bot.get_guild(guild_id)
        if not guild:
            return
        
        user = guild.get_member(user_id)
        if not user:
            return
        
        # Prepare details
        details = {
            'category': category,
            'duration_seconds': duration_seconds,
            'duration_formatted': duration_formatted
        }
        
        # If force clockout, add admin info
        if force and admin_id:
            admin = guild.get_member(admin_id)
            if admin:
                details['admin'] = admin.mention
            
            if reason:
                details['reason'] = reason
        
        # Log the activity
        event_type = "force_clockout" if force else "clock_out"
        await activity_cog.log_activity(
            guild_id=guild_id,
            event_type=event_type,
            user=user,
            details=details
        )
        
    except Exception as e:
        logger.error(f"Error logging clock out activity: {e}")