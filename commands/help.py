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
    
    async def _handle_list_categories(self, interaction: discord.Interaction):
        """List all categories"""
        categories = await self.tracker.list_categories(interaction.guild.id)
        
        if categories:
            embed = discord.Embed(
                title="📋 Server Categories",
                color=discord.Color.blue()
            )
            
            category_list = "\n".join([f"• `{cat}`" for cat in sorted(categories)])
            embed.add_field(
                name=f"Categories ({len(categories)})",
                value=category_list,
                inline=False
            )
        else:
            embed = discord.Embed(
                title="📋 No Categories",
                description="No categories configured. Use `/config add_category` to add one.",
                color=discord.Color.orange()
            )
        
        await interaction.followup.send(embed=embed)

    async def _handle_add_category(self, interaction: discord.Interaction, category: str):
        """Add a new category"""
        if not category:
            await interaction.followup.send("❌ Please provide a category name!", ephemeral=True)
            return
        
        try:
            await self.tracker.add_category(interaction.guild.id, category)
            
            embed = discord.Embed(
                title="✅ Category Added",
                description=f"Added category: `{category}`",
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed)
            logger.info(f"Category added: {category}, guild={interaction.guild.id}")
            
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to add category: {str(e)}", ephemeral=True)

    async def _handle_remove_category(self, interaction: discord.Interaction, category: str):
        """Remove a category"""
        if not category:
            await interaction.followup.send("❌ Please provide a category name!", ephemeral=True)
            return
        
        # Confirmation view
        view = ConfirmationView()
        embed = discord.Embed(
            title="⚠️ Confirm Category Removal",
            description=f"Are you sure you want to remove the category `{category}`?\n\n**This will delete all user data for this category!**",
            color=discord.Color.orange()
        )
        
        await interaction.followup.send(embed=embed, view=view)
        await view.wait()
        
        if view.confirmed:
            try:
                await self.tracker.remove_category(interaction.guild.id, category, force=True)
                
                embed = discord.Embed(
                    title="🗑️ Category Removed",
                    description=f"Removed category: `{category}` and all associated data",
                    color=discord.Color.green()
                )
                await interaction.edit_original_response(embed=embed, view=None)
                logger.info(f"Category removed: {category}, guild={interaction.guild.id}")
                
            except Exception as e:
                await interaction.edit_original_response(
                    content=f"❌ Failed to remove category: {str(e)}", 
                    embed=None, 
                    view=None
                )
        else:
            embed = discord.Embed(
                title="❌ Cancelled",
                description="Category removal cancelled.",
                color=discord.Color.gray()
            )
            await interaction.edit_original_response(embed=embed, view=None)

    # ========================================================================
    # USER MANAGEMENT HANDLERS
    # ========================================================================

    async def _handle_user_stats(self, interaction: discord.Interaction, user: discord.Member):
        """Show detailed user statistics"""
        if not user:
            await interaction.followup.send("❌ Please specify a user!", ephemeral=True)
            return
        
        user_stats = await self.tracker.get_user_times(
            interaction.guild.id, 
            user.id,
            include_metadata=True
        )
        
        embed = discord.Embed(
            title=f"📊 Stats for {user.display_name}",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        embed.set_thumbnail(url=user.display_avatar.url)
        
        # Total time
        total_time = user_stats.get('total', 0)
        embed.add_field(
            name="⏱️ Total Time",
            value=user_stats.get('total_formatted', self.tracker._format_time(total_time)),
            inline=True
        )
        
        # Productivity score
        analytics = user_stats.get('analytics', {})
        if analytics and 'productivity_score' in analytics:
            embed.add_field(
                name="🎯 Productivity Score",
                value=f"{analytics['productivity_score']}/100",
                inline=True
            )
        
        # Streak
        if analytics and 'streak_days' in analytics:
            embed.add_field(
                name="🔥 Streak",
                value=f"{analytics['streak_days']} days",
                inline=True
            )
        
        # Show top categories
        categories = user_stats.get('categories', {})
        if categories:
            sorted_categories = sorted(
                [(cat, data['seconds']) for cat, data in categories.items() if data['seconds'] > 0],
                key=lambda x: x[1],
                reverse=True
            )[:5]
            
            if sorted_categories:
                category_text = "\n".join([
                    f"`{cat}`: {self.tracker._format_time(time)}" 
                    for cat, time in sorted_categories
                ])
                embed.add_field(
                    name="🏆 Top Categories",
                    value=category_text,
                    inline=False
                )
        
        # Check if user is suspended
        permissions = await self._get_server_permissions(interaction.guild.id)
        if user.id in permissions["suspended_users"]:
            embed.add_field(
                name="🚫 Status",
                value="**SUSPENDED** - Cannot use time tracking",
                inline=False
            )
        
        await interaction.followup.send(embed=embed)

    async def _handle_set_user_time(self, interaction: discord.Interaction, user: discord.Member, category: str, value: str):
        """Set user's time for a category"""
        if not user or not category or not value:
            await interaction.followup.send("❌ Please provide user, category, and time value!\nExample: `/config set_user_time user:@john category:work value:2h30m`", ephemeral=True)
            return
        
        try:
            seconds = self._parse_time_string(value)
            await self.tracker.set_user_time(interaction.guild.id, user.id, category, seconds)
            
            embed = discord.Embed(
                title="⏰ Time Set",
                description=f"Set {user.mention}'s time in `{category}` to {self.tracker._format_time(seconds)}",
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed)
            logger.info(f"Time set: user={user.id}, category={category}, seconds={seconds}")
            
        except ValueError as e:
            await interaction.followup.send(f"❌ Invalid time format: {str(e)}\nUse format like: `2h30m`, `90m`, `3600s`", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to set time: {str(e)}", ephemeral=True)

    async def _handle_add_user_time(self, interaction: discord.Interaction, user: discord.Member, category: str, value: str):
        """Add time to user's category"""
        if not user or not category or not value:
            await interaction.followup.send("❌ Please provide user, category, and time value!", ephemeral=True)
            return
        
        try:
            seconds = self._parse_time_string(value)
            result = await self.tracker.add_time(interaction.guild.id, user.id, category, seconds)
            
            if not result.get('success', False):
                await interaction.followup.send(f"❌ Failed to add time: {result.get('message', 'Unknown error')}", ephemeral=True)
                return
            
            user_times = await self.tracker.get_user_times(interaction.guild.id, user.id)
            category_data = user_times.get('categories', {}).get(category, {})
            new_total = category_data.get('seconds', seconds)
            
            embed = discord.Embed(
                title="➕ Time Added",
                description=f"Added {self.tracker._format_time(seconds)} to {user.mention}'s `{category}`\n**New total:** {self.tracker._format_time(new_total)}",
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed)
            logger.info(f"Time added: user={user.id}, category={category}, seconds={seconds}")
            
        except ValueError as e:
            await interaction.followup.send(f"❌ Invalid time format: {str(e)}", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to add time: {str(e)}", ephemeral=True)

    async def _handle_reset_user(self, interaction: discord.Interaction, user: discord.Member):
        """Reset all user data"""
        if not user:
            await interaction.followup.send("❌ Please specify a user!", ephemeral=True)
            return
        
        # Confirmation
        view = ConfirmationView()
        embed = discord.Embed(
            title="⚠️ Confirm User Reset",
            description=f"Are you sure you want to reset ALL time data for {user.mention}?\n\n**This action cannot be undone!**",
            color=discord.Color.orange()
        )
        
        await interaction.followup.send(embed=embed, view=view)
        await view.wait()
        
        if view.confirmed:
            try:
                deleted = await self.tracker.delete_user(interaction.guild.id, user.id)
                
                if deleted:
                    embed = discord.Embed(
                        title="🔄 User Reset",
                        description=f"Reset all time data for {user.mention}",
                        color=discord.Color.green()
                    )
                else:
                    embed = discord.Embed(
                        title="ℹ️ No Data",
                        description=f"{user.mention} had no time data to reset",
                        color=discord.Color.blue()
                    )
                
                await interaction.edit_original_response(embed=embed, view=None)
                logger.info(f"User reset: user={user.id}, guild={interaction.guild.id}")
                
            except Exception as e:
                await interaction.edit_original_response(
                    content=f"❌ Failed to reset user: {str(e)}", 
                    embed=None, 
                    view=None
                )

    # ========================================================================
    # PERMISSION HANDLERS
    # ========================================================================

    async def _handle_suspend_user(self, interaction: discord.Interaction, user: discord.Member):
        """Suspend a user from time tracking"""
        if not user:
            await interaction.followup.send("❌ Please specify a user!", ephemeral=True)
            return
        
        permissions = await self._get_server_permissions(interaction.guild.id)
        
        if user.id in permissions["suspended_users"]:
            await interaction.followup.send(f"❌ {user.mention} is already suspended!", ephemeral=True)
            return
        
        permissions["suspended_users"].append(user.id)
        await self._save_server_permissions(interaction.guild.id, permissions)
        
        try:
            await self.clock.clock_out(interaction.guild.id, user.id)
        except:
            pass
        
        embed = discord.Embed(
            title="🚫 User Suspended",
            description=f"{user.mention} has been suspended from time tracking",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed)
        logger.info(f"User suspended: user={user.id}, guild={interaction.guild.id}")

    async def _handle_unsuspend_user(self, interaction: discord.Interaction, user: discord.Member):
        """Unsuspend a user"""
        if not user:
            await interaction.followup.send("❌ Please specify a user!", ephemeral=True)
            return
        
        permissions = await self._get_server_permissions(interaction.guild.id)
        
        if user.id not in permissions["suspended_users"]:
            await interaction.followup.send(f"❌ {user.mention} is not suspended!", ephemeral=True)
            return
        
        permissions["suspended_users"].remove(user.id)
        await self._save_server_permissions(interaction.guild.id, permissions)
        
        embed = discord.Embed(
            title="✅ User Unsuspended",
            description=f"{user.mention} can now use time tracking again",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed)
        logger.info(f"User unsuspended: user={user.id}, guild={interaction.guild.id}")

    async def _handle_set_role(self, interaction: discord.Interaction, role: discord.Role):
        """Set required role for time tracking"""
        if not role:
            await interaction.followup.send("❌ Please specify a role!", ephemeral=True)
            return
        
        permissions = await self._get_server_permissions(interaction.guild.id)
        
        if role.id in permissions["required_roles"]:
            await interaction.followup.send(f"❌ {role.mention} is already a required role!", ephemeral=True)
            return
        
        permissions["required_roles"].append(role.id)
        await self._save_server_permissions(interaction.guild.id, permissions)
        
        embed = discord.Embed(
            title="🔒 Required Role Set",
            description=f"Users now need the {role.mention} role to use time tracking",
            color=discord.Color.blue()
        )
        await interaction.followup.send(embed=embed)
        logger.info(f"Required role set: role={role.id}, guild={interaction.guild.id}")

    async def _handle_remove_role(self, interaction: discord.Interaction, role: discord.Role):
        """Remove required role"""
        if not role:
            await interaction.followup.send("❌ Please specify a role!", ephemeral=True)
            return
        
        permissions = await self._get_server_permissions(interaction.guild.id)
        
        if role.id not in permissions["required_roles"]:
            await interaction.followup.send(f"❌ {role.mention} is not a required role!", ephemeral=True)
            return
        
        permissions["required_roles"].remove(role.id)
        await self._save_server_permissions(interaction.guild.id, permissions)
        
        embed = discord.Embed(
            title="🔓 Required Role Removed",
            description=f"Removed {role.mention} from required roles",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed)

    async def _handle_list_suspended(self, interaction: discord.Interaction):
        """List suspended users"""
        permissions = await self._get_server_permissions(interaction.guild.id)
        
        if not permissions["suspended_users"]:
            embed = discord.Embed(
                title="👥 No Suspended Users",
                description="No users are currently suspended",
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="🚫 Suspended Users",
                color=discord.Color.red()
            )
            
            user_list = []
            for user_id in permissions["suspended_users"]:
                user = self.bot.get_user(user_id)
                if user:
                    user_list.append(f"• {user.mention} ({user.name})")
                else:
                    user_list.append(f"• Unknown User (ID: {user_id})")
            
            embed.add_field(
                name=f"Suspended Users ({len(permissions['suspended_users'])})",
                value="\n".join(user_list),
                inline=False
            )
        
        # Show role requirements
        if permissions["required_roles"]:
            role_list = []
            for role_id in permissions["required_roles"]:
                role = interaction.guild.get_role(role_id)
                if role:
                    role_list.append(f"• {role.mention}")
                else:
                    role_list.append(f"• Deleted Role (ID: {role_id})")
            
            embed.add_field(
                name="🔒 Required Roles",
                value="\n".join(role_list),
                inline=False
            )
        
        await interaction.followup.send(embed=embed)

    # [TRUNCATED - See full file for remaining handlers]
    # Includes: _handle_server_stats, _handle_leaderboard, _handle_export, 
    # _handle_system_status, _handle_toggle_system, _parse_time_string

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