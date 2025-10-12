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


import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Set, Tuple
from collections import defaultdict
from cachetools import TTLCache

logger = logging.getLogger(__name__)


# ============================================================================
# PERMISSION NODE REGISTRY - Bitmask System
# ============================================================================

class PermissionNodes:
    """
    Registry of all permission nodes with unique bit assignments.
    Each permission is assigned a unique bit position for O(1) checks.
    """
    
    # Administrative permissions (bits 0-9)
    ADMIN_SYSTEM = 1 << 0
    ADMIN_CATEGORIES = 1 << 1
    ADMIN_USERS = 1 << 2
    ADMIN_ROLES = 1 << 3
    ADMIN_SETTINGS = 1 << 4
    ADMIN_LOGS = 1 << 5
    ADMIN_CLEANUP = 1 << 6
    ADMIN_FORCE_CLOCKOUT = 1 << 7
    ADMIN_EXPORT_ALL = 1 << 8
    ADMIN_API = 1 << 9
    
    # Time tracking permissions (bits 10-19)
    TIME_CLOCKIN = 1 << 10
    TIME_CLOCKOUT = 1 << 11
    TIME_VIEW_OWN = 1 << 12
    TIME_VIEW_OTHERS = 1 << 13
    TIME_MODIFY_OWN = 1 << 14
    TIME_MODIFY_OTHERS = 1 << 15
    TIME_DELETE_OWN = 1 << 16
    TIME_DELETE_OTHERS = 1 << 17
    TIME_SET_OWN = 1 << 18
    TIME_SET_OTHERS = 1 << 19
    
    # Category permissions (bits 20-24)
    CATEGORY_CREATE = 1 << 20
    CATEGORY_DELETE = 1 << 21
    CATEGORY_MODIFY = 1 << 22
    CATEGORY_VIEW = 1 << 23
    CATEGORY_ARCHIVE = 1 << 24
    
    # Export permissions (bits 25-27)
    EXPORT_OWN = 1 << 25
    EXPORT_OTHERS = 1 << 26
    EXPORT_SERVER = 1 << 27
    
    # Leaderboard permissions (bits 28-29)
    LEADERBOARD_VIEW = 1 << 28
    LEADERBOARD_MANAGE = 1 << 29
    
    # Dashboard permissions (bits 30-32)
    DASHBOARD_CREATE = 1 << 30
    DASHBOARD_DELETE = 1 << 31
    DASHBOARD_MANAGE = 1 << 32
    
    # Analytics permissions (bits 33-35)
    ANALYTICS_VIEW_OWN = 1 << 33
    ANALYTICS_VIEW_OTHERS = 1 << 34
    ANALYTICS_ADVANCED = 1 << 35
    
    # Support permissions (bits 36-38)
    SUPPORT_CREATE_TICKET = 1 << 36
    SUPPORT_VIEW_TICKETS = 1 << 37
    SUPPORT_MANAGE_TICKETS = 1 << 38
    
    # API permissions (bits 39-41)
    API_GENERATE_KEY = 1 << 39
    API_MANAGE_KEYS = 1 << 40
    API_REVOKE_KEYS = 1 << 41
    
    # Activity log permissions (bits 42-43)
    ACTIVITY_VIEW = 1 << 42
    ACTIVITY_CONFIGURE = 1 << 43
    
    # Config permissions (bits 44-46)
    CONFIG_VIEW = 1 << 44
    CONFIG_MODIFY = 1 << 45
    CONFIG_ADVANCED = 1 << 46
    
    # System permissions (bits 47-49)
    SYSTEM_BYPASS_LIMITS = 1 << 47
    SYSTEM_VIEW_STATUS = 1 << 48
    SYSTEM_DEBUG = 1 << 49
    
    # Reserved for future use (bits 50-63)
    
    @classmethod
    def get_node_map(cls) -> Dict[str, int]:
        """Get mapping of permission names to bitmasks"""
        return {
            # Admin permissions
            "admin.system": cls.ADMIN_SYSTEM,
            "admin.categories": cls.ADMIN_CATEGORIES,
            "admin.users": cls.ADMIN_USERS,
            "admin.roles": cls.ADMIN_ROLES,
            "admin.settings": cls.ADMIN_SETTINGS,
            "admin.logs": cls.ADMIN_LOGS,
            "admin.cleanup": cls.ADMIN_CLEANUP,
            "admin.force_clockout": cls.ADMIN_FORCE_CLOCKOUT,
            "admin.export_all": cls.ADMIN_EXPORT_ALL,
            "admin.api": cls.ADMIN_API,
            
            # Time tracking permissions
            "time.clockin": cls.TIME_CLOCKIN,
            "time.clockout": cls.TIME_CLOCKOUT,
            "time.view.own": cls.TIME_VIEW_OWN,
            "time.view.others": cls.TIME_VIEW_OTHERS,
            "time.modify.own": cls.TIME_MODIFY_OWN,
            "time.modify.others": cls.TIME_MODIFY_OTHERS,
            "time.delete.own": cls.TIME_DELETE_OWN,
            "time.delete.others": cls.TIME_DELETE_OTHERS,
            "time.set.own": cls.TIME_SET_OWN,
            "time.set.others": cls.TIME_SET_OTHERS,
            
            # Category permissions
            "category.create": cls.CATEGORY_CREATE,
            "category.delete": cls.CATEGORY_DELETE,
            "category.modify": cls.CATEGORY_MODIFY,
            "category.view": cls.CATEGORY_VIEW,
            "category.archive": cls.CATEGORY_ARCHIVE,
            
            # Export permissions
            "export.own": cls.EXPORT_OWN,
            "export.others": cls.EXPORT_OTHERS,
            "export.server": cls.EXPORT_SERVER,
            
            # Leaderboard permissions
            "leaderboard.view": cls.LEADERBOARD_VIEW,
            "leaderboard.manage": cls.LEADERBOARD_MANAGE,
            
            # Dashboard permissions
            "dashboard.create": cls.DASHBOARD_CREATE,
            "dashboard.delete": cls.DASHBOARD_DELETE,
            "dashboard.manage": cls.DASHBOARD_MANAGE,
            
            # Analytics permissions
            "analytics.view.own": cls.ANALYTICS_VIEW_OWN,
            "analytics.view.others": cls.ANALYTICS_VIEW_OTHERS,
            "analytics.advanced": cls.ANALYTICS_ADVANCED,
            
            # Support permissions
            "support.create_ticket": cls.SUPPORT_CREATE_TICKET,
            "support.view_tickets": cls.SUPPORT_VIEW_TICKETS,
            "support.manage_tickets": cls.SUPPORT_MANAGE_TICKETS,
            
            # API permissions
            "api.generate_key": cls.API_GENERATE_KEY,
            "api.manage_keys": cls.API_MANAGE_KEYS,
            "api.revoke_keys": cls.API_REVOKE_KEYS,
            
            # Activity log permissions
            "activity.view": cls.ACTIVITY_VIEW,
            "activity.configure": cls.ACTIVITY_CONFIGURE,
            
            # Config permissions
            "config.view": cls.CONFIG_VIEW,
            "config.modify": cls.CONFIG_MODIFY,
            "config.advanced": cls.CONFIG_ADVANCED,
            
            # System permissions
            "system.bypass_limits": cls.SYSTEM_BYPASS_LIMITS,
            "system.view_status": cls.SYSTEM_VIEW_STATUS,
            "system.debug": cls.SYSTEM_DEBUG,
        }
    
    @classmethod
    def resolve_permission(cls, permission: str) -> int:
        """
        Resolve permission string to bitmask.
        Supports wildcards: "admin.*" resolves to all admin permissions.
        """
        node_map = cls.get_node_map()
        
        # Direct match
        if permission in node_map:
            return node_map[permission]
        
        # Wildcard match
        if permission.endswith(".*"):
            prefix = permission[:-2]
            mask = 0
            for perm_name, perm_mask in node_map.items():
                if perm_name.startswith(prefix + "."):
                    mask |= perm_mask
            return mask
        
        # Invalid permission
        logger.warning(f"Unknown permission node: {permission}")
        return 0


class PermissionGroups:
    """Predefined permission groups for common roles"""
    
    # Basic user permissions - can use time tracking
    USER = (
        PermissionNodes.TIME_CLOCKIN |
        PermissionNodes.TIME_CLOCKOUT |
        PermissionNodes.TIME_VIEW_OWN |
        PermissionNodes.TIME_MODIFY_OWN |
        PermissionNodes.CATEGORY_VIEW |
        PermissionNodes.EXPORT_OWN |
        PermissionNodes.LEADERBOARD_VIEW |
        PermissionNodes.DASHBOARD_CREATE |
        PermissionNodes.ANALYTICS_VIEW_OWN |
        PermissionNodes.SUPPORT_CREATE_TICKET |
        PermissionNodes.ACTIVITY_VIEW |
        PermissionNodes.CONFIG_VIEW
    )
    
    # Moderator permissions - can view others
    MODERATOR = USER | (
        PermissionNodes.TIME_VIEW_OTHERS |
        PermissionNodes.EXPORT_OTHERS |
        PermissionNodes.ANALYTICS_VIEW_OTHERS |
        PermissionNodes.SUPPORT_VIEW_TICKETS |
        PermissionNodes.ADMIN_FORCE_CLOCKOUT
    )
    
    # Administrator permissions - full control except system
    ADMINISTRATOR = MODERATOR | (
        PermissionNodes.ADMIN_CATEGORIES |
        PermissionNodes.ADMIN_USERS |
        PermissionNodes.ADMIN_ROLES |
        PermissionNodes.ADMIN_SETTINGS |
        PermissionNodes.ADMIN_LOGS |
        PermissionNodes.ADMIN_CLEANUP |
        PermissionNodes.ADMIN_EXPORT_ALL |
        PermissionNodes.TIME_MODIFY_OTHERS |
        PermissionNodes.TIME_DELETE_OTHERS |
        PermissionNodes.TIME_SET_OTHERS |
        PermissionNodes.CATEGORY_CREATE |
        PermissionNodes.CATEGORY_DELETE |
        PermissionNodes.CATEGORY_MODIFY |
        PermissionNodes.CATEGORY_ARCHIVE |
        PermissionNodes.EXPORT_SERVER |
        PermissionNodes.LEADERBOARD_MANAGE |
        PermissionNodes.DASHBOARD_DELETE |
        PermissionNodes.DASHBOARD_MANAGE |
        PermissionNodes.ANALYTICS_ADVANCED |
        PermissionNodes.SUPPORT_MANAGE_TICKETS |
        PermissionNodes.ACTIVITY_CONFIGURE |
        PermissionNodes.CONFIG_MODIFY |
        PermissionNodes.SYSTEM_VIEW_STATUS
    )
    
    # Owner permissions - everything
    OWNER = 0xFFFFFFFFFFFFFFFF
    
    @classmethod
    def get_group(cls, group_name: str) -> int:
        """Get permission mask for a group"""
        groups = {
            "user": cls.USER,
            "moderator": cls.MODERATOR,
            "admin": cls.ADMINISTRATOR,
            "administrator": cls.ADMINISTRATOR,
            "owner": cls.OWNER,
        }
        return groups.get(group_name.lower(), 0)


# ============================================================================
# PERMISSION CONTEXT - Multi-layer permission system
# ============================================================================

class PermissionContext:
    """
    Represents a permission context with multiple layers:
    - Global: System-wide permissions
    - Guild: Server-specific permissions
    - Session: Temporary session permissions
    """
    
    def __init__(self):
        self.global_allow = 0
        self.global_deny = 0
        self.guild_allow = 0
        self.guild_deny = 0
        self.session_allow = 0
        self.session_deny = 0
        
        # Cache for computed effective mask
        self._effective_mask = None
        self._cache_valid = False
    
    def set_global(self, allow: int = 0, deny: int = 0):
        """Set global permissions"""
        self.global_allow = allow
        self.global_deny = deny
        self._cache_valid = False
    
    def set_guild(self, allow: int = 0, deny: int = 0):
        """Set guild permissions"""
        self.guild_allow = allow
        self.guild_deny = deny
        self._cache_valid = False
    
    def set_session(self, allow: int = 0, deny: int = 0):
        """Set session permissions"""
        self.session_allow = allow
        self.session_deny = deny
        self._cache_valid = False
    
    def compute_effective_mask(self) -> int:
        """
        Compute effective permission mask with layer priority.
        Priority: Session > Guild > Global
        Deny always overrides allow at the same layer.
        """
        if self._cache_valid and self._effective_mask is not None:
            return self._effective_mask
        
        # Start with global permissions
        effective = self.global_allow & ~self.global_deny
        
        # Apply guild layer (overwrites global)
        guild_effective = self.guild_allow & ~self.guild_deny
        effective = (effective & ~(self.guild_allow | self.guild_deny)) | guild_effective
        
        # Apply session layer (overwrites all)
        session_effective = self.session_allow & ~self.session_deny
        effective = (effective & ~(self.session_allow | self.session_deny)) | session_effective
        
        self._effective_mask = effective
        self._cache_valid = True
        
        return effective
    
    def has_permission(self, permission: int) -> bool:
        """Check if permission is granted (O(1) bitwise operation)"""
        effective = self.compute_effective_mask()
        return (effective & permission) == permission
    
    def has_any_permission(self, *permissions: int) -> bool:
        """Check if any of the permissions are granted"""
        effective = self.compute_effective_mask()
        combined = 0
        for perm in permissions:
            combined |= perm
        return (effective & combined) != 0
    
    def has_all_permissions(self, *permissions: int) -> bool:
        """Check if all permissions are granted"""
        effective = self.compute_effective_mask()
        for perm in permissions:
            if (effective & perm) != perm:
                return False
        return True
    
    def grant(self, permission: int, layer: str = "guild"):
        """Grant a permission at specified layer"""
        if layer == "global":
            self.global_allow |= permission
        elif layer == "guild":
            self.guild_allow |= permission
        elif layer == "session":
            self.session_allow |= permission
        self._cache_valid = False
    
    def deny(self, permission: int, layer: str = "guild"):
        """Deny a permission at specified layer"""
        if layer == "global":
            self.global_deny |= permission
        elif layer == "guild":
            self.guild_deny |= permission
        elif layer == "session":
            self.session_deny |= permission
        self._cache_valid = False
    
    def revoke(self, permission: int, layer: str = "guild"):
        """Revoke a permission (remove from both allow and deny)"""
        if layer == "global":
            self.global_allow &= ~permission
            self.global_deny &= ~permission
        elif layer == "guild":
            self.guild_allow &= ~permission
            self.guild_deny &= ~permission
        elif layer == "session":
            self.session_allow &= ~permission
            self.session_deny &= ~permission
        self._cache_valid = False


# ============================================================================
# PERMISSION MIXIN - Integration with Tracker
# ============================================================================

class PermissionMixin:
    """Enhanced permission mixin with bitmask system"""
    
    def __init__(self):
        # Permission cache: (guild_id, user_id) -> PermissionContext
        self.permission_cache = TTLCache(maxsize=10000, ttl=300)  # 5 min cache
        
        # Role permission cache: (guild_id, role_id) -> (allow_mask, deny_mask)
        self.role_permission_cache = TTLCache(maxsize=5000, ttl=600)  # 10 min cache
        
        # Suspended users (legacy compatibility)
        self.suspended_users_cache = TTLCache(maxsize=2000, ttl=300)
    
    def _get_permissions_key(self, guild_id: int, entity_type: str, entity_id: int) -> str:
        """Get Redis key for permissions"""
        return f"permissions:v2:{guild_id}:{entity_type}:{entity_id}"
    
    async def get_role_permissions(self, guild_id: int, role_id: int) -> Tuple[int, int]:
        """
        Get allow/deny masks for a role.
        Returns (allow_mask, deny_mask)
        """
        cache_key = (guild_id, role_id)
        if cache_key in self.role_permission_cache:
            return self.role_permission_cache[cache_key]
        
        try:
            self._ensure_connected()
            perm_key = self._get_permissions_key(guild_id, "role", role_id)
            perm_data = await self.redis.hgetall(perm_key)
            
            allow_mask = int(perm_data.get(b"allow", b"0"))
            deny_mask = int(perm_data.get(b"deny", b"0"))
            
            self.role_permission_cache[cache_key] = (allow_mask, deny_mask)
            return allow_mask, deny_mask
            
        except Exception as e:
            logger.error(f"Error getting role permissions: {e}")
            return 0, 0
    
    async def set_role_permissions(self, guild_id: int, role_id: int, 
                                  allow_mask: int = 0, deny_mask: int = 0):
        """Set permissions for a role"""
        try:
            self._ensure_connected()
            perm_key = self._get_permissions_key(guild_id, "role", role_id)
            
            await self.redis.hset(perm_key, mapping={
                "allow": str(allow_mask),
                "deny": str(deny_mask),
                "updated_at": datetime.now().isoformat()
            })
            
            # Invalidate cache
            cache_key = (guild_id, role_id)
            self.role_permission_cache.pop(cache_key, None)
            
            # Invalidate all user caches for this guild
            self._invalidate_guild_user_cache(guild_id)
            
            logger.info(f"Set role permissions: guild={guild_id}, role={role_id}, allow={allow_mask}, deny={deny_mask}")
            
        except Exception as e:
            logger.error(f"Error setting role permissions: {e}")
    
    async def get_user_permissions(self, guild_id: int, user_id: int) -> Tuple[int, int]:
        """
        Get allow/deny masks for a user.
        Returns (allow_mask, deny_mask)
        """
        try:
            self._ensure_connected()
            perm_key = self._get_permissions_key(guild_id, "user", user_id)
            perm_data = await self.redis.hgetall(perm_key)
            
            allow_mask = int(perm_data.get(b"allow", b"0"))
            deny_mask = int(perm_data.get(b"deny", b"0"))
            
            return allow_mask, deny_mask
            
        except Exception as e:
            logger.error(f"Error getting user permissions: {e}")
            return 0, 0
    
    async def set_user_permissions(self, guild_id: int, user_id: int,
                                  allow_mask: int = 0, deny_mask: int = 0):
        """Set permissions for a user"""
        try:
            self._ensure_connected()
            perm_key = self._get_permissions_key(guild_id, "user", user_id)
            
            await self.redis.hset(perm_key, mapping={
                "allow": str(allow_mask),
                "deny": str(deny_mask),
                "updated_at": datetime.now().isoformat()
            })
            
            # Invalidate cache
            cache_key = (guild_id, user_id)
            self.permission_cache.pop(cache_key, None)
            
            logger.info(f"Set user permissions: guild={guild_id}, user={user_id}, allow={allow_mask}, deny={deny_mask}")
            
        except Exception as e:
            logger.error(f"Error setting user permissions: {e}")
    
    async def compute_user_context(self, guild_id: int, user_id: int, 
                                   role_ids: List[int]) -> PermissionContext:
        """
        Compute complete permission context for a user.
        Combines role permissions with user-specific overrides.
        """
        cache_key = (guild_id, user_id)
        if cache_key in self.permission_cache:
            return self.permission_cache[cache_key]
        
        context = PermissionContext()
        
        try:
            # Get base user permissions
            user_allow, user_deny = await self.get_user_permissions(guild_id, user_id)
            
            # Combine all role permissions
            role_allow = 0
            role_deny = 0
            
            for role_id in role_ids:
                r_allow, r_deny = await self.get_role_permissions(guild_id, role_id)
                role_allow |= r_allow
                role_deny |= r_deny
            
            # Set context layers
            # Global: Default user permissions
            context.set_global(allow=PermissionGroups.USER)
            
            # Guild: Role-based permissions
            context.set_guild(allow=role_allow, deny=role_deny)
            
            # User-specific overrides (highest priority)
            if user_allow or user_deny:
                # User overrides are applied as session layer
                context.set_session(allow=user_allow, deny=user_deny)
            
            # Cache the context
            self.permission_cache[cache_key] = context
            
            return context
            
        except Exception as e:
            logger.error(f"Error computing user context: {e}")
            # Return default context with basic user permissions
            context.set_global(allow=PermissionGroups.USER)
            return context
    
    async def check_permission(self, guild_id: int, user_id: int, 
                             role_ids: List[int], permission: str) -> bool:
        """
        Check if user has a specific permission (O(1) operation).
        
        Args:
            guild_id: Discord guild ID
            user_id: Discord user ID
            role_ids: List of user's role IDs
            permission: Permission string (e.g., "admin.categories")
        
        Returns:
            bool: True if permission is granted
        """
        try:
            # Resolve permission string to bitmask
            perm_mask = PermissionNodes.resolve_permission(permission)
            if perm_mask == 0:
                logger.warning(f"Unknown permission: {permission}")
                return False
            
            # Get user's permission context
            context = await self.compute_user_context(guild_id, user_id, role_ids)
            
            # Check permission
            return context.has_permission(perm_mask)
            
        except Exception as e:
            logger.error(f"Error checking permission: {e}")
            return False
    
    async def check_any_permission(self, guild_id: int, user_id: int,
                                  role_ids: List[int], *permissions: str) -> bool:
        """Check if user has ANY of the specified permissions"""
        try:
            context = await self.compute_user_context(guild_id, user_id, role_ids)
            
            perm_masks = [PermissionNodes.resolve_permission(p) for p in permissions]
            perm_masks = [m for m in perm_masks if m != 0]
            
            if not perm_masks:
                return False
            
            return context.has_any_permission(*perm_masks)
            
        except Exception as e:
            logger.error(f"Error checking any permission: {e}")
            return False
    
    async def check_all_permissions(self, guild_id: int, user_id: int,
                                   role_ids: List[int], *permissions: str) -> bool:
        """Check if user has ALL of the specified permissions"""
        try:
            context = await self.compute_user_context(guild_id, user_id, role_ids)
            
            perm_masks = [PermissionNodes.resolve_permission(p) for p in permissions]
            perm_masks = [m for m in perm_masks if m != 0]
            
            if not perm_masks:
                return False
            
            return context.has_all_permissions(*perm_masks)
            
        except Exception as e:
            logger.error(f"Error checking all permissions: {e}")
            return False
    
    async def grant_permission(self, guild_id: int, entity_type: str, 
                             entity_id: int, permission: str):
        """
        Grant a permission to a user or role.
        
        Args:
            guild_id: Discord guild ID
            entity_type: "user" or "role"
            entity_id: User or role ID
            permission: Permission string or wildcard
        """
        try:
            perm_mask = PermissionNodes.resolve_permission(permission)
            if perm_mask == 0:
                logger.warning(f"Cannot grant unknown permission: {permission}")
                return
            
            if entity_type == "role":
                allow, deny = await self.get_role_permissions(guild_id, entity_id)
                allow |= perm_mask
                deny &= ~perm_mask  # Remove from deny if present
                await self.set_role_permissions(guild_id, entity_id, allow, deny)
            elif entity_type == "user":
                allow, deny = await self.get_user_permissions(guild_id, entity_id)
                allow |= perm_mask
                deny &= ~perm_mask
                await self.set_user_permissions(guild_id, entity_id, allow, deny)
            
            logger.info(f"Granted permission {permission} to {entity_type} {entity_id} in guild {guild_id}")
            
        except Exception as e:
            logger.error(f"Error granting permission: {e}")
    
    async def deny_permission(self, guild_id: int, entity_type: str,
                            entity_id: int, permission: str):
        """Deny a permission (explicit deny overrides allow)"""
        try:
            perm_mask = PermissionNodes.resolve_permission(permission)
            if perm_mask == 0:
                logger.warning(f"Cannot deny unknown permission: {permission}")
                return
            
            if entity_type == "role":
                allow, deny = await self.get_role_permissions(guild_id, entity_id)
                allow &= ~perm_mask  # Remove from allow
                deny |= perm_mask  # Add to deny
                await self.set_role_permissions(guild_id, entity_id, allow, deny)
            elif entity_type == "user":
                allow, deny = await self.get_user_permissions(guild_id, entity_id)
                allow &= ~perm_mask
                deny |= perm_mask
                await self.set_user_permissions(guild_id, entity_id, allow, deny)
            
            logger.info(f"Denied permission {permission} to {entity_type} {entity_id} in guild {guild_id}")
            
        except Exception as e:
            logger.error(f"Error denying permission: {e}")
    
    async def revoke_permission(self, guild_id: int, entity_type: str,
                              entity_id: int, permission: str):
        """Revoke a permission (remove from both allow and deny)"""
        try:
            perm_mask = PermissionNodes.resolve_permission(permission)
            if perm_mask == 0:
                logger.warning(f"Cannot revoke unknown permission: {permission}")
                return
            
            if entity_type == "role":
                allow, deny = await self.get_role_permissions(guild_id, entity_id)
                allow &= ~perm_mask
                deny &= ~perm_mask
                await self.set_role_permissions(guild_id, entity_id, allow, deny)
            elif entity_type == "user":
                allow, deny = await self.get_user_permissions(guild_id, entity_id)
                allow &= ~perm_mask
                deny &= ~perm_mask
                await self.set_user_permissions(guild_id, entity_id, allow, deny)
            
            logger.info(f"Revoked permission {permission} from {entity_type} {entity_id} in guild {guild_id}")
            
        except Exception as e:
            logger.error(f"Error revoking permission: {e}")
    
    async def assign_permission_group(self, guild_id: int, entity_type: str,
                                     entity_id: int, group: str):
        """
        Assign a predefined permission group.
        
        Args:
            guild_id: Discord guild ID
            entity_type: "user" or "role"
            entity_id: User or role ID
            group: Group name ("user", "moderator", "admin", "owner")
        """
        try:
            group_mask = PermissionGroups.get_group(group)
            if group_mask == 0:
                logger.warning(f"Unknown permission group: {group}")
                return
            
            if entity_type == "role":
                await self.set_role_permissions(guild_id, entity_id, allow_mask=group_mask, deny_mask=0)
            elif entity_type == "user":
                await self.set_user_permissions(guild_id, entity_id, allow_mask=group_mask, deny_mask=0)
            
            logger.info(f"Assigned group {group} to {entity_type} {entity_id} in guild {guild_id}")
            
        except Exception as e:
            logger.error(f"Error assigning permission group: {e}")
    
    def _invalidate_guild_user_cache(self, guild_id: int):
        """Invalidate all cached permissions for users in a guild"""
        keys_to_remove = [key for key in self.permission_cache.keys() if key[0] == guild_id]
        for key in keys_to_remove:
            self.permission_cache.pop(key, None)
    
    async def get_user_permission_summary(self, guild_id: int, user_id: int,
                                        role_ids: List[int]) -> Dict[str, Any]:
        """Get detailed permission summary for a user"""
        try:
            context = await self.compute_user_context(guild_id, user_id, role_ids)
            effective_mask = context.compute_effective_mask()
            
            node_map = PermissionNodes.get_node_map()
            
            granted_permissions = []
            denied_permissions = []
            
            for perm_name, perm_mask in node_map.items():
                if (effective_mask & perm_mask) == perm_mask:
                    granted_permissions.append(perm_name)
            
            return {
                "guild_id": guild_id,
                "user_id": user_id,
                "effective_mask": effective_mask,
                "granted_permissions": granted_permissions,
                "permission_count": len(granted_permissions),
                "has_admin": context.has_any_permission(
                    PermissionNodes.ADMIN_SYSTEM,
                    PermissionNodes.ADMIN_CATEGORIES,
                    PermissionNodes.ADMIN_USERS
                ),
                "layers": {
                    "global_allow": context.global_allow,
                    "global_deny": context.global_deny,
                    "guild_allow": context.guild_allow,
                    "guild_deny": context.guild_deny,
                    "session_allow": context.session_allow,
                    "session_deny": context.session_deny
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting permission summary: {e}")
            return {}
    
    # ========================================================================
    # LEGACY COMPATIBILITY METHODS
    # ========================================================================
    
    async def get_server_permissions(self, server_id: int) -> Dict[str, Any]:
        """Legacy method - maintained for backward compatibility"""
        try:
            self._ensure_connected()
            # Check if old format data exists
            old_key = f"permissions:{server_id}"
            old_data = await self.redis.hgetall(old_key)
            
            if old_data:
                # Return old format
                return {
                    "required_roles": json.loads(old_data.get(b"required_roles", b"[]")),
                    "suspended_users": json.loads(old_data.get(b"suspended_users", b"[]")),
                    "admin_roles": json.loads(old_data.get(b"admin_roles", b"[]")),
                    "enabled": old_data.get(b"enabled", b"true") == b"true",
                    "created_at": old_data.get(b"created_at", datetime.now().isoformat()),
                    "updated_at": old_data.get(b"updated_at", datetime.now().isoformat())
                }
            else:
                # Return default
                return {
                    "required_roles": [],
                    "suspended_users": [],
                    "admin_roles": [],
                    "enabled": True,
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat()
                }
        except Exception as e:
            logger.error(f"Error getting server permissions (legacy): {e}")
            return {
                "required_roles": [],
                "suspended_users": [],
                "admin_roles": [],
                "enabled": True,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def permissions_to_list(mask: int) -> List[str]:
    """Convert permission mask to list of permission names"""
    node_map = PermissionNodes.get_node_map()
    permissions = []
    
    for perm_name, perm_mask in node_map.items():
        if (mask & perm_mask) == perm_mask:
            permissions.append(perm_name)
    
    return permissions


def permissions_from_list(permissions: List[str]) -> int:
    """Convert list of permission names to mask"""
    mask = 0
    for perm in permissions:
        mask |= PermissionNodes.resolve_permission(perm)
    return mask


def format_permission_mask(mask: int) -> str:
    """Format permission mask as human-readable string"""
    return f"0x{mask:016X}"


def parse_permission_mask(mask_str: str) -> int:
    """Parse permission mask from string"""
    try:
        if mask_str.startswith("0x"):
            return int(mask_str, 16)
        return int(mask_str)
    except ValueError:
        return 0