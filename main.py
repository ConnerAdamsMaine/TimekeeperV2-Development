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


import argparse
import os
from dotenv import load_dotenv
import logging
import discord 
import tkinter as tk

from Core.Bot import Bot

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if __name__ == '__main__':    
    TOKEN = os.getenv("DISCORD_AUTH_TOKEN")
    PREFIX = os.getenv("COMMAND_PREFIX", ".")
    
    bot = Bot(prefix=PREFIX, intents=discord.Intents.all())

    bot.run(TOKEN)

#if __name__ == '__main__':
#    parser = argparse.ArgumentParser(description="Discord Bot")
#    parser.add_argument("--token", type=str, default=os.getenv("DISCORD_AUTH_TOKEN"), required=True, help="Discord bot token")
#    parser.add_argument("--prefix", type=str, default="!", help="Command prefix")
#    parser.add_argument("--lazy", action="store_true", help="Enable lazy loading of cogs")
#    parser.add_argument("--logging-level", type=int, default="20", help="Logging level")
#    
#    args = parser.parse_args()
#    print(args)
#    
#    token = args.token
#    prefix = args.prefix
#    lazy = args.lazy
#    level = args.logging_level
#    
#    if token.lower() == "env":
#        token = os.getenv("DISCORD_AUTH_TOKEN") or ""
#    
#    match level:
#        case 10:
#            level = logging.DEBUG
#        case 20:
#            level = logging.INFO
#        case 30:
#            level = logging.WARNING
#        case 40:
#            level = logging.ERROR
#        case 50:
#            level = logging.CRITICAL
#        case _:
#            level = logging.INFO
#            
#            
#    logging.basicConfig(level=level)
#    logger.info("Starting bot...")
#    intents = discord.Intents.all()
#    
#    bot = Bot(prefix=prefix, intents=intents)
#    if not token:
#        logger.error("No token provided. Exiting.")
#        exit(1)
#        
#    bot.run(token)