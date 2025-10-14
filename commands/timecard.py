# ============================================================================
# TimekeeperV2 - Premium Time Tracking System
# Copyright © 2025 404ConnerNotFound. All Rights Reserved.
# ============================================================================

import discord 
from discord.ext import commands
from discord import app_commands
import logging
from typing import Optional, Dict, Any
import asyncio
from datetime import datetime

from Utils.timekeeper import (
    get_shared_role_tracker, 
    close_shared_role_tracker,
    ValidationError,
    CategoryError,
    PermissionError,
    CircuitBreakerOpenError,
    TimeTrackerError
)

logger = logging.getLogger(__name__)


class TimecardCog(commands.Cog):
    """Core timecard system - clock in, clock out, and status commands"""
    
    def __init__(self, bot):
        self.bot = bot
        self.tracker = None
        self.clock = None
        
        self.command_metrics = {
            'clockin_count': 0,
            'clockout_count': 0, 
            'status_count': 0,
            'total_response_time': 0.0,
            'error_count': 0
        }
        
        logger.info("TimecardCog initialized")
    
    async def cog_load(self):
        """Initialize enterprise tracker when cog loads"""
        try:
            self.tracker, self.clock = await get_shared_role_tracker(self.bot)
            logger.info("TimecardCog connected to tracker system")
            asyncio.create_task(self._performance_monitor())
        except Exception as e:
            logger.error(f"Failed to initialize timecard: {e}", exc_info=True)
    
    async def cog_unload(self):
        """Cleanup when cog unloads"""
        try:
            await close_shared_role_tracker()
            logger.info("TimecardCog unloaded")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    async def _ensure_initialized(self):
        """Ensure tracker is initialized with retry logic"""
        if not self.tracker or not self.clock:
            try:
                self.tracker, self.clock = await get_shared_role_tracker(self.bot)
            except Exception as e:
                logger.error(f"Failed to reinitialize tracker: {e}")
                raise commands.CommandError("🔧 Timecard system temporarily unavailable.")
    
    async def _track_command_performance(self, command_name: str, start_time: float, success: bool):
        """Track command performance metrics"""
        response_time = datetime.now().timestamp() - start_time
        self.command_metrics['total_response_time'] += response_time
        
        if success:
            self.command_metrics[f'{command_name}_count'] += 1
        else:
            self.command_metrics['error_count'] += 1
    
    async def _performance_monitor(self):
        """Background performance monitoring"""
        while True:
            try:
                await asyncio.sleep(300)  # Every 5 minutes
                
                total_commands = sum([
                    self.command_metrics['clockin_count'],
                    self.command_metrics['clockout_count'],
                    self.command_metrics['status_count']
                ])
                
                if total_commands > 0:
                    avg_response = self.command_metrics['total_response_time'] / total_commands
                    error_rate = (self.command_metrics['error_count'] / 
                                (total_commands + self.command_metrics['error_count']) * 100)
                    
                    logger.info(f"Performance - Commands: {total_commands}, "
                              f"Error Rate: {error_rate:.1f}%, Avg Response: {avg_response:.3f}s")
                
            except Exception as e:
                logger.error(f"Performance monitor error: {e}")
    
    def _get_category_suggestions(self, input_category: str, available_categories: list) -> list:
        """Get smart category suggestions using fuzzy matching"""
        if not available_categories:
            return []
            
        suggestions = []
        input_lower = input_category.lower()
        
        # Exact substring matches first
        for cat in available_categories:
            if input_lower in cat.lower() or cat.lower() in input_lower:
                suggestions.append(cat)
        
        # Similar sounding matches
        if not suggestions:
            for cat in available_categories:
                if len(set(input_lower) & set(cat.lower())) >= min(2, len(input_lower) // 2):
                    suggestions.append(cat)
        
        return suggestions[:3]
    
    def _get_session_tips(self, category: str) -> Optional[str]:
        """Get contextual tips based on category"""
        tips = {
            'work': "💪 Stay focused! Consider using the Pomodoro technique (25min work, 5min break)",
            'meeting': "🗣️ Remember to take notes and track action items",
            'development': "💻 Great for coding sessions! Don't forget to commit your code",
            'break': "☕ Enjoy your break! Even short breaks boost productivity",
            'training': "📚 Learning time! Take notes and practice what you learn",
            'support': "🆘 Helping others builds teamwork and knowledge sharing"
        }
        return tips.get(category)
    
    def _create_error_embed(self, result: Dict[str, Any]) -> discord.Embed:
        """Create standardized error embed"""
        embed = discord.Embed(
            title="❌ Error",
            description=result['message'],
            color=discord.Color.red()
        )
        
        if result.get('error_code'):
            embed.add_field(
                name="Error Code",
                value=f"`{result['error_code']}`",
                inline=True
            )
        
        return embed
    
    def _create_generic_error_embed(self, error: Exception) -> discord.Embed:
        """Create generic error embed for unexpected errors"""
        embed = discord.Embed(
            title="❌ Unexpected Error",
            description="An unexpected error occurred. The team has been notified.",
            color=discord.Color.red()
        )
        embed.add_field(
            name="🆔 Error ID",
            value=f"`{hash(str(error)) % 100000:05d}`",
            inline=True
        )
        return embed
    
    # ========================================================================
    # CLOCK IN COMMAND
    # ========================================================================
    @app_commands.command(name="clockin", description="🕐 Clock in to start tracking time")
    @app_commands.describe(
        category="Category to track time for",
        description="Optional description for this session"
    )
    async def clockin(self, interaction: discord.Interaction, category: str = "main", 
                     description: Optional[str] = None):
        """Clock in command with enterprise features"""
        start_time = datetime.now().timestamp()
        await interaction.response.defer()
        
        try:
            await self._ensure_initialized()
            
            # Get categories
            categories_info = await self.tracker.list_categories(
                interaction.guild.id, 
                include_metadata=True
            )
            
            # Determine role
            role = "Break" if category.lower().strip() == 'break' else "Clocked In"
            
            # Check if categories exist
            if not categories_info:
                logger.warning(f"No categories configured for guild {interaction.guild.id}")
                embed = discord.Embed(
                    title="⚙️ Categories Not Configured",
                    description="This server hasn't set up any time tracking categories yet.",
                    color=discord.Color.orange()
                )
                embed.add_field(
                    name="👑 Server Admins",
                    value="Use `/admin categories add <name>` to set up your first category\n"
                        "Example: `/admin categories add work`",
                    inline=False
                )
                embed.add_field(
                    name="💡 Suggested Categories",
                    value="• `work` • `meetings` • `development` • `support` • `training`",
                    inline=False
                )
                await interaction.followup.send(embed=embed)
                await self._track_command_performance("clockin", start_time, False)
                return
            
            # Validate category
            if category.lower().strip() not in categories_info:
                logger.debug(f"Invalid category '{category}' for guild {interaction.guild.id}")
                
                suggestions = self._get_category_suggestions(category, list(categories_info.keys()))
                
                embed = discord.Embed(
                    title="❌ Category Not Available",
                    description=f"**'{category}'** is not set up for this server.",
                    color=discord.Color.red()
                )
                
                if suggestions:
                    embed.add_field(
                        name="🎯 Did you mean?",
                        value=", ".join(f"`{cat}`" for cat in suggestions[:3]),
                        inline=False
                    )
                
                active_categories = [cat for cat, info in categories_info.items() if info.get('active', True)]
                
                if active_categories:
                    embed.add_field(
                        name="📋 Available Categories",
                        value=", ".join(f"`{cat}`" for cat in sorted(active_categories)[:10]),
                        inline=False
                    )
                
                await interaction.followup.send(embed=embed)
                await self._track_command_performance("clockin", start_time, False)
                return
            
            # Prepare metadata
            session_metadata = {
                'description': description,
                'guild_name': interaction.guild.name,
                'channel_id': interaction.channel_id,
            }
            
            # Clock in
            logger.info(f"Clock in: user={interaction.user.id}, guild={interaction.guild.id}, category={category}")
            
            result = await self.clock.clock_in(
                server_id=interaction.guild.id,
                user_id=interaction.user.id,
                category=category,
                interaction=interaction,
                role=role,
                metadata=session_metadata
            )
            
            if result['success']:
                # Get category metadata
                category_info = categories_info.get(category, {})
                category_metadata = category_info.get('metadata', {})
                color_hex = category_metadata.get('color', '#3498db')
                
                embed = discord.Embed(
                    title="⏰ Successfully Clocked In",
                    description=result['message'],
                    color=int(color_hex.replace('#', ''), 16)
                )
                
                # Main session info
                embed.add_field(
                    name="📊 Session Details",
                    value=f"**Category:** `{result['category']}`\n"
                        f"**Started:** <t:{int(result['start_time'].timestamp())}:t>\n"
                        f"**Session ID:** `{result['session_id'][:8]}...`",
                    inline=False
                )
                
                # Role status
                status_items = []
                if result.get('role_assigned'):
                    status_items.append("✅ Role assigned")
                elif result.get('role_warning'):
                    status_items.append(f"⚠️ {result['role_warning']}")
                
                if status_items:
                    embed.add_field(
                        name="🔧 System Status",
                        value="\n".join(status_items),
                        inline=True
                    )
                
                # Category insights
                if category_metadata:
                    productivity_weight = category_metadata.get('productivity_weight', 1.0)
                    if productivity_weight != 1.0:
                        embed.add_field(
                            name="📈 Category Info",
                            value=f"Productivity Weight: {productivity_weight}x",
                            inline=True
                        )
                
                # Session tips
                tips = self._get_session_tips(category)
                if tips:
                    embed.add_field(
                        name="💡 Session Tips",
                        value=tips,
                        inline=False
                    )
                
                embed.set_footer(text="Use /clockout when finished • /status for session details")
                logger.info(f"Clock in successful: user={interaction.user.id}, session={result['session_id']}")
                
            else:
                logger.warning(f"Clock in failed: user={interaction.user.id}, reason={result.get('message')}")
                embed = self._create_error_embed(result)
            
            await interaction.followup.send(embed=embed)
            await self._track_command_performance("clockin", start_time, result['success'])
            
        except CircuitBreakerOpenError as e:
            logger.error(f"Circuit breaker open: {e}")
            embed = discord.Embed(
                title="🔧 Service Temporarily Unavailable",
                description="The timecard system is experiencing high load. Please try again in a moment.",
                color=discord.Color.orange()
            )
            await interaction.followup.send(embed=embed)
            await self._track_command_performance("clockin", start_time, False)
            
        except Exception as e:
            logger.error(f"Clock in error: user={interaction.user.id}, error={e}", exc_info=True)
            embed = self._create_generic_error_embed(e)
            await interaction.followup.send(embed=embed)
            await self._track_command_performance("clockin", start_time, False)
    
    # ========================================================================
    # CLOCK OUT COMMAND
    # ========================================================================
    @app_commands.command(name="clockout", description="🕐 Clock out to stop tracking time")
    async def clockout(self, interaction: discord.Interaction):
        """Clock out command with session analytics"""
        start_time = datetime.now().timestamp()
        await interaction.response.defer()
        
        try:
            await self._ensure_initialized()
            
            # Attempt to clock out
            result = await self.clock.clock_out(
                interaction.guild.id,
                interaction.user.id
            )
            
            if result['success']:
                embed = discord.Embed(
                    title="✅ Successfully Clocked Out",
                    description=result['message'],
                    color=discord.Color.green()
                )
                
                # Session summary
                embed.add_field(
                    name="📊 Session Summary",
                    value=f"**Category:** `{result['category']}`\n"
                          f"**Duration:** {result['session_duration_formatted']}\n"
                          f"**Session:** <t:{int(result['start_time'].timestamp())}:t> → <t:{int(result['end_time'].timestamp())}:t>",
                    inline=False
                )
                
                # Progress and totals
                if result.get('time_added'):
                    embed.add_field(
                        name="📈 Progress Update",
                        value=f"**Category Total:** {result['time_added']['category_total_formatted']}\n"
                              f"**Time Added:** {result['session_duration_formatted']}",
                        inline=True
                    )
                
                # Session quality
                quality_analysis = self._analyze_session_quality(result['session_duration'], result['category'])
                if quality_analysis:
                    embed.add_field(
                        name="🎯 Session Analysis",
                        value=quality_analysis,
                        inline=True
                    )
                
                # System status
                status_items = []
                if result.get('role_removed'):
                    status_items.append("✅ Role removed")
                elif result.get('role_warning'):
                    status_items.append(f"⚠️ {result['role_warning']}")
                
                if status_items:
                    embed.add_field(
                        name="🔧 System Status",
                        value="\n".join(status_items),
                        inline=True
                    )
                
                # Insights
                insights = self._generate_session_insights(result['session_duration'], result['category'])
                if insights:
                    embed.add_field(
                        name="💡 Insights",
                        value=insights,
                        inline=False
                    )
                
                embed.set_footer(text="Use /status for detailed analytics")
                logger.info(f"Clock out: user={interaction.user.id}, duration={result['session_duration']}s")
                
            else:
                embed = self._create_error_embed(result)
                
                # Add helpful suggestions
                if result.get('error_code') == 'NOT_CLOCKED_IN':
                    embed.add_field(
                        name="💡 Quick Actions",
                        value="• Use `/clockin` to start tracking\n• Use `/status` to see your progress",
                        inline=False
                    )
            
            await interaction.followup.send(embed=embed)
            await self._track_command_performance("clockout", start_time, result['success'])
            
        except Exception as e:
            logger.error(f"Clock out error: user={interaction.user.id}, error={e}", exc_info=True)
            embed = self._create_generic_error_embed(e)
            await interaction.followup.send(embed=embed)
            await self._track_command_performance("clockout", start_time, False)
    
    def _analyze_session_quality(self, duration_seconds: int, category: str) -> Optional[str]:
        """Analyze session quality and provide feedback"""
        hours = duration_seconds / 3600
        
        if category in ['work', 'development']:
            if hours >= 4:
                return "🌟 **Excellent** - Great deep work session!"
            elif hours >= 2:
                return "👍 **Good** - Solid focused session"
            elif hours >= 1:
                return "✅ **Fair** - Good progress made"
            elif hours >= 0.5:
                return "⚡ **Short** - Every bit counts!"
            else:
                return "⏱️ **Brief** - Consider longer sessions"
        
        elif category == 'meeting':
            if hours <= 0.5:
                return "⚡ **Efficient** - Concise and focused"
            elif hours <= 1.5:
                return "✅ **Standard** - Good meeting length"
            else:
                return "🕐 **Extended** - Consider shorter meetings"
        
        elif category == 'break':
            if hours <= 0.5:
                return "☕ **Perfect** - Refreshing break"
            else:
                return "🛋️ **Extended** - Long break taken"
        
        return None
    
    def _generate_session_insights(self, duration_seconds: int, category: str) -> Optional[str]:
        """Generate personalized insights for the session"""
        hours = duration_seconds / 3600
        insights = []
        
        if category in ['work', 'development'] and hours >= 2:
            insights.append("🧠 Deep work achieved")
        
        if category == 'break' and hours >= 0.25:
            insights.append("🔋 Mental battery recharged")
        
        if hours >= 1 and category != 'break':
            insights.append("📈 Productivity score boosted")
        
        return " • ".join(insights) if insights else None
    
    # ========================================================================
    # STATUS COMMAND
    # ========================================================================
    @app_commands.command(name="status", description="📊 Check your time tracking status")
    async def status(self, interaction: discord.Interaction):
        """Status command with comprehensive analytics"""
        start_time = datetime.now().timestamp()
        await interaction.response.defer()
        
        try:
            await self._ensure_initialized()
            
            # Get status
            status = await self.clock.get_status(interaction.guild.id, interaction.user.id)
            
            if status.get('error'):
                logger.error(f"Status error: user={interaction.user.id}, error={status['error']}")
                embed = discord.Embed(
                    title="❌ Error Getting Status",
                    description=f"Error: {status['error']}",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed)
                await self._track_command_performance("status", start_time, False)
                return
            
            if status['clocked_in']:
                # Currently clocked in
                embed = discord.Embed(
                    title="⏰ Currently Clocked In",
                    color=discord.Color.blue()
                )
                
                embed.add_field(
                    name="📊 Active Session",
                    value=f"**Category:** `{status['category']}`\n"
                          f"**Duration:** {status['current_duration_formatted']}\n"
                          f"**Started:** <t:{int(status['start_time'].timestamp())}:t>",
                    inline=False
                )
                
                # Analytics
                analytics = status.get('analytics', {})
                if analytics:
                    quality = analytics.get('session_quality', 'good')
                    quality_emoji = {
                        'excellent': '🌟', 'good': '👍', 'fair': '✅', 
                        'starting': '🚀', 'long': '🕐', 'extended': '⏰'
                    }.get(quality, '📊')
                    
                    analytics_text = f"{quality_emoji} **Quality:** {quality.title()}"
                    
                    if analytics.get('productivity_estimate'):
                        productivity = analytics['productivity_estimate'] * 100
                        analytics_text += f"\n📈 **Productivity:** {productivity:.0f}%"
                    
                    if analytics.get('recommended_break_in'):
                        analytics_text += f"\n☕ **Break:** {analytics['recommended_break_in']}"
                    
                    embed.add_field(
                        name="🧠 Session Analytics",
                        value=analytics_text,
                        inline=True
                    )
                
                # Progress bar
                hours = status['current_duration'] / 3600
                if hours >= 1:
                    progress_bars = min(int(hours), 8)
                    progress = "█" * progress_bars + "░" * (8 - progress_bars)
                    embed.add_field(
                        name="⏱️ Session Progress",
                        value=f"`{progress}` {hours:.1f}h",
                        inline=False
                    )
                
                embed.set_footer(text="Use /clockout when finished")
                
            else:
                # Not clocked in
                if status['total_time'] > 0:
                    embed = discord.Embed(
                        title="📊 Time Tracking Summary",
                        color=discord.Color.green()
                    )
                    
                    total_hours = status['total_time'] / 3600
                    embed.add_field(
                        name="⏱️ Total Time Tracked",
                        value=f"**{status['total_time_formatted']}** ({total_hours:.1f} hours)",
                        inline=False
                    )
                    
                    # Categories
                    if status['categories']:
                        category_text = []
                        sorted_categories = sorted(
                            status['categories'].items(), 
                            key=lambda x: x[1]['percentage'], 
                            reverse=True
                        )
                        
                        for category, data in sorted_categories[:8]:
                            percentage = data['percentage']
                            time_str = data['time']
                            bar_length = min(int(percentage / 10), 10)
                            bar = "█" * bar_length + "░" * (10 - bar_length)
                            category_text.append(f"`{bar}` **{category}**: {time_str} ({percentage:.1f}%)")
                        
                        if category_text:
                            embed.add_field(
                                name="📈 Category Breakdown",
                                value="\n".join(category_text),
                                inline=False
                            )
                    
                    # Recent activity
                    recent_session = status.get('recent_session')
                    if recent_session:
                        embed.add_field(
                            name="🕐 Last Session",
                            value=f"**{recent_session['category']}** for {recent_session['duration']}\n"
                                  f"*{recent_session['hours_since']:.1f} hours ago*",
                            inline=True
                        )
                    
                    # Quick stats
                    summary = status.get('summary', {})
                    if summary:
                        summary_text = []
                        if summary.get('total_sessions'):
                            summary_text.append(f"📅 **{summary['total_sessions']}** sessions")
                        if summary.get('estimated_daily_avg'):
                            summary_text.append(f"📊 **{summary['estimated_daily_avg']}h** daily avg")
                        
                        if summary_text:
                            embed.add_field(
                                name="📋 Quick Stats",
                                value="\n".join(summary_text),
                                inline=True
                            )
                        
                        # Achievements
                        insights = summary.get('insights', [])
                        if insights:
                            embed.add_field(
                                name="🌟 Achievements",
                                value="\n".join(insights),
                                inline=False
                            )
                    
                    embed.set_footer(text="Use /clockin <category> to start tracking")
                    
                else:
                    # No time tracked
                    embed = discord.Embed(
                        title="📋 No Time Tracked Yet",
                        description="Ready to start tracking your time?",
                        color=discord.Color.light_grey()
                    )
                    
                    try:
                        categories = await self.tracker.list_categories(interaction.guild.id)
                        if categories:
                            embed.add_field(
                                name="📂 Available Categories",
                                value=", ".join(f"`{cat}`" for cat in sorted(categories)[:8]),
                                inline=False
                            )
                        else:
                            embed.add_field(
                                name="⚙️ Setup Required",
                                value="Ask admins to set up categories: `/admin categories add <name>`",
                                inline=False
                            )
                    except Exception as e:
                        logger.warning(f"Could not get categories: {e}")
                    
                    embed.add_field(
                        name="🚀 Get Started",
                        value="Use `/clockin <category>` to begin",
                        inline=False
                    )
            
            await interaction.followup.send(embed=embed)
            await self._track_command_performance("status", start_time, True)
            
        except Exception as e:
            logger.error(f"Status error: user={interaction.user.id}, error={e}", exc_info=True)
            embed = self._create_generic_error_embed(e)
            await interaction.followup.send(embed=embed)
            await self._track_command_performance("status", start_time, False)


async def setup(bot):
    await bot.add_cog(TimecardCog(bot))
    logger.info("TimecardCog loaded")

async def teardown(bot):
    cog = bot.get_cog("TimecardCog")
    if cog:
        await cog.cog_unload()
    logger.info("TimecardCog unloaded")