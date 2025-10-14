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
from datetime import datetime
import json
import os

from Utils.timekeeper import get_shared_role_tracker

logger = logging.getLogger(__name__)


class HelpSupportCog(commands.Cog):
    """Comprehensive help, guide, and support system"""
    
    def __init__(self, bot):
        self.bot = bot
        self.tracker = None
        self.clock = None
        
        # Support ticket system
        self.active_tickets = {}  # user_id -> ticket_data
        self.ticket_counter = 0
        
        logger.info("HelpSupportCog initialized")
    
    async def cog_load(self):
        try:
            self.tracker, self.clock = await get_shared_role_tracker(self.bot)
            await self._load_tickets()
            logger.info("HelpSupportCog connected")
        except Exception as e:
            logger.error(f"Init failed: {e}")
    
    async def _load_tickets(self):
        """Load active tickets from Redis"""
        try:
            if not self.tracker:
                return
            
            tickets_data = await self.tracker.redis.get("support_tickets")
            if tickets_data:
                self.active_tickets = json.loads(tickets_data)
                self.ticket_counter = await self.tracker.redis.get("ticket_counter") or 0
                logger.info(f"Loaded {len(self.active_tickets)} tickets")
        except Exception as e:
            logger.error(f"Load tickets failed: {e}")
    
    async def _save_tickets(self):
        """Save tickets to Redis"""
        try:
            if not self.tracker:
                return
            
            await self.tracker.redis.set("support_tickets", json.dumps(self.active_tickets))
            await self.tracker.redis.set("ticket_counter", self.ticket_counter)
        except Exception as e:
            logger.error(f"Save tickets failed: {e}")
    
    # ========================================================================
    # HELP COMMAND - Interactive and Comprehensive
    # ========================================================================
    
    @app_commands.command(name="help", description="📚 Get help with Timekeeper commands")
    @app_commands.describe(
        category="Specific category to get help with"
    )
    @app_commands.choices(category=[
        app_commands.Choice(name="⏰ Time Tracking", value="tracking"),
        app_commands.Choice(name="📊 Analytics & Stats", value="analytics"),
        app_commands.Choice(name="👑 Admin Commands", value="admin"),
        app_commands.Choice(name="🎯 Dashboard", value="dashboard"),
        app_commands.Choice(name="📥 Export & Data", value="export"),
        app_commands.Choice(name="🔧 Configuration", value="config"),
    ])
    async def help_command(self, interaction: discord.Interaction, category: Optional[str] = None):
        """Comprehensive interactive help system"""
        await interaction.response.defer()
        
        if category:
            embed = await self._create_category_help(category)
        else:
            embed = await self._create_main_help()
        
        # Create navigation view
        view = HelpNavigationView(self)
        
        await interaction.followup.send(embed=embed, view=view)
    
    async def _create_main_help(self) -> discord.Embed:
        """Create main help embed"""
        embed = discord.Embed(
            title="📚 Timekeeper Help Center",
            description="Welcome to Timekeeper V2! Select a category below to learn more.\n\n"
                       "**Quick Start:** Use `/guide` for a step-by-step tutorial\n"
                       "**Need Help?** Use `/support` to contact the developer",
            color=discord.Color.blue()
        )
        
        # Command categories
        embed.add_field(
            name="⏰ Time Tracking Commands",
            value="• `/clockin` - Start tracking time\n"
                  "• `/clockout` - Stop tracking time\n"
                  "• `/status` - View your current status\n"
                  "• `/dashboard` - Interactive dashboard",
            inline=False
        )
        
        embed.add_field(
            name="📊 Analytics & Insights",
            value="• `/leaderboard` - Server rankings\n"
                  "• `/insights` - Advanced productivity analytics\n"
                  "• `/export` - Export your data",
            inline=False
        )
        
        embed.add_field(
            name="👑 Admin Commands (Administrators Only)",
            value="• `/admin categories` - Manage categories\n"
                  "• `/admin system` - View system status\n"
                  "• `/config` - Server configuration\n"
                  "• `/activitylog` - Configure activity logging",
            inline=False
        )
        
        embed.add_field(
            name="🎯 Other Commands",
            value="• `/whoclocked` - See who's currently tracking\n"
                  "• `/forceclockout` - Force clock out a user (Admin)\n"
                  "• `/guide` - Getting started guide\n"
                  "• `/support` - Contact support",
            inline=False
        )
        
        embed.add_field(
            name="🔗 Quick Links",
            value="• [Documentation](https://timekeeper.404connernotfound.dev)\n"
                  "• [Support Server](https://discord.gg/timekeeper)\n"
                  "• [Website](https://timekeeper.404connernotfound.dev)",
            inline=False
        )
        
        embed.set_footer(text="Use the buttons below to navigate • /help <category> for details")
        
        return embed
    
    async def _create_category_help(self, category: str) -> discord.Embed:
        """Create detailed help for specific category"""
        
        if category == "tracking":
            embed = discord.Embed(
                title="⏰ Time Tracking Commands",
                description="Learn how to track your time efficiently with Timekeeper",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="/clockin <category>",
                value="**Start tracking time in a category**\n"
                      "• Example: `/clockin work`\n"
                      "• Categories must be set up by server admins first\n"
                      "• You'll receive a role while clocked in\n"
                      "• Only one active session at a time",
                inline=False
            )
            
            embed.add_field(
                name="/clockout",
                value="**Stop tracking time**\n"
                      "• Saves your session duration\n"
                      "• Removes your tracking role\n"
                      "• Updates your statistics\n"
                      "• Shows session summary",
                inline=False
            )
            
            embed.add_field(
                name="/status",
                value="**View your tracking status**\n"
                      "• Shows if you're currently clocked in\n"
                      "• Displays total time tracked\n"
                      "• Category breakdown with percentages\n"
                      "• Recent activity and achievements",
                inline=False
            )
            
            embed.add_field(
                name="/dashboard [personal:True/False]",
                value="**Interactive control panel**\n"
                      "• `personal:False` - Shared dashboard (default)\n"
                      "• `personal:True` - Private ephemeral dashboard\n"
                      "• Quick buttons for all actions\n"
                      "• Real-time server statistics",
                inline=False
            )
            
            embed.add_field(
                name="💡 Pro Tips",
                value="• Clock in as soon as you start working\n"
                      "• Use descriptive categories for better insights\n"
                      "• Check your status regularly to track progress\n"
                      "• Sessions over 2 hours show 'deep work' achievements",
                inline=False
            )
        
        elif category == "analytics":
            embed = discord.Embed(
                title="📊 Analytics & Insights",
                description="Understand your productivity with advanced analytics",
                color=discord.Color.purple()
            )
            
            embed.add_field(
                name="/leaderboard [category] [timeframe]",
                value="**Server rankings and competition**\n"
                      "• View top contributors\n"
                      "• Filter by category (optional)\n"
                      "• Time periods: All Time, Week, Month\n"
                      "• Shows productivity scores (Premium)",
                inline=False
            )
            
            embed.add_field(
                name="/insights [user]",
                value="**Advanced productivity analytics**\n"
                      "• Productivity score (0-100)\n"
                      "• Activity streak tracking\n"
                      "• Category breakdown with trends\n"
                      "• Personalized recommendations\n"
                      "• Week-ahead predictions\n"
                      "• Server ranking comparison",
                inline=False
            )
            
            embed.add_field(
                name="/export <format> [user]",
                value="**Export your time data**\n"
                      "• Formats: CSV, PDF, DOCX\n"
                      "• Complete session history\n"
                      "• Category summaries\n"
                      "• Admin can export other users' data",
                inline=False
            )
            
            embed.add_field(
                name="📈 Understanding Your Score",
                value="**Productivity Score Factors:**\n"
                      "• Consistency (20%) - Regular work patterns\n"
                      "• Balance (15%) - Healthy work-life mix\n"
                      "• Time Patterns (15%) - Working optimal hours\n"
                      "• Session Quality (15%) - Ideal session lengths\n"
                      "• Volume (15%) - Appropriate work hours\n"
                      "• Focus (10%) - Longer, deeper sessions\n"
                      "• Trend (10%) - Improvement over time",
                inline=False
            )
        
        elif category == "admin":
            embed = discord.Embed(
                title="👑 Admin Commands",
                description="Server management and configuration (Administrator permission required)",
                color=discord.Color.gold()
            )
            
            embed.add_field(
                name="/admin categories",
                value="**Manage time tracking categories**\n"
                      "• `list` - View all categories\n"
                      "• `add <name>` - Create new category\n"
                      "• `remove <name>` - Delete category\n"
                      "• Categories with data are archived, not deleted",
                inline=False
            )
            
            embed.add_field(
                name="/admin system",
                value="**View system health and metrics**\n"
                      "• System status and health score\n"
                      "• Redis database status\n"
                      "• Performance metrics\n"
                      "• Cache hit rates\n"
                      "• Session statistics",
                inline=False
            )
            
            embed.add_field(
                name="/config",
                value="**Server configuration**\n"
                      "• Manage categories\n"
                      "• User permissions\n"
                      "• Role requirements\n"
                      "• Suspend/unsuspend users\n"
                      "• Export server data\n"
                      "• System enable/disable",
                inline=False
            )
            
            embed.add_field(
                name="/activitylog",
                value="**Configure activity logging**\n"
                      "• Set channel for clock in/out logs\n"
                      "• Real-time activity feed\n"
                      "• Track user engagement\n"
                      "• Achievement notifications",
                inline=False
            )
            
            embed.add_field(
                name="/forceclockout <user> [reason]",
                value="**Force clock out a user**\n"
                      "• Emergency session termination\n"
                      "• Saves session data\n"
                      "• Logs action with reason\n"
                      "• Notifies user",
                inline=False
            )
        
        elif category == "dashboard":
            embed = discord.Embed(
                title="🎯 Interactive Dashboard",
                description="Master the dashboard for quick and efficient time tracking",
                color=discord.Color.blurple()
            )
            
            embed.add_field(
                name="Dashboard Types",
                value="**Shared Dashboard** (`/dashboard`)\n"
                      "• Posted in channel for everyone\n"
                      "• Auto-updates every 60 seconds\n"
                      "• Persistent - no timeout\n"
                      "• Shows real-time server stats\n\n"
                      "**Personal Dashboard** (`/dashboard personal:True`)\n"
                      "• Private - only you can see it\n"
                      "• Ephemeral - disappears after 5 minutes\n"
                      "• Customized to your data\n"
                      "• No server stats",
                inline=False
            )
            
            embed.add_field(
                name="Dashboard Buttons",
                value="⏰ **Clock In** - Opens modal to start tracking\n"
                      "🛑 **Clock Out** - Stops your current session\n"
                      "📊 **My Stats** - View your personal statistics\n"
                      "🌐 **Server Total** - View server-wide stats\n"
                      "👥 **Who's Clocked In** - See active users",
                inline=False
            )
            
            embed.add_field(
                name="Managing Dashboards",
                value="**One per channel** - Only one shared dashboard per channel\n"
                      "**Admin removal** - Use `/dashboard-remove` (Admin only)\n"
                      "**Multiple personal** - Create as many as needed\n"
                      "**Auto-cleanup** - Personal dashboards expire automatically",
                inline=False
            )
            
            embed.add_field(
                name="💡 Best Practices",
                value="• Create one shared dashboard in a dedicated channel\n"
                      "• Pin the dashboard message for easy access\n"
                      "• Use personal dashboards for private checking\n"
                      "• Check 'Who's Clocked In' for team awareness",
                inline=False
            )
        
        elif category == "export":
            embed = discord.Embed(
                title="📥 Export & Data Management",
                description="Export and analyze your time tracking data",
                color=discord.Color.orange()
            )
            
            embed.add_field(
                name="/export <format> [user]",
                value="**Export your time data**\n\n"
                      "**Formats:**\n"
                      "• `CSV` - Spreadsheet compatible, best for analysis\n"
                      "• `PDF` - Professional reports (HTML format)\n"
                      "• `DOCX` - Text document (TXT format)\n\n"
                      "**Contents:**\n"
                      "• Complete session history\n"
                      "• Category breakdown\n"
                      "• Time summaries\n"
                      "• Session metadata",
                inline=False
            )
            
            embed.add_field(
                name="Admin Features",
                value="**Export Other Users** (Admin only)\n"
                      "• Specify user parameter\n"
                      "• Access to all user data\n"
                      "• Bulk export capabilities\n"
                      "• Server-wide reports",
                inline=False
            )
            
            embed.add_field(
                name="Data Privacy",
                value="• Only you can export your own data\n"
                      "• Admins can export any user's data\n"
                      "• Exports are sent privately (ephemeral)\n"
                      "• No data leaves Discord without your action",
                inline=False
            )
        
        elif category == "config":
            embed = discord.Embed(
                title="🔧 Configuration System",
                description="Customize Timekeeper for your server",
                color=discord.Color.dark_grey()
            )
            
            embed.add_field(
                name="Category Management",
                value="**Setting Up Categories:**\n"
                      "1. Use `/admin categories add <name>`\n"
                      "2. Choose clear, descriptive names\n"
                      "3. Examples: work, meetings, development, support\n"
                      "4. Users can only track in configured categories",
                inline=False
            )
            
            embed.add_field(
                name="Permission System",
                value="**User Access Control:**\n"
                      "• Suspend users from tracking\n"
                      "• Require specific roles\n"
                      "• Enable/disable system server-wide\n"
                      "• Admin roles configuration",
                inline=False
            )
            
            embed.add_field(
                name="Activity Logging",
                value="**Track User Activity:**\n"
                      "• Set logging channel with `/activitylog`\n"
                      "• See all clock in/out events\n"
                      "• Monitor user engagement\n"
                      "• Achievement notifications",
                inline=False
            )
        
        embed.set_footer(text="Use /help to return to main menu")
        return embed
    
    # ========================================================================
    # GUIDE COMMAND - Step-by-Step Tutorial
    # ========================================================================
    
    @app_commands.command(name="guide", description="📖 Step-by-step getting started guide")
    async def guide_command(self, interaction: discord.Interaction):
        """Interactive getting started guide"""
        await interaction.response.defer()
        
        embed = discord.Embed(
            title="📖 Timekeeper Getting Started Guide",
            description="Welcome! Let's get you started with time tracking in just a few steps.",
            color=discord.Color.green()
        )
        
        # Step 1
        embed.add_field(
            name="📝 Step 1: Categories Setup (Admins Only)",
            value="**Server administrators need to set up categories first.**\n"
                  "```\n/admin categories add work```\n"
                  "Suggested categories: `work`, `meetings`, `development`, `support`, `training`, `break`\n\n"
                  "💡 Choose categories that match your team's activities!",
            inline=False
        )
        
        # Step 2
        embed.add_field(
            name="⏰ Step 2: Your First Clock In",
            value="**Start tracking time in any configured category.**\n"
                  "```\n/clockin work```\n"
                  "• A role will be assigned to you\n"
                  "• You'll see a confirmation message\n"
                  "• You can only have one active session\n\n"
                  "💡 Clock in as soon as you start working!",
            inline=False
        )
        
        # Step 3
        embed.add_field(
            name="📊 Step 3: Check Your Status",
            value="**See your current tracking status anytime.**\n"
                  "```\n/status```\n"
                  "This shows:\n"
                  "• Whether you're currently clocked in\n"
                  "• Current session duration\n"
                  "• Your total tracked time\n"
                  "• Category breakdown\n\n"
                  "💡 Check this regularly to stay aware of your time!",
            inline=False
        )
        
        # Step 4
        embed.add_field(
            name="🛑 Step 4: Clock Out When Done",
            value="**Stop tracking when you finish.**\n"
                  "```\n/clockout```\n"
                  "• Saves your session\n"
                  "• Removes your role\n"
                  "• Shows session summary\n"
                  "• Updates your stats\n\n"
                  "💡 Don't forget to clock out at the end of your work!",
            inline=False
        )
        
        # Step 5
        embed.add_field(
            name="🎯 Step 5: Use the Dashboard (Optional)",
            value="**Create an interactive control panel.**\n"
                  "```\n/dashboard```\n"
                  "• Quick-access buttons\n"
                  "• Real-time server stats\n"
                  "• See who's currently tracking\n"
                  "• One command for everything\n\n"
                  "💡 Pin the dashboard message for easy access!",
            inline=False
        )
        
        # Next Steps
        embed.add_field(
            name="🚀 Next Steps",
            value="**Explore Advanced Features:**\n"
                  "• `/leaderboard` - Compete with your team\n"
                  "• `/insights` - View productivity analytics\n"
                  "• `/export` - Download your data\n"
                  "• `/help analytics` - Learn about insights\n\n"
                  "**Need Help?**\n"
                  "• `/help` - Full command reference\n"
                  "• `/support` - Contact developer",
            inline=False
        )
        
        embed.set_footer(text="You're all set! Start tracking your time with /clockin")
        
        await interaction.followup.send(embed=embed)
    
    # ========================================================================
    # SUPPORT COMMAND - Ticket System with Developer Proxy
    # ========================================================================
    
    @app_commands.command(name="support", description="🆘 Contact the developer for help")
    async def support_command(self, interaction: discord.Interaction):
        """Open a support ticket"""
        await interaction.response.send_modal(SupportTicketModal(self))
    
    async def create_ticket(self, user: discord.User, subject: str, message: str):
        """Create a new support ticket"""
        self.ticket_counter += 1
        ticket_id = f"TK{self.ticket_counter:04d}"
        
        # Create ticket data
        ticket_data = {
            'id': ticket_id,
            'user_id': user.id,
            'username': str(user),
            'subject': subject,
            'status': 'open',
            'created_at': datetime.now().isoformat(),
            'messages': [
                {
                    'from': 'user',
                    'content': message,
                    'timestamp': datetime.now().isoformat()
                }
            ]
        }
        
        self.active_tickets[user.id] = ticket_data
        await self._save_tickets()
        
        # Send to developer
        dev_id = int(os.getenv('DEV_USER_ID', 0))
        if dev_id:
            try:
                developer = await self.bot.fetch_user(dev_id)
                
                embed = discord.Embed(
                    title=f"🎫 New Support Ticket: {ticket_id}",
                    description=f"**Subject:** {subject}",
                    color=discord.Color.red()
                )
                
                embed.add_field(
                    name="👤 From",
                    value=f"{user.mention} ({user.name})\nUser ID: `{user.id}`",
                    inline=False
                )
                
                embed.add_field(
                    name="💬 Message",
                    value=message[:1000],
                    inline=False
                )
                
                embed.add_field(
                    name="📝 How to Respond",
                    value=f"Reply using: `/ticket-reply {ticket_id} <message>`\n"
                          f"Close ticket: `/ticket-close {ticket_id}`\n"
                          f"View all: `/tickets`",
                    inline=False
                )
                
                embed.timestamp = datetime.now()
                embed.set_footer(text=f"Ticket ID: {ticket_id}")
                
                await developer.send(embed=embed)
                
            except Exception as e:
                logger.error(f"Send to dev failed: {e}")
        
        # Confirm to user
        try:
            embed = discord.Embed(
                title="✅ Support Ticket Created",
                description="Your ticket has been submitted successfully!",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="🎫 Ticket ID",
                value=f"`{ticket_id}`",
                inline=True
            )
            
            embed.add_field(
                name="📋 Subject",
                value=subject,
                inline=True
            )
            
            embed.add_field(
                name="💬 Your Message",
                value=message[:500],
                inline=False
            )
            
            embed.add_field(
                name="⏱️ What's Next?",
                value="• The developer will be notified\n"
                      "• You'll receive a DM when they respond\n"
                      "• Use `/support` again to check status\n"
                      "• Average response time: 24-48 hours",
                inline=False
            )
            
            embed.set_footer(text=f"Ticket ID: {ticket_id} • Created")
            embed.timestamp = datetime.now()
            
            await user.send(embed=embed)
            
        except discord.Forbidden:
            logger.warning(f"DM failed: user={user.id}")
        
        return ticket_id
    
    async def send_ticket_response(self, ticket_id: str, developer: discord.User, response_message: str):
        """Developer responds to a ticket"""
        # Find ticket
        ticket_data = None
        user_id = None
        
        for uid, ticket in self.active_tickets.items():
            if ticket['id'] == ticket_id:
                ticket_data = ticket
                user_id = uid
                break
        
        if not ticket_data:
            return False, "Ticket not found"
        
        if ticket_data['status'] == 'closed':
            return False, "Ticket is already closed"
        
        # Add response to ticket
        ticket_data['messages'].append({
            'from': 'developer',
            'content': response_message,
            'timestamp': datetime.now().isoformat()
        })
        
        await self._save_tickets()
        
        # Send to user
        try:
            user = await self.bot.fetch_user(user_id)
            
            embed = discord.Embed(
                title=f"💬 Developer Response - Ticket {ticket_id}",
                description=f"**Subject:** {ticket_data['subject']}",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="👨‍💻 Developer says:",
                value=response_message,
                inline=False
            )
            
            embed.add_field(
                name="💬 Reply",
                value="Use `/support` to reply to this ticket",
                inline=False
            )
            
            embed.timestamp = datetime.now()
            embed.set_footer(text=f"Ticket ID: {ticket_id}")
            
            await user.send(embed=embed)
            
            return True, "Response sent successfully"
            
        except Exception as e:
            logger.error(f"Send response failed: {e}")
            return False, f"Error: {str(e)}"
    
    async def close_ticket(self, ticket_id: str, reason: str = None):
        """Close a support ticket"""
        # Find ticket
        ticket_data = None
        user_id = None
        
        for uid, ticket in self.active_tickets.items():
            if ticket['id'] == ticket_id:
                ticket_data = ticket
                user_id = uid
                break
        
        if not ticket_data:
            return False, "Ticket not found"
        
        # Update status
        ticket_data['status'] = 'closed'
        ticket_data['closed_at'] = datetime.now().isoformat()
        ticket_data['close_reason'] = reason
        
        await self._save_tickets()
        
        # Notify user
        try:
            user = await self.bot.fetch_user(user_id)
            
            embed = discord.Embed(
                title=f"🎫 Ticket Closed: {ticket_id}",
                description="Your support ticket has been resolved.",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="📋 Subject",
                value=ticket_data['subject'],
                inline=False
            )
            
            if reason:
                embed.add_field(
                    name="✅ Resolution",
                    value=reason,
                    inline=False
                )
            
            embed.add_field(
                name="💬 Need More Help?",
                value="You can create a new ticket anytime with `/support`",
                inline=False
            )
            
            embed.timestamp = datetime.now()
            embed.set_footer(text=f"Ticket ID: {ticket_id} • Closed")
            
            await user.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Notify close failed: {e}")
        
        return True, "Ticket closed successfully"
    
    # ========================================================================
    # DEVELOPER COMMANDS (Hidden from normal users)
    # ========================================================================
    
    @app_commands.command(name="ticket-reply", description="🔧 Reply to a support ticket (Dev only)")
    @app_commands.describe(
        ticket_id="Ticket ID (e.g., TK0001)",
        message="Your response message"
    )
    async def ticket_reply(self, interaction: discord.Interaction, ticket_id: str, message: str):
        """Developer replies to a ticket"""
        dev_id = int(os.getenv('DEV_USER_ID', 0))
        
        if interaction.user.id != dev_id:
            await interaction.response.send_message("❌ This command is developer-only.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        success, result = await self.send_ticket_response(ticket_id.upper(), interaction.user, message)
        
        if success:
            embed = discord.Embed(
                title="✅ Response Sent",
                description="Your response has been sent to the user.",
                color=discord.Color.green()
            )
            embed.add_field(name="Ticket ID", value=ticket_id.upper(), inline=True)
            embed.add_field(name="Message", value=message[:1000], inline=False)
        else:
            embed = discord.Embed(
                title="❌ Error",
                description=result,
                color=discord.Color.red()
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="ticket-close", description="🔧 Close a support ticket (Dev only)")
    @app_commands.describe(
        ticket_id="Ticket ID (e.g., TK0001)",
        reason="Reason for closing (optional)"
    )
    async def ticket_close(self, interaction: discord.Interaction, ticket_id: str, reason: Optional[str] = None):
        """Developer closes a ticket"""
        dev_id = int(os.getenv('DEV_USER_ID', 0))
        
        if interaction.user.id != dev_id:
            await interaction.response.send_message("❌ This command is developer-only.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        success, result = await self.close_ticket(ticket_id.upper(), reason)
        
        if success:
            embed = discord.Embed(
                title="✅ Ticket Closed",
                description=f"Ticket {ticket_id.upper()} has been closed.",
                color=discord.Color.green()
            )
            if reason:
                embed.add_field(name="Reason", value=reason, inline=False)
        else:
            embed = discord.Embed(
                title="❌ Error",
                description=result,
                color=discord.Color.red()
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="tickets", description="🔧 View all support tickets (Dev only)")
    @app_commands.describe(
        status="Filter by status"
    )
    @app_commands.choices(status=[
        app_commands.Choice(name="Open", value="open"),
        app_commands.Choice(name="Closed", value="closed"),
        app_commands.Choice(name="All", value="all")
    ])
    async def tickets_list(self, interaction: discord.Interaction, status: str = "open"):
        """Developer views all tickets"""
        dev_id = int(os.getenv('DEV_USER_ID', 0))
        
        if interaction.user.id != dev_id:
            await interaction.response.send_message("❌ This command is developer-only.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Filter tickets
        filtered_tickets = []
        for user_id, ticket in self.active_tickets.items():
            if status == "all" or ticket['status'] == status:
                filtered_tickets.append(ticket)
        
        if not filtered_tickets:
            embed = discord.Embed(
                title="📋 Support Tickets",
                description=f"No {status} tickets found.",
                color=discord.Color.blue()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Create embeds (max 10 tickets per embed)
        embed = discord.Embed(
            title=f"📋 Support Tickets ({status.title()})",
            description=f"Total: {len(filtered_tickets)} tickets",
            color=discord.Color.blue()
        )
        
        for ticket in filtered_tickets[:10]:
            status_emoji = "🟢" if ticket['status'] == "open" else "⚫"
            
            value = f"**Subject:** {ticket['subject']}\n"
            value += f"**User:** {ticket['username']} (`{ticket['user_id']}`)\n"
            value += f"**Messages:** {len(ticket['messages'])}\n"
            value += f"**Created:** {ticket['created_at'][:16]}\n"
            
            if ticket['status'] == 'closed':
                value += f"**Closed:** {ticket.get('closed_at', 'Unknown')[:16]}"
            
            embed.add_field(
                name=f"{status_emoji} {ticket['id']}",
                value=value,
                inline=False
            )
        
        if len(filtered_tickets) > 10:
            embed.set_footer(text=f"Showing 10 of {len(filtered_tickets)} tickets")
        
        await interaction.followup.send(embed=embed, ephemeral=True)


class HelpNavigationView(discord.ui.View):
    """Interactive navigation for help command"""
    
    def __init__(self, cog):
        super().__init__(timeout=180)
        self.cog = cog
    
    @discord.ui.button(label="⏰ Time Tracking", style=discord.ButtonStyle.primary, custom_id="help_tracking")
    async def tracking_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = await self.cog._create_category_help("tracking")
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="📊 Analytics", style=discord.ButtonStyle.primary, custom_id="help_analytics")
    async def analytics_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = await self.cog._create_category_help("analytics")
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="👑 Admin", style=discord.ButtonStyle.danger, custom_id="help_admin")
    async def admin_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = await self.cog._create_category_help("admin")
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="🎯 Dashboard", style=discord.ButtonStyle.success, custom_id="help_dashboard")
    async def dashboard_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = await self.cog._create_category_help("dashboard")
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="📥 Export", style=discord.ButtonStyle.secondary, custom_id="help_export")
    async def export_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = await self.cog._create_category_help("export")
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="🏠 Main Menu", style=discord.ButtonStyle.primary, custom_id="help_main", row=1)
    async def main_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = await self.cog._create_main_help()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="📖 Getting Started", style=discord.ButtonStyle.success, custom_id="help_guide", row=1)
    async def guide_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        
        embed = discord.Embed(
            title="📖 Quick Start Guide",
            description="Use `/guide` for the full interactive getting started guide!",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="Quick Steps",
            value="1️⃣ Admins: Set up categories with `/admin categories add <n>`\n"
                  "2️⃣ Users: Start tracking with `/clockin <category>`\n"
                  "3️⃣ Check progress with `/status`\n"
                  "4️⃣ Stop tracking with `/clockout`\n"
                  "5️⃣ Create dashboard with `/dashboard`",
            inline=False
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)


class SupportTicketModal(discord.ui.Modal, title="Create Support Ticket"):
    """Modal for creating support tickets"""
    
    subject = discord.ui.TextInput(
        label="Subject",
        placeholder="Brief description of your issue",
        required=True,
        max_length=100
    )
    
    message = discord.ui.TextInput(
        label="Message",
        placeholder="Detailed description of your issue or question...",
        required=True,
        max_length=1000,
        style=discord.TextStyle.paragraph
    )
    
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        # Check if user already has an open ticket
        if interaction.user.id in self.cog.active_tickets:
            existing = self.cog.active_tickets[interaction.user.id]
            if existing['status'] == 'open':
                embed = discord.Embed(
                    title="⚠️ Existing Ticket",
                    description=f"You already have an open ticket: **{existing['id']}**",
                    color=discord.Color.orange()
                )
                embed.add_field(
                    name="Subject",
                    value=existing['subject'],
                    inline=False
                )
                embed.add_field(
                    name="Status",
                    value="Waiting for developer response",
                    inline=False
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
        
        # Create ticket
        ticket_id = await self.cog.create_ticket(
            interaction.user,
            self.subject.value,
            self.message.value
        )
        
        embed = discord.Embed(
            title="✅ Ticket Created",
            description=f"Your support ticket **{ticket_id}** has been created successfully!",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="📬 What's Next?",
            value="You'll receive a DM when the developer responds.\n"
                  "Average response time: 24-48 hours",
            inline=False
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(HelpSupportCog(bot))
    logger.info("HelpSupportCog loaded")