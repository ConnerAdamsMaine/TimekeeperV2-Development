# ============================================================================
# TimekeeperV2 - Premium Time Tracking System
# Copyright © 2025 404ConnerNotFound. All Rights Reserved.
# ============================================================================

import discord 
from discord.ext import commands, tasks
from discord import app_commands
import logging
from typing import Optional, Dict, Any, List
import asyncio
from datetime import datetime
import json
import os

from Utils.timekeeper import get_shared_role_tracker

logger = logging.getLogger(__name__)


class CategorySelectView(discord.ui.View):
    """View with category selection dropdown for clock in"""
    
    def __init__(self, bot, guild_id: int, categories: List[str]):
        super().__init__(timeout=60)
        self.bot = bot
        self.guild_id = guild_id
        
        options = []
        for cat in categories[:25]:
            emoji = {
                "break": "☕",
                "clocked in": "⏰",
                "main": "⏰",
                "work": "⏰",
                "meeting": "📞",
                "call": "📞",
                "development": "💻",
                "coding": "💻",
                "dev": "💻"
            }.get(cat.lower(), "📋")
            
            options.append(
                discord.SelectOption(
                    label=cat.title(),
                    value=cat,
                    description=f"Clock into {cat}",
                    emoji=emoji
                )
            )
        
        self.category_select = discord.ui.Select(
            placeholder="Choose a category to clock into...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="category_select"
        )
        self.category_select.callback = self.category_callback
        self.add_item(self.category_select)
    
    async def category_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        selected_category = self.category_select.values[0]
        tracker, clock = await get_shared_role_tracker(self.bot)
        
        category_lower = selected_category.lower().strip()
        role = "Break" if category_lower == "break" else "Clocked In"
        
        result = await clock.clock_in(
            server_id=self.guild_id,
            user_id=interaction.user.id,
            category=category_lower,
            role=role,
            interaction=interaction,
            metadata={'selected_from_dropdown': True}
        )
        
        if result['success']:
            embed = discord.Embed(
                title="✅ Clocked In",
                description=f"Category: `{result['category']}`\n"
                           f"Started: <t:{int(result['start_time'].timestamp())}:t>",
                color=discord.Color.green()
            )
            logger.info(f"Clock in via dropdown: user={interaction.user.id}, category={category_lower}")
        else:
            embed = discord.Embed(
                title="❌ Error",
                description=result['message'],
                color=discord.Color.red()
            )
            logger.warning(f"Clock in failed via dropdown: user={interaction.user.id}, reason={result['message']}")
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        
        for item in self.children:
            item.disabled = True
        self.stop()


class SharedDashboardView(discord.ui.View):
    """Shared dashboard for all users - no timeout"""
    
    def __init__(self, bot, guild_id: int):
        super().__init__(timeout=None)
        self.bot = bot
        self.guild_id = guild_id
        self.tracker = None
        self.clock = None
        
        self.children[0].custom_id = f"shared_clockin_{guild_id}"
        self.children[1].custom_id = f"shared_clockout_{guild_id}"
        self.children[2].custom_id = f"shared_stats_{guild_id}"
        self.children[3].custom_id = f"shared_server_{guild_id}"
        self.children[4].custom_id = f"shared_whoclocked_{guild_id}"
    
    async def _ensure_initialized(self):
        if not self.tracker or not self.clock:
            self.tracker, self.clock = await get_shared_role_tracker(self.bot)
    
    @discord.ui.button(label="⏰ Clock In", style=discord.ButtonStyle.green, custom_id="clockin_btn")
    async def clock_in_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await self._ensure_initialized()
        
        categories = await self.tracker.list_categories(self.guild_id)
        
        if not categories:
            embed = discord.Embed(
                title="❌ No Categories",
                description="No categories configured. Ask admins to set up categories.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        view = CategorySelectView(self.bot, self.guild_id, categories)
        embed = discord.Embed(
            title="⏰ Select Category",
            description="Choose which category you'd like to clock into:",
            color=discord.Color.blue()
        )
        
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    
    @discord.ui.button(label="🛑 Clock Out", style=discord.ButtonStyle.red, custom_id="clockout_btn")
    async def clock_out_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await self._ensure_initialized()
        
        result = await self.clock.clock_out(self.guild_id, interaction.user.id)
        
        if result['success']:
            embed = discord.Embed(
                title="✅ Clocked Out",
                description=f"Session: {result['session_duration_formatted']}\n"
                           f"Category: `{result['category']}`",
                color=discord.Color.green()
            )
            logger.info(f"Clock out via dashboard: user={interaction.user.id}")
        else:
            embed = discord.Embed(
                title="❌ Error",
                description=result['message'],
                color=discord.Color.red()
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="📊 My Stats", style=discord.ButtonStyle.blurple, custom_id="stats_btn")
    async def stats_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await self._ensure_initialized()
        
        status = await self.clock.get_status(self.guild_id, interaction.user.id)
        
        embed = discord.Embed(
            title=f"📊 Your Stats",
            color=discord.Color.blue()
        )
        
        if status['clocked_in']:
            embed.add_field(
                name="⏰ Currently Clocked In",
                value=f"Category: `{status['category']}`\n"
                      f"Duration: {status['current_duration_formatted']}",
                inline=False
            )
        else:
            embed.add_field(
                name="Status",
                value="Not currently clocked in",
                inline=False
            )
        
        if status.get('total_time', 0) > 0:
            embed.add_field(
                name="⏱️ Total Time",
                value=status['total_time_formatted'],
                inline=True
            )
            
            if status.get('categories'):
                top_cats = sorted(
                    status['categories'].items(),
                    key=lambda x: x[1]['percentage'],
                    reverse=True
                )[:3]
                
                cat_text = "\n".join([f"`{cat}`: {data['time']}" for cat, data in top_cats])
                embed.add_field(
                    name="📈 Top Categories",
                    value=cat_text,
                    inline=True
                )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="🌐 Server Total", style=discord.ButtonStyle.gray, custom_id="server_btn")
    async def server_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await self._ensure_initialized()
        
        server_key = f"server_times:{self.guild_id}"
        server_data = await self.tracker.redis.hgetall(server_key)
        
        embed = discord.Embed(
            title=f"🌐 {interaction.guild.name} - Server Stats",
            color=discord.Color.gold()
        )
        
        if server_data:
            total_seconds = int(server_data.get(b'total', b'0'))
            total_hours = total_seconds / 3600
            
            embed.add_field(
                name="⏱️ Total Time Tracked",
                value=f"{total_hours:.1f} hours",
                inline=True
            )
            
            pattern = f"user_times:{self.guild_id}:*"
            cursor = 0
            user_count = 0
            
            while True:
                cursor, keys = await self.tracker.redis.scan(cursor, match=pattern, count=100)
                user_count += len(keys)
                if cursor == 0:
                    break
            
            embed.add_field(
                name="👥 Active Users",
                value=str(user_count),
                inline=True
            )
            
            categories = {}
            for key, value in server_data.items():
                key_str = key.decode('utf-8')
                if key_str != 'total':
                    categories[key_str] = int(value)
            
            if categories:
                top_cats = sorted(categories.items(), key=lambda x: x[1], reverse=True)[:5]
                cat_text = "\n".join([f"`{cat}`: {val/3600:.1f}h" for cat, val in top_cats])
                embed.add_field(
                    name="📊 Top Categories",
                    value=cat_text,
                    inline=False
                )
        else:
            embed.description = "No time tracked yet"
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="👥 Who's Clocked In", style=discord.ButtonStyle.gray, custom_id="whoclocked_btn")
    async def who_clocked_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await self._ensure_initialized()
        
        pattern = f"active_session:{self.guild_id}:*"
        cursor = 0
        active_sessions = []
        
        while True:
            cursor, keys = await self.tracker.redis.scan(cursor, match=pattern, count=100)
            
            for key in keys:
                session_data = await self.tracker.redis.get(key)
                if session_data:
                    session = json.loads(session_data)
                    active_sessions.append(session)
            
            if cursor == 0:
                break
        
        embed = discord.Embed(
            title="👥 Currently Clocked In",
            color=discord.Color.blue()
        )
        
        if active_sessions:
            session_text = []
            for session in active_sessions[:10]:
                user = self.bot.get_user(session['user_id'])
                username = user.name if user else f"User {session['user_id']}"
                
                start_time = datetime.fromisoformat(session['start_time'])
                duration = int((datetime.now() - start_time).total_seconds())
                hours = duration / 3600
                
                session_text.append(f"**{username}** - `{session['category']}` ({hours:.1f}h)")
            
            embed.description = "\n".join(session_text)
            embed.set_footer(text=f"{len(active_sessions)} user(s) currently clocked in")
        else:
            embed.description = "No one is currently clocked in"
        
        await interaction.followup.send(embed=embed, ephemeral=True)


class PersonalDashboardView(discord.ui.View):
    """Personal ephemeral dashboard for a specific user"""
    
    def __init__(self, bot, guild_id: int, user_id: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild_id = guild_id
        self.user_id = user_id
        self.tracker = None
        self.clock = None
    
    async def _ensure_initialized(self):
        if not self.tracker or not self.clock:
            self.tracker, self.clock = await get_shared_role_tracker(self.bot)
    
    @discord.ui.button(label="⏰ Clock In", style=discord.ButtonStyle.green)
    async def clock_in_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This dashboard is not for you!", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        await self._ensure_initialized()
        
        categories = await self.tracker.list_categories(self.guild_id)
        
        if not categories:
            embed = discord.Embed(
                title="❌ No Categories",
                description="No categories configured.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        view = CategorySelectView(self.bot, self.guild_id, categories)
        embed = discord.Embed(
            title="⏰ Select Category",
            description="Choose which category you'd like to clock into:",
            color=discord.Color.blue()
        )
        
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    
    @discord.ui.button(label="🛑 Clock Out", style=discord.ButtonStyle.red)
    async def clock_out_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This dashboard is not for you!", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        await self._ensure_initialized()
        
        result = await self.clock.clock_out(self.guild_id, self.user_id)
        
        if result['success']:
            embed = discord.Embed(
                title="✅ Clocked Out",
                description=f"Session: {result['session_duration_formatted']}\n"
                           f"Category: `{result['category']}`",
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="❌ Error",
                description=result['message'],
                color=discord.Color.red()
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="📊 My Stats", style=discord.ButtonStyle.blurple)
    async def stats_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This dashboard is not for you!", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        await self._ensure_initialized()
        
        status = await self.clock.get_status(self.guild_id, self.user_id)
        
        embed = discord.Embed(title=f"📊 Your Stats", color=discord.Color.blue())
        
        if status['clocked_in']:
            embed.add_field(
                name="⏰ Currently Clocked In",
                value=f"Category: `{status['category']}`\n"
                      f"Duration: {status['current_duration_formatted']}",
                inline=False
            )
        
        if status.get('total_time', 0) > 0:
            embed.add_field(name="⏱️ Total Time", value=status['total_time_formatted'], inline=True)
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="🌐 Server Total", style=discord.ButtonStyle.gray)
    async def server_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This dashboard is not for you!", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        await self._ensure_initialized()
        
        server_key = f"server_times:{self.guild_id}"
        server_data = await self.tracker.redis.hgetall(server_key)
        
        embed = discord.Embed(
            title=f"🌐 {interaction.guild.name}",
            color=discord.Color.gold()
        )
        
        if server_data:
            total_seconds = int(server_data.get(b'total', b'0'))
            embed.add_field(name="⏱️ Total", value=f"{total_seconds/3600:.1f} hours", inline=True)
        else:
            embed.description = "No time tracked yet"
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="👥 Who's Clocked In", style=discord.ButtonStyle.gray)
    async def who_clocked_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This dashboard is not for you!", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        await self._ensure_initialized()
        
        pattern = f"active_session:{self.guild_id}:*"
        cursor = 0
        active_sessions = []
        
        while True:
            cursor, keys = await self.tracker.redis.scan(cursor, match=pattern, count=100)
            for key in keys:
                session_data = await self.tracker.redis.get(key)
                if session_data:
                    active_sessions.append(json.loads(session_data))
            if cursor == 0:
                break
        
        embed = discord.Embed(title="👥 Currently Clocked In", color=discord.Color.blue())
        
        if active_sessions:
            session_text = []
            for session in active_sessions[:10]:
                user = self.bot.get_user(session['user_id'])
                username = user.name if user else f"User {session['user_id']}"
                session_text.append(f"**{username}** - `{session['category']}`")
            embed.description = "\n".join(session_text)
        else:
            embed.description = "No one is clocked in"
        
        await interaction.followup.send(embed=embed, ephemeral=True)


class DashboardManager:
    """Manages persistent shared dashboards using Redis"""
    
    def __init__(self, bot):
        self.bot = bot
        self.tracker = None
        self.clock = None
        self.redis = None
        
        logger.info("DashboardManager initialized")
    
    async def _ensure_redis(self):
        if not self.redis:
            if not self.tracker:
                self.tracker, self.clock = await get_shared_role_tracker(self.bot)
            self.redis = self.tracker.redis
    
    async def load_dashboards(self):
        try:
            await self._ensure_redis()
            
            pattern = "dashboard:*"
            cursor = 0
            dashboard_count = 0
            
            while True:
                cursor, keys = await self.redis.scan(cursor, match=pattern, count=100)
                dashboard_count += len(keys)
                if cursor == 0:
                    break
            
            logger.info(f"Loaded {dashboard_count} dashboards from Redis")
            
        except Exception as e:
            logger.error(f"Failed to load dashboards: {e}")
    
    async def add_dashboard(self, guild_id: int, channel_id: int, message_id: int):
        try:
            await self._ensure_redis()
            
            key = f"dashboard:{guild_id}:{channel_id}"
            dashboard_data = {
                'guild_id': guild_id,
                'channel_id': channel_id,
                'message_id': message_id,
                'created_at': datetime.now().isoformat(),
                'last_updated': datetime.now().isoformat()
            }
            
            await self.redis.set(key, json.dumps(dashboard_data))
            logger.info(f"Dashboard added: guild={guild_id}, channel={channel_id}")
            
        except Exception as e:
            logger.error(f"Failed to add dashboard: {e}")
    
    async def remove_dashboard(self, guild_id: int, channel_id: int):
        try:
            await self._ensure_redis()
            key = f"dashboard:{guild_id}:{channel_id}"
            await self.redis.delete(key)
            logger.info(f"Dashboard removed: guild={guild_id}, channel={channel_id}")
        except Exception as e:
            logger.error(f"Failed to remove dashboard: {e}")
    
    async def get_dashboard(self, guild_id: int, channel_id: int) -> Optional[Dict[str, Any]]:
        try:
            await self._ensure_redis()
            key = f"dashboard:{guild_id}:{channel_id}"
            data = await self.redis.get(key)
            
            if data:
                if isinstance(data, bytes):
                    data = data.decode('utf-8')
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get dashboard: {e}")
            return None
    
    async def get_guild_dashboards(self, guild_id: int) -> List[Dict[str, Any]]:
        try:
            await self._ensure_redis()
            pattern = f"dashboard:{guild_id}:*"
            cursor = 0
            dashboards = []
            
            while True:
                cursor, keys = await self.redis.scan(cursor, match=pattern, count=100)
                for key in keys:
                    data = await self.redis.get(key)
                    if data:
                        if isinstance(data, bytes):
                            data = data.decode('utf-8')
                        dashboards.append(json.loads(data))
                if cursor == 0:
                    break
            
            return dashboards
        except Exception as e:
            logger.error(f"Failed to get guild dashboards: {e}")
            return []
    
    async def update_dashboard_timestamp(self, guild_id: int, channel_id: int):
        try:
            await self._ensure_redis()
            dashboard = await self.get_dashboard(guild_id, channel_id)
            if dashboard:
                dashboard['last_updated'] = datetime.now().isoformat()
                key = f"dashboard:{guild_id}:{channel_id}"
                await self.redis.set(key, json.dumps(dashboard))
        except Exception as e:
            logger.error(f"Failed to update dashboard timestamp: {e}")
    
    async def update_dashboard_embed(self, dashboard_info: Dict[str, Any]) -> discord.Embed:
        if not self.tracker or not self.clock:
            self.tracker, self.clock = await get_shared_role_tracker(self.bot)
        
        guild_id = dashboard_info['guild_id']
        guild = self.bot.get_guild(guild_id)
        guild_name = guild.name if guild else f"Guild {guild_id}"
        
        embed = discord.Embed(
            title=f"⏰ {guild_name} - Time Tracking",
            description="Use buttons below to interact.\n*This dashboard is shared.*",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        try:
            pattern = f"active_session:{guild_id}:*"
            cursor = 0
            active_count = 0
            
            while True:
                cursor, keys = await self.tracker.redis.scan(cursor, match=pattern, count=100)
                active_count += len(keys)
                if cursor == 0:
                    break
            
            server_key = f"server_times:{guild_id}"
            server_data = await self.tracker.redis.hgetall(server_key)
            
            if server_data:
                total_seconds = int(server_data.get(b'total', b'0'))
                total_hours = total_seconds / 3600
                
                embed.add_field(
                    name="🌐 Server Stats",
                    value=f"**Total:** {total_hours:.1f}h\n**Active:** {active_count} user(s)",
                    inline=False
                )
                
                categories = {k.decode('utf-8'): int(v) for k, v in server_data.items() if k.decode('utf-8') != 'total'}
                if categories:
                    top_cats = sorted(categories.items(), key=lambda x: x[1], reverse=True)[:3]
                    cat_text = "\n".join([f"`{cat}`: {val/3600:.1f}h" for cat, val in top_cats])
                    embed.add_field(name="📊 Top Categories", value=cat_text, inline=False)
        except Exception as e:
            logger.error(f"Failed to build dashboard embed: {e}")
            embed.add_field(name="📊 Stats", value="Unable to fetch stats", inline=False)
        
        embed.set_footer(text="Shared Dashboard • Auto-updates every 30s")
        return embed
    
    async def update_all_dashboards(self):
        try:
            await self._ensure_redis()
            pattern = "dashboard:*"
            cursor = 0
            
            while True:
                cursor, keys = await self.redis.scan(cursor, match=pattern, count=100)
                
                for key in keys:
                    try:
                        if isinstance(key, bytes):
                            key = key.decode('utf-8')
                        
                        data = await self.redis.get(key)
                        if not data:
                            continue
                        
                        if isinstance(data, bytes):
                            data = data.decode('utf-8')
                        
                        dashboard_info = json.loads(data)
                        
                        channel = self.bot.get_channel(dashboard_info['channel_id'])
                        if not channel:
                            await self.remove_dashboard(dashboard_info['guild_id'], dashboard_info['channel_id'])
                            continue
                        
                        try:
                            message = await channel.fetch_message(dashboard_info['message_id'])
                        except discord.NotFound:
                            await self.remove_dashboard(dashboard_info['guild_id'], dashboard_info['channel_id'])
                            continue
                        
                        embed = await self.update_dashboard_embed(dashboard_info)
                        view = SharedDashboardView(self.bot, dashboard_info['guild_id'])
                        
                        await message.edit(embed=embed, view=view)
                        await self.update_dashboard_timestamp(dashboard_info['guild_id'], dashboard_info['channel_id'])
                        
                    except Exception as e:
                        logger.error(f"Failed to update dashboard: {e}")
                
                if cursor == 0:
                    break
                    
        except Exception as e:
            logger.error(f"Failed to update all dashboards: {e}")


class DashboardCog(commands.Cog):
    """Interactive persistent dashboard for time tracking"""
    
    def __init__(self, bot):
        self.bot = bot
        self.tracker = None
        self.clock = None
        self.dashboard_manager = DashboardManager(bot)
        logger.info("DashboardCog initialized")
    
    async def cog_load(self):
        try:
            self.tracker, self.clock = await get_shared_role_tracker(self.bot)
            self.dashboard_manager.tracker = self.tracker
            self.dashboard_manager.clock = self.clock
            
            await self.dashboard_manager.load_dashboards()
            self.dashboard_update_loop.start()
            
            logger.info("DashboardCog loaded and update loop started")
        except Exception as e:
            logger.error(f"Failed to load DashboardCog: {e}", exc_info=True)
    
    async def _ensure_initialized(self):
        if not self.tracker or not self.clock:
            self.tracker, self.clock = await get_shared_role_tracker(self.bot)
    
    async def cog_unload(self):
        self.dashboard_update_loop.cancel()
        logger.info("DashboardCog unloaded")
    
    @tasks.loop(seconds=30)
    async def dashboard_update_loop(self):
        try:
            await self.dashboard_manager.update_all_dashboards()
        except Exception as e:
            logger.error(f"Dashboard update loop error: {e}")
    
    @dashboard_update_loop.before_loop
    async def before_dashboard_update(self):
        await self.bot.wait_until_ready()
    
    @app_commands.command(name="dashboard", description="📊 Open interactive dashboard")
    @app_commands.describe(personal="Make this personal (default: False)")
    async def dashboard(self, interaction: discord.Interaction, personal: bool = False):
        await interaction.response.defer(ephemeral=personal)
        
        try:
            await self._ensure_initialized()
            
            if personal:
                status = await self.clock.get_status(interaction.guild.id, interaction.user.id)
                
                embed = discord.Embed(
                    title=f"⏰ Personal Dashboard",
                    description="Your personal dashboard (only you can see this).",
                    color=discord.Color.purple()
                )
                
                if status['clocked_in']:
                    embed.add_field(
                        name="📊 Status",
                        value=f"⏰ **Clocked In** to `{status['category']}`\n"
                              f"Duration: {status['current_duration_formatted']}",
                        inline=False
                    )
                else:
                    embed.add_field(name="📊 Status", value="✅ Not clocked in", inline=False)
                
                if status.get('total_time', 0) > 0:
                    embed.add_field(name="⏱️ Total", value=status['total_time_formatted'], inline=True)
                
                embed.set_footer(text="Personal Dashboard • Expires after 5 minutes")
                
                view = PersonalDashboardView(self.bot, interaction.guild.id, interaction.user.id)
                await interaction.followup.send(embed=embed, view=view, ephemeral=True)
                logger.info(f"Personal dashboard created: user={interaction.user.id}")
                
            else:
                # Shared dashboard
                existing = await self.dashboard_manager.get_dashboard(interaction.guild.id, interaction.channel.id)
                if existing:
                    try:
                        channel = self.bot.get_channel(existing['channel_id'])
                        if channel:
                            message = await channel.fetch_message(existing['message_id'])
                            
                            embed = discord.Embed(
                                title="📊 Dashboard Exists",
                                description=f"This channel already has a dashboard.",
                                color=discord.Color.blue()
                            )
                            embed.add_field(name="🔗 Jump", value=f"[Click here]({message.jump_url})", inline=False)
                            await interaction.followup.send(embed=embed, ephemeral=True)
                            return
                    except discord.NotFound:
                        await self.dashboard_manager.remove_dashboard(interaction.guild.id, interaction.channel.id)
                
                embed = await self.dashboard_manager.update_dashboard_embed({
                    'guild_id': interaction.guild.id,
                    'channel_id': interaction.channel.id,
                    'message_id': 0
                })
                
                view = SharedDashboardView(self.bot, interaction.guild.id)
                message = await interaction.followup.send(embed=embed, view=view)
                
                await self.dashboard_manager.add_dashboard(
                    interaction.guild.id,
                    interaction.channel.id,
                    message.id
                )
                
                logger.info(f"Shared dashboard created: guild={interaction.guild.id}, channel={interaction.channel.id}")
            
        except Exception as e:
            logger.error(f"Dashboard command error: {e}", exc_info=True)
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to create dashboard: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="dashboard-remove", description="🗑️ Remove dashboard (Admin only)")
    async def dashboard_remove(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            if not interaction.user.guild_permissions.administrator:
                embed = discord.Embed(
                    title="🔒 Admin Only",
                    description="Only administrators can remove dashboards.",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            dashboard = await self.dashboard_manager.get_dashboard(interaction.guild.id, interaction.channel.id)
            
            if not dashboard:
                embed = discord.Embed(
                    title="ℹ️ No Dashboard",
                    description="No dashboard in this channel.",
                    color=discord.Color.blue()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            try:
                channel = self.bot.get_channel(dashboard['channel_id'])
                if channel:
                    message = await channel.fetch_message(dashboard['message_id'])
                    await message.delete()
            except:
                pass
            
            await self.dashboard_manager.remove_dashboard(interaction.guild.id, interaction.channel.id)
            
            embed = discord.Embed(
                title="✅ Dashboard Removed",
                description="Dashboard removed from this channel.",
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info(f"Dashboard removed: guild={interaction.guild.id}, channel={interaction.channel.id}")
            
        except Exception as e:
            logger.error(f"Dashboard remove error: {e}", exc_info=True)
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to remove dashboard: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="forceclockout", description="👑 Force clock out (Admin only)")
    @app_commands.describe(user="User to force clock out", reason="Reason")
    async def force_clockout(self, interaction: discord.Interaction, 
                            user: Optional[discord.Member] = None,
                            reason: Optional[str] = None):
        await interaction.response.defer()
        
        try:
            if not interaction.user.guild_permissions.administrator:
                embed = discord.Embed(
                    title="🔒 Admin Only",
                    description="Only administrators can force clock out.",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed)
                return
            
            if not user:
                embed = discord.Embed(
                    title="❌ Missing User",
                    description="Please specify a user to force clock out.",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed)
                return
            
            await self.cog_load()
            result = await self.clock.clock_out(interaction.guild.id, user.id, force=True)
            
            if result['success']:
                embed = discord.Embed(
                    title="✅ Force Clocked Out",
                    description=f"Force clocked out {user.mention}",
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="📊 Session",
                    value=f"**Category:** `{result['category']}`\n"
                          f"**Duration:** {result['session_duration_formatted']}",
                    inline=False
                )
                if reason:
                    embed.add_field(name="📝 Reason", value=reason, inline=False)
                
                logger.info(f"Force clockout: user={user.id}, admin={interaction.user.id}, reason={reason}")
            else:
                embed = discord.Embed(
                    title="❌ Failed",
                    description=result['message'],
                    color=discord.Color.red()
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Force clockout error: {e}", exc_info=True)
            embed = discord.Embed(
                title="❌ Error",
                description=f"An error occurred: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="whoclocked", description="👥 See who's currently clocked in")
    async def who_clocked(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        try:
            await self.cog_load()
            
            pattern = f"active_session:{interaction.guild.id}:*"
            cursor = 0
            active_sessions = []
            
            while True:
                cursor, keys = await self.tracker.redis.scan(cursor, match=pattern, count=100)
                for key in keys:
                    session_data = await self.tracker.redis.get(key)
                    if session_data:
                        active_sessions.append(json.loads(session_data))
                if cursor == 0:
                    break
            
            embed = discord.Embed(
                title="👥 Currently Clocked In",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            if active_sessions:
                active_sessions.sort(
                    key=lambda s: datetime.now() - datetime.fromisoformat(s['start_time']),
                    reverse=True
                )
                
                session_text = []
                for session in active_sessions[:25]:
                    user = self.bot.get_user(session['user_id'])
                    username = user.mention if user else f"User {session['user_id']}"
                    
                    start_time = datetime.fromisoformat(session['start_time'])
                    duration = int((datetime.now() - start_time).total_seconds())
                    hours = duration / 3600
                    duration_str = f"{hours:.1f}h" if hours >= 1 else f"{duration/60:.0f}m"
                    
                    session_text.append(f"• {username} - `{session['category']}` ({duration_str})")
                
                chunk_size = 10
                for i in range(0, len(session_text), chunk_size):
                    chunk = session_text[i:i + chunk_size]
                    field_name = "Active Sessions" if i == 0 else "More Sessions"
                    embed.add_field(name=field_name, value="\n".join(chunk), inline=False)
                
                embed.set_footer(text=f"{len(active_sessions)} user(s) clocked in")
            else:
                embed.description = "No one is currently clocked in"
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Whoclocked error: {e}", exc_info=True)
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to fetch: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(DashboardCog(bot))
    logger.info("DashboardCog loaded")