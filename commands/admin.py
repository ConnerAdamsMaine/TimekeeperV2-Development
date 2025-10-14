# ============================================================================
# TimekeeperV2 - Premium Time Tracking System
# Copyright © 2025 404ConnerNotFound. All Rights Reserved.
# ============================================================================

import discord 
from discord.ext import commands
from discord import app_commands
import logging
from typing import Optional, Dict, Any, List
import asyncio
from datetime import datetime, timedelta
import os

from Utils.timekeeper import (
    get_shared_role_tracker, 
    get_system_status,
)

logger = logging.getLogger(__name__)


class TimecardAdminCog(commands.Cog):
    """Administrative timecard system"""
    
    def __init__(self, bot):
        self.bot = bot
        self.tracker = None
        self.clock = None
        
        self.admin_metrics = {
            'categories_managed': 0,
            'leaderboard_requests': 0,
            'admin_commands': 0,
        }
        
        logger.info("TimecardAdminCog initialized")
    
    async def cog_load(self):
        try:
            self.tracker, self.clock = await get_shared_role_tracker(self.bot)
            logger.info("TimecardAdminCog connected to tracker")
        except Exception as e:
            logger.error(f"Failed to initialize admin system: {e}")
    
    async def cog_unload(self):
        logger.info("TimecardAdminCog unloaded")
    
    async def _ensure_initialized(self):
        if not self.tracker or not self.clock:
            try:
                self.tracker, self.clock = await get_shared_role_tracker(self.bot)
            except Exception as e:
                logger.error(f"Failed to reinitialize tracker: {e}")
                raise commands.CommandError("🔧 Admin system temporarily unavailable.")
    
    def _create_error_embed(self, result: Dict[str, Any]) -> discord.Embed:
        embed = discord.Embed(
            title="❌ Error",
            description=result['message'],
            color=discord.Color.red()
        )
        if result.get('error_code'):
            embed.add_field(name="Error Code", value=f"`{result['error_code']}`", inline=True)
        return embed
    
    def _create_generic_error_embed(self, error: Exception) -> discord.Embed:
        embed = discord.Embed(
            title="❌ Unexpected Error",
            description="An unexpected error occurred.",
            color=discord.Color.red()
        )
        embed.add_field(name="🆔 Error ID", value=f"`{hash(str(error)) % 100000:05d}`", inline=True)
        return embed
    
    admin_group = app_commands.Group(name="admin", description="👑 Admin commands")
    
    @admin_group.command(name="categories", description="👑 Manage categories (Dev Only)")
    @app_commands.describe(
        action="Action to perform",
        name="Category name (for add/remove)",
        description="Description for category",
        color="Hex color (e.g., #FF5733)"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="list", value="list"),
        app_commands.Choice(name="add", value="add"),
        app_commands.Choice(name="remove", value="remove")
    ])
    async def admin_categories(self, interaction: discord.Interaction, action: str, 
                              name: Optional[str] = None, description: Optional[str] = None, 
                              color: Optional[str] = None):
        """Manage categories"""
        await interaction.response.defer()
        
        if interaction.user.id != int(os.getenv("DEV_USER_ID", 0)):
            embed = discord.Embed(
                title="🔒 Developer Only",
                description="This command is restricted to the developer.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed)
            return
        
        try:
            await self._ensure_initialized()
            
            if action == "list":
                categories = await self.tracker.list_categories(
                    interaction.guild.id, 
                    include_archived=False, 
                    include_metadata=True
                )
                
                embed = discord.Embed(
                    title="📋 Server Categories",
                    color=discord.Color.blue()
                )
                
                if not categories:
                    embed.description = "No categories configured."
                    embed.add_field(
                        name="💡 Common Categories",
                        value="• `work` • `meetings` • `development` • `support` • `training` • `break`",
                        inline=False
                    )
                else:
                    active_cats = []
                    for cat, info in categories.items():
                        if info.get('active', True):
                            metadata = info.get('metadata', {})
                            usage = info.get('usage', {})
                            
                            cat_display = f"**{cat}**"
                            if metadata.get('description'):
                                cat_display += f"\n*{metadata['description']}*"
                            if usage.get('total_time'):
                                cat_display += f"\n📊 {usage['total_time_formatted']} tracked"
                            
                            active_cats.append(cat_display)
                    
                    if active_cats:
                        chunk_size = 5
                        for i in range(0, len(active_cats), chunk_size):
                            chunk = active_cats[i:i + chunk_size]
                            field_name = "📂 Categories" if i == 0 else "📂 More Categories"
                            embed.add_field(name=field_name, value="\n\n".join(chunk), inline=False)
                    
                    embed.add_field(
                        name="ℹ️ Usage",
                        value="Use `/clockin <category>` to start tracking",
                        inline=False
                    )
                
                embed.set_footer(text="Only admins can add/remove categories")
                
            elif action in ["add", "remove"]:
                if not interaction.user.guild_permissions.administrator:
                    embed = discord.Embed(
                        title="🔒 Admin Only",
                        description="Only administrators can manage categories.",
                        color=discord.Color.red()
                    )
                    await interaction.followup.send(embed=embed)
                    return
                
                if not name:
                    embed = discord.Embed(
                        title="❌ Missing Category Name",
                        description=f"Provide a category name for **{action}**.",
                        color=discord.Color.red()
                    )
                    await interaction.followup.send(embed=embed)
                    return
                
                if action == "add":
                    result = await self.tracker.add_category(
                        interaction.guild.id, name, user_id=interaction.user.id,
                        description=description, color=color
                    )
                    
                    if result['success']:
                        embed = discord.Embed(
                            title="✅ Category Added",
                            description=f"Added **{result['category']}**!",
                            color=discord.Color.green()
                        )
                        
                        metadata = result.get('metadata', {})
                        if metadata:
                            embed.add_field(
                                name="📊 Details",
                                value=f"**Name:** `{metadata['name']}`\n"
                                      f"**Description:** {metadata.get('description', 'None')}\n"
                                      f"**Color:** {metadata.get('color', 'Auto')}",
                                inline=False
                            )
                        
                        embed.add_field(
                            name="🚀 Next",
                            value=f"Users can now track: `/clockin {result['category']}`",
                            inline=False
                        )
                        
                        self.admin_metrics['categories_managed'] += 1
                        logger.info(f"Category added: {name} in guild {interaction.guild.id}")
                    else:
                        embed = self._create_error_embed(result)
                        if result.get('error_code') == 'CATEGORY_EXISTS':
                            embed.add_field(
                                name="💡 Alternative",
                                value="View existing: `/admin categories list`",
                                inline=False
                            )
                
                elif action == "remove":
                    result = await self.tracker.remove_category(
                        interaction.guild.id, name, user_id=interaction.user.id
                    )
                    
                    if result['success']:
                        action_taken = result.get('action', 'removed')
                        embed = discord.Embed(
                            title=f"✅ Category {action_taken.title()}",
                            description=f"{action_taken.title()} **{name}** from server.",
                            color=discord.Color.green()
                        )
                        
                        usage_info = result.get('usage_info', {})
                        if usage_info and usage_info.get('total_time', 0) > 0:
                            embed.add_field(
                                name="📊 Historical Data",
                                value=f"**Preserved:** {usage_info['total_time_formatted']} from {usage_info['unique_users']} users\n"
                                      f"**Entries:** {usage_info['total_entries']} archived",
                                inline=False
                            )
                        
                        if action_taken == "archived":
                            embed.add_field(
                                name="ℹ️ Note",
                                value="Archived (not deleted) because it contains data.",
                                inline=False
                            )
                        
                        self.admin_metrics['categories_managed'] += 1
                        logger.info(f"Category {action_taken}: {name} in guild {interaction.guild.id}")
                    else:
                        embed = self._create_error_embed(result)
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Admin categories error: {e}", exc_info=True)
            embed = self._create_generic_error_embed(e)
            await interaction.followup.send(embed=embed)

    @admin_group.command(name="system", description="🔧 View system status")
    async def admin_system(self, interaction: discord.Interaction):
        """System status"""
        await interaction.response.defer()
        
        try:
            if interaction.user.id != int(os.getenv("DEV_USER_ID", 0)):
                embed = discord.Embed(
                    title="🔒 Admin Only",
                    description="Only administrators can view system status.",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed)
                return
            
            await self._ensure_initialized()
            
            system_status = await get_system_status()
            
            embed = discord.Embed(
                title="🔧 System Status",
                color=discord.Color.green() if system_status['status'] == 'operational' else discord.Color.red()
            )
            
            embed.add_field(
                name="🌐 Status",
                value=f"**{system_status['status'].title()}**",
                inline=True
            )
            
            tracker_health = system_status.get('tracker_health', {})
            if tracker_health:
                embed.add_field(
                    name="🏥 Health",
                    value=f"**Score:** {tracker_health.get('health_score', 0):.1f}%\n"
                          f"**Status:** {tracker_health.get('status', 'unknown').title()}",
                    inline=True
                )
            
            clock_metrics = system_status.get('clock_metrics', {})
            if clock_metrics:
                embed.add_field(
                    name="⏰ Sessions",
                    value=f"**Created:** {clock_metrics.get('total_sessions_created', 0)}\n"
                          f"**Completed:** {clock_metrics.get('total_sessions_completed', 0)}",
                    inline=True
                )
            
            if tracker_health.get('components'):
                components = tracker_health['components']
                
                redis_info = components.get('redis', {})
                embed.add_field(
                    name="💾 Redis",
                    value=f"**Status:** {redis_info.get('status', 'unknown').title()}\n"
                          f"**Response:** {redis_info.get('response_time_ms', 0):.1f}ms",
                    inline=True
                )
                
                perf_info = components.get('performance', {})
                embed.add_field(
                    name="📊 Performance",
                    value=f"**Avg:** {perf_info.get('avg_response_time_ms', 0):.1f}ms\n"
                          f"**Success:** {perf_info.get('success_rate', 0):.1f}%",
                    inline=True
                )
                
                cache_info = components.get('cache', {})
                embed.add_field(
                    name="🗂️ Cache",
                    value=f"**Hit Rate:** {cache_info.get('hit_rate', 0):.1f}%",
                    inline=True
                )
            
            embed.set_footer(text="System monitoring • Real-time")
            
            await interaction.followup.send(embed=embed)
            self.admin_metrics['admin_commands'] += 1
            
        except Exception as e:
            logger.error(f"Admin system error: {e}", exc_info=True)
            embed = self._create_generic_error_embed(e)
            await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(TimecardAdminCog(bot))
    logger.info("TimecardAdminCog loaded")

async def teardown(bot):
    cog = bot.get_cog("TimecardAdminCog")
    if cog:
        await cog.cog_unload()
    logger.info("TimecardAdminCog unloaded")