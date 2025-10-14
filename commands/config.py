# ============================================================================
# TimekeeperV2 - Premium Time Tracking System
# Copyright © 2025 404ConnerNotFound. All Rights Reserved.
# ============================================================================

import discord 
from discord import app_commands
from discord.ext import commands
from typing import Optional, List, Dict, Any
import logging
import asyncio
import json
from datetime import datetime

from Utils.timekeeper import get_shared_tracker

logger = logging.getLogger("commands.config")
logger.setLevel(logging.INFO)

class TimeTrackerConfig(commands.Cog):
    """Configuration and administration for the time tracking system"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.tracker = None
        self.clock = None
        self._initialization_lock = asyncio.Lock()
        self._initialized = False

    async def _ensure_initialized(self):
        """Ensure the tracker and clock are initialized"""
        if self._initialized:
            return
        
        async with self._initialization_lock:
            if self._initialized:
                return
            
            try:
                self.tracker, self.clock = await get_shared_tracker()
                self._initialized = True
                logger.info("Config system initialized")
            except Exception as e:
                logger.error(f"Init failed: {e}")
                raise

    def _check_admin_permissions(self, interaction: discord.Interaction) -> bool:
        """Check if user has admin permissions"""
        return (interaction.user.guild_permissions.manage_guild or 
                interaction.user.guild_permissions.administrator)

    async def _get_server_permissions(self, server_id: int) -> Dict[str, Any]:
        """Get server permission settings"""
        await self._ensure_initialized()
        perms_key = f"permissions:{server_id}"
        perms_data = await self.tracker.redis.hgetall(perms_key)
        
        return {
            "required_roles": json.loads(perms_data.get("required_roles", "[]")),
            "suspended_users": json.loads(perms_data.get("suspended_users", "[]")),
            "admin_roles": json.loads(perms_data.get("admin_roles", "[]")),
            "enabled": perms_data.get("enabled", "true") == "true"
        }

    async def _save_server_permissions(self, server_id: int, permissions: Dict[str, Any]):
        """Save server permission settings"""
        perms_key = f"permissions:{server_id}"
        perms_data = {
            "required_roles": json.dumps(permissions.get("required_roles", [])),
            "suspended_users": json.dumps(permissions.get("suspended_users", [])),
            "admin_roles": json.dumps(permissions.get("admin_roles", [])),
            "enabled": str(permissions.get("enabled", True)).lower(),
            "updated_at": datetime.now().isoformat()
        }
        await self.tracker.redis.hset(perms_key, mapping=perms_data)

    async def check_user_permissions(self, interaction: discord.Interaction) -> tuple[bool, str]:
        """Check if user can use time tracking commands. Returns (can_use, reason_if_not)"""
        await self._ensure_initialized()
        
        permissions = await self._get_server_permissions(interaction.guild.id)
        
        # Check if system is enabled
        if not permissions["enabled"]:
            return False, "Time tracking is currently disabled on this server."
        
        # Check if user is suspended
        if interaction.user.id in permissions["suspended_users"]:
            return False, "You are suspended from using time tracking commands."
        
        # Check role requirements
        if permissions["required_roles"]:
            user_role_ids = [role.id for role in interaction.user.roles]
            if not any(role_id in user_role_ids for role_id in permissions["required_roles"]):
                role_names = []
                for role_id in permissions["required_roles"]:
                    role = interaction.guild.get_role(role_id)
                    if role:
                        role_names.append(role.name)
                return False, f"You need one of these roles: {', '.join(role_names)}"
        
        return True, ""
    
    # ========================================================================
    # DEV MANAGEMENT
    # ========================================================================    
    @app_commands.command(name="deques", description="Show all deque objects in timekeeper.py")
    async def deques(self, interaction: discord.Interaction):
        """Show all deque objects in timekeeper.py"""
        if interaction.user.id != 473622504586477589:
            await interaction.response.send_message("❌ You do not have permission to use this command.", ephemeral=True)
            return
        
        await self._ensure_initialized()
        await interaction.response.defer()
        
        try:
            import inspect
            import collections
            from Utils import timekeeper
            
            deque_info = []
            for name, obj in inspect.getmembers(timekeeper):
                if isinstance(obj, collections.deque):
                    deque_info.append(f"• `{name}`: {len(obj)} items")
            
            if not deque_info:
                message = "No deque objects found in timekeeper.py."
            else:
                message = "Deque objects in timekeeper.py:\n" + "\n".join(deque_info)
            
            await interaction.followup.send(message, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(f"❌ Error retrieving deque info: {str(e)}", ephemeral=True)
            logger.error(f"Deque cmd error: {e}", exc_info=True)

    # ========================================================================
    # CATEGORY MANAGEMENT
    # ========================================================================
    @app_commands.command(name="config", description="Configure time tracking settings (Admin only)")
    @app_commands.describe(
        action="Configuration action to perform",
        category="Category name (for category actions)",
        user="User to manage (for user actions)",
        role="Role to manage (for permission actions)",
        value="Value to set"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="📋 List Categories", value="list_categories"),
        app_commands.Choice(name="➕ Add Category", value="add_category"),
        app_commands.Choice(name="🗑️ Remove Category", value="remove_category"),
        app_commands.Choice(name="👤 User Stats", value="user_stats"),
        app_commands.Choice(name="⏰ Set User Time", value="set_user_time"),
        app_commands.Choice(name="➕ Add User Time", value="add_user_time"),
        app_commands.Choice(name="🔄 Reset User", value="reset_user"),
        app_commands.Choice(name="🚫 Suspend User", value="suspend_user"),
        app_commands.Choice(name="✅ Unsuspend User", value="unsuspend_user"),
        app_commands.Choice(name="🔒 Set Required Role", value="set_role"),
        app_commands.Choice(name="🔓 Remove Required Role", value="remove_role"),
        app_commands.Choice(name="👥 List Suspended", value="list_suspended"),
        app_commands.Choice(name="📊 Server Stats", value="server_stats"),
        app_commands.Choice(name="🏆 Leaderboard", value="leaderboard"),
        app_commands.Choice(name="📥 Export Data", value="export"),
        app_commands.Choice(name="⚙️ System Status", value="system_status"),
        app_commands.Choice(name="🔴 Disable System", value="disable_system"),
        app_commands.Choice(name="🟢 Enable System", value="enable_system"),
    ])
    async def config(
        self,
        interaction: discord.Interaction,
        action: str,
        category: Optional[str] = None,
        user: Optional[discord.Member] = None,
        role: Optional[discord.Role] = None,
        value: Optional[str] = None
    ):
        """Main configuration command"""
        
        # Check admin permissions
        if not self._check_admin_permissions(interaction):
            embed = discord.Embed(
                title="❌ Permission Denied",
                description="You need 'Manage Server' permission to use this command.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await self._ensure_initialized()
        await interaction.response.defer()

        try:
            if action == "list_categories":
                await self._handle_list_categories(interaction)
            elif action == "add_category":
                await self._handle_add_category(interaction, category)
            elif action == "remove_category":
                await self._handle_remove_category(interaction, category)
            elif action == "user_stats":
                await self._handle_user_stats(interaction, user)
            elif action == "set_user_time":
                await self._handle_set_user_time(interaction, user, category, value)
            elif action == "add_user_time":
                await self._handle_add_user_time(interaction, user, category, value)
            elif action == "reset_user":
                await self._handle_reset_user(interaction, user)
            elif action == "suspend_user":
                await self._handle_suspend_user(interaction, user)
            elif action == "unsuspend_user":
                await self._handle_unsuspend_user(interaction, user)
            elif action == "set_role":
                await self._handle_set_role(interaction, role)
            elif action == "remove_role":
                await self._handle_remove_role(interaction, role)
            elif action == "list_suspended":
                await self._handle_list_suspended(interaction)
            elif action == "server_stats":
                await self._handle_server_stats(interaction)
            elif action == "leaderboard":
                await self._handle_leaderboard(interaction, category)
            elif action == "export":
                await self._handle_export(interaction)
            elif action == "system_status":
                await self._handle_system_status(interaction)
            elif action == "disable_system":
                await self._handle_toggle_system(interaction, False)
            elif action == "enable_system":
                await self._handle_toggle_system(interaction, True)
            else:
                await interaction.followup.send("❌ Unknown action!", ephemeral=True)

        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Configuration Error",
                description=f"An error occurred: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)
            logger.error(f"Config cmd error: {e}", exc_info=True)
    async def _handle_server_stats(self, interaction: discord.Interaction):
        """Show server statistics"""
        stats = await self.tracker.get_server_stats(interaction.guild.id)
        
        embed = discord.Embed(
            title=f"📊 {interaction.guild.name} Statistics",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name="👥 Users",
            value=f"{stats.active_users} active / {stats.total_users} total",
            inline=True
        )
        
        embed.add_field(
            name="⏱️ Total Time",
            value=self.tracker._format_time(stats.total_time),
            inline=True
        )
        
        embed.add_field(
            name="📋 Categories",
            value=str(len(stats.categories)),
            inline=True
        )
        
        embed.add_field(
            name="📈 Daily Average",
            value=self.tracker._format_time(int(stats.daily_average * 86400)),
            inline=True
        )
        
        # Top categories
        if stats.category_totals:
            top_categories = sorted(
                stats.category_totals.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]
            
            category_text = "\n".join([
                f"`{cat}`: {self.tracker._format_time(time)}"
                for cat, time in top_categories if time > 0
            ])
            
            if category_text:
                embed.add_field(
                    name="🔥 Top Categories",
                    value=category_text,
                    inline=False
                )
        
        # System status
        permissions = await self._get_server_permissions(interaction.guild.id)
        status_text = "🟢 Enabled" if permissions["enabled"] else "🔴 Disabled"
        embed.add_field(
            name="⚙️ System Status",
            value=status_text,
            inline=True
        )
        
        await interaction.followup.send(embed=embed)

    async def _handle_leaderboard(self, interaction: discord.Interaction, category: str):
        """Show leaderboard"""
        if category:
            # Category-specific leaderboard
            leaderboard = await self.tracker.get_server_leaderboard(interaction.guild.id, category, 10)
            title = f"🏆 {category.title()} Leaderboard"
        else:
            # Total time leaderboard
            leaderboard = await self.tracker.get_server_leaderboard(interaction.guild.id, None, 10)
            title = "🏆 Total Time Leaderboard"
        
        if not leaderboard:
            embed = discord.Embed(
                title=title,
                description="No data available for leaderboard",
                color=discord.Color.orange()
            )
        else:
            embed = discord.Embed(
                title=title,
                color=discord.Color.gold()
            )
            
            medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
            
            leaderboard_text = []
            for i, entry in enumerate(leaderboard):
                user = self.bot.get_user(entry["user_id"])
                user_name = user.display_name if user else f"User {entry['user_id']}"
                time_str = self.tracker._format_time(entry["time"])
                
                leaderboard_text.append(f"{medals[i]} **{user_name}** - {time_str}")
            
            embed.add_field(
                name="Rankings",
                value="\n".join(leaderboard_text),
                inline=False
            )
        
        await interaction.followup.send(embed=embed)

    async def _handle_export(self, interaction: discord.Interaction):
        """Export server data"""
        try:
            stats = await self.tracker.get_server_stats(interaction.guild.id)
            categories = await self.tracker.get_server_categories(interaction.guild.id)
            
            # Get all user data
            all_users = {}
            server_key = self.tracker._get_server_hash_key(interaction.guild.id)
            all_data = await self.tracker.redis.hgetall(server_key)
            
            for user_id_str, raw_data in all_data.items():
                try:
                    user_data = self.tracker._decompress_data(raw_data)
                    user = self.bot.get_user(int(user_id_str))
                    user_name = user.name if user else f"Unknown_{user_id_str}"
                    
                    all_users[user_name] = user_data
                except:
                    continue
            
            export_data = {
                "server_name": interaction.guild.name,
                "server_id": interaction.guild.id,
                "export_date": datetime.now().isoformat(),
                "stats": {
                    "total_users": stats.total_users,
                    "active_users": stats.active_users,
                    "total_time": stats.total_time,
                    "categories": list(categories),
                    "category_totals": stats.category_totals
                },
                "user_data": all_users
            }
            
            # Create file
            import io
            file_content = json.dumps(export_data, indent=2)
            file_obj = io.StringIO(file_content)
            
            file = discord.File(
                io.BytesIO(file_content.encode()),
                filename=f"timetracker_export_{interaction.guild.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            
            embed = discord.Embed(
                title="📥 Data Export",
                description="Server time tracking data exported successfully",
                color=discord.Color.green()
            )
            
            await interaction.followup.send(embed=embed, file=file)
            logger.info(f"Server export: guild={interaction.guild.id}")
            
        except Exception as e:
            logger.error(f"Export failed: {e}")
            await interaction.followup.send(f"❌ Export failed: {str(e)}", ephemeral=True)

    async def _handle_system_status(self, interaction: discord.Interaction):
        """Show system health status"""
        health = await self.tracker.health_check()
        metrics = await self.tracker.get_metrics()
        
        embed = discord.Embed(
            title="⚙️ System Status",
            color=discord.Color.green() if health["status"] == "healthy" else discord.Color.orange(),
            timestamp=datetime.fromisoformat(health["timestamp"])
        )
        
        embed.add_field(
            name="🔌 Redis Status",
            value=f"{health['components']['redis']['status'].title()}\n{health['components']['redis']['latency_ms']:.2f}ms latency",
            inline=True
        )
        
        embed.add_field(
            name="🔄 Circuit Breaker",
            value=health['components']['circuit_breaker']['status'].title(),
            inline=True
        )
        
        embed.add_field(
            name="💾 Cache Performance",
            value=f"Hit Rate: {metrics['cache_metrics']['category_cache_hit_rate']:.1%}",
            inline=True
        )
        
        pool_stats = health['components']['connection_pool']
        embed.add_field(
            name="🏊 Connection Pool",
            value=f"{pool_stats['in_use_connections']}/{pool_stats['max_connections']} in use\n{pool_stats['utilization_percent']:.1f}% utilization",
            inline=True
        )
        
        embed.add_field(
            name="📦 Batch Queue",
            value=f"{metrics['batch_processor_queue']} pending operations",
            inline=True
        )
        
        embed.add_field(
            name="🔄 Fallback Storage",
            value=f"{metrics['fallback_operations']} operations",
            inline=True
        )
        
        await interaction.followup.send(embed=embed)

    async def _handle_toggle_system(self, interaction: discord.Interaction, enabled: bool):
        """Enable/disable the time tracking system"""
        permissions = await self._get_server_permissions(interaction.guild.id)
        permissions["enabled"] = enabled
        await self._save_server_permissions(interaction.guild.id, permissions)
        
        if not enabled:
            # Force clock out all users
            try:
                results = await self.clock.force_clock_out_all(interaction.guild.id)
                clocked_out_count = len([r for r in results if r.get("success")])
            except:
                clocked_out_count = 0
        else:
            clocked_out_count = 0
        
        status = "🟢 Enabled" if enabled else "🔴 Disabled"
        action = "enabled" if enabled else "disabled"
        
        embed = discord.Embed(
            title=f"⚙️ System {action.title()}",
            description=f"Time tracking system has been {action}",
            color=discord.Color.green() if enabled else discord.Color.red()
        )
        
        embed.add_field(
            name="Status",
            value=status,
            inline=True
        )
        
        if clocked_out_count > 0:
            embed.add_field(
                name="Users Clocked Out",
                value=str(clocked_out_count),
                inline=True
            )
        
        await interaction.followup.send(embed=embed)
        logger.info(f"System {action}: guild={interaction.guild.id}")

    # ========================================================================
    # UTILITY METHODS
    # ========================================================================

    def _parse_time_string(self, time_str: str) -> int:
        """Parse time string like '2h30m' into seconds"""
        import re
        
        time_str = time_str.lower().strip()
        total_seconds = 0
        
        # Match patterns like 2h, 30m, 45s
        patterns = [
            (r'(\d+)h', 3600),  # hours
            (r'(\d+)m', 60),    # minutes
            (r'(\d+)s', 1),     # seconds
        ]
        
        found_match = False
        for pattern, multiplier in patterns:
            matches = re.findall(pattern, time_str)
            for match in matches:
                total_seconds += int(match) * multiplier
                found_match = True
        
        # If no time units found, assume it's seconds
        if not found_match:
            try:
                total_seconds = int(time_str)
                found_match = True
            except ValueError:
                pass
        
        if not found_match:
            raise ValueError("Invalid time format. Use formats like: 2h30m, 90m, 3600s, or just 3600")
        
        if total_seconds < 0:
            raise ValueError("Time cannot be negative")
        
        if total_seconds > 86400 * 7:  # More than a week
            raise ValueError("Time cannot be more than 7 days")
        
        return total_seconds

    async def cog_unload(self):
        """Clean up when cog is unloaded"""
        if self.tracker:
            try:
                await self.tracker.close()
                logger.info("Config system closed")
            except Exception as e:
                logger.error(f"Close error: {e}")


class ConfirmationView(discord.ui.View):
    """Confirmation dialog for destructive operations"""
    
    def __init__(self):
        super().__init__(timeout=60)
        self.confirmed = False
    
    @discord.ui.button(label="✅ Confirm", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = True
        self.stop()
    
    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = False
        self.stop()


async def setup(bot: commands.Bot):
    await bot.add_cog(TimeTrackerConfig(bot))
    logger.info("TimeTrackerConfig loaded")