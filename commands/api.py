import discord
from discord.ext import commands
from discord import app_commands
import logging
import os
import asyncio
import threading

logger = logging.getLogger(__name__)


class APIManagementCog(commands.Cog):
    """Manage the Premium API server"""
    
    def __init__(self, bot):
        self.bot = bot
        self.api_thread = None
        self.api_running = False
        logger.info("APIManagementCog initialized")
    
    async def cog_load(self):
        """Auto-start API if configured"""
        if os.getenv('AUTO_START_API', 'false').lower() == 'true':
            logger.info("Auto-starting Premium API...")
            await self.start_api()
    
    async def cog_unload(self):
        """Stop API when cog unloads"""
        if self.api_running:
            logger.info("Stopping Premium API...")
            # The API will stop when the thread ends
            self.api_running = False
    
    async def start_api(self):
        """Start the API server in a separate thread"""
        if self.api_running:
            logger.warning("API already running")
            return False
        
        try:
            from premium.API.app import run_api
            
            def run_api_thread():
                try:
                    host = os.getenv('API_HOST', '0.0.0.0')
                    port = int(os.getenv('API_PORT', 5000))
                    run_api(self.bot, host=host, port=port)
                except Exception as e:
                    logger.error(f"API server error: {e}")
            
            self.api_thread = threading.Thread(target=run_api_thread, daemon=True)
            self.api_thread.start()
            self.api_running = True
            
            logger.info("Premium API started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start API: {e}")
            return False
    
    @app_commands.command(name="api", description="🔧 Manage the Premium API server (Dev only)")
    @app_commands.describe(action="Action to perform")
    @app_commands.choices(action=[
        app_commands.Choice(name="Start", value="start"),
        app_commands.Choice(name="Status", value="status"),
        app_commands.Choice(name="Generate Key", value="generate")
    ])
    async def api_command(self, interaction: discord.Interaction, action: str):
        """Manage the API server"""
        # Check if user is developer
        dev_id = int(os.getenv('DEV_USER_ID', 0))
        if interaction.user.id != dev_id:
            embed = discord.Embed(
                title="🔒 Developer Only",
                description="This command is restricted to the bot developer.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            if action == "start":
                if self.api_running:
                    embed = discord.Embed(
                        title="⚠️ API Already Running",
                        description="The Premium API server is already active.",
                        color=discord.Color.orange()
                    )
                else:
                    success = await self.start_api()
                    
                    if success:
                        port = int(os.getenv('API_PORT', 5000))
                        embed = discord.Embed(
                            title="✅ API Started",
                            description=f"Premium API server started successfully.",
                            color=discord.Color.green()
                        )
                        embed.add_field(name="Port", value=str(port), inline=True)
                        embed.add_field(name="Host", value=os.getenv('API_HOST', '0.0.0.0'), inline=True)
                    else:
                        embed = discord.Embed(
                            title="❌ API Start Failed",
                            description="Failed to start the API server. Check logs for details.",
                            color=discord.Color.red()
                        )
            
            elif action == "status":
                if self.api_running:
                    port = int(os.getenv('API_PORT', 5000))
                    host = os.getenv('API_HOST', '0.0.0.0')
                    
                    embed = discord.Embed(
                        title="✅ API Status",
                        description="Premium API server is **running**",
                        color=discord.Color.green()
                    )
                    embed.add_field(name="Host", value=host, inline=True)
                    embed.add_field(name="Port", value=str(port), inline=True)
                    embed.add_field(
                        name="Endpoint",
                        value=f"http://{host}:{port}/api/v1/status",
                        inline=False
                    )
                else:
                    embed = discord.Embed(
                        title="⚠️ API Status",
                        description="Premium API server is **not running**",
                        color=discord.Color.orange()
                    )
                    embed.add_field(
                        name="Start API",
                        value="Use `/api start` to start the server",
                        inline=False
                    )
            
            elif action == "generate":
                if not interaction.guild:
                    embed = discord.Embed(
                        title="❌ Error",
                        description="This command must be used in a server.",
                        color=discord.Color.red()
                    )
                else:
                    from premium.API.middleware.auth import APIAuth
                    from Utils.timekeeper import get_shared_tracker
                    
                    # Generate API key for this guild
                    tracker, _ = await get_shared_tracker()
                    
                    api_key = await APIAuth.generate_api_key(
                        interaction.guild.id,
                        interaction.user.id,
                        ['read', 'write', 'admin'],
                        tracker.redis
                    )
                    
                    embed = discord.Embed(
                        title="🔑 API Key Generated",
                        description="**IMPORTANT:** Store this key securely. It will not be shown again.",
                        color=discord.Color.blue()
                    )
                    embed.add_field(
                        name="API Key",
                        value=f"```{api_key}```",
                        inline=False
                    )
                    embed.add_field(
                        name="Guild ID",
                        value=str(interaction.guild.id),
                        inline=True
                    )
                    embed.add_field(
                        name="Rate Limit",
                        value="1000 requests/hour",
                        inline=True
                    )
                    embed.add_field(
                        name="Permissions",
                        value="read, write, admin",
                        inline=True
                    )
                    embed.add_field(
                        name="Usage",
                        value="Include in requests as `X-API-Key` header",
                        inline=False
                    )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in api command: {e}")
            embed = discord.Embed(
                title="❌ Error",
                description=f"An error occurred: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)


#async def setup(bot):
#    await bot.add_cog(APIManagementCog(bot))
#    logger.info("APIManagementCog loaded successfully")