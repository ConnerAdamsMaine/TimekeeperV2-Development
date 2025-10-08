# premium/API/app.py
# ============================================================================
# TimekeeperV2 - Premium API
# Main Flask application setup
# ============================================================================

from flask import Flask
from flask_cors import CORS
import logging
import os
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_app(bot=None):
    """Create and configure the Flask application"""
    app = Flask(__name__)
    app.config['JSON_AS_ASCII'] = False
    app.config['JSON_SORT_KEYS'] = False
    
    # Enable CORS
    CORS(app, resources={
        r"/api/*": {
            "origins": os.getenv("ALLOWED_ORIGINS", "*").split(","),
            "methods": ["GET", "POST", "PUT", "DELETE", "PATCH"],
            "allow_headers": ["Content-Type", "Authorization", "X-API-Key"]
        }
    })
    
    # Store bot instance in app config
    app.config['BOT'] = bot
    
    # Register blueprints
    from .routes import (
        auth_bp, status_bp, users_bp, clock_bp,
        categories_bp, leaderboard_bp, export_bp,
        config_bp, permissions_bp, analytics_bp, webhooks_bp
    )
    
    app.register_blueprint(auth_bp, url_prefix='/api/v1/auth')
    app.register_blueprint(status_bp, url_prefix='/api/v1')
    app.register_blueprint(users_bp, url_prefix='/api/v1/guild/<int:guild_id>/users')
    app.register_blueprint(clock_bp, url_prefix='/api/v1/guild/<int:guild_id>')
    app.register_blueprint(categories_bp, url_prefix='/api/v1/guild/<int:guild_id>/categories')
    app.register_blueprint(leaderboard_bp, url_prefix='/api/v1/guild/<int:guild_id>/leaderboard')
    app.register_blueprint(export_bp, url_prefix='/api/v1/guild/<int:guild_id>/export')
    app.register_blueprint(config_bp, url_prefix='/api/v1/guild/<int:guild_id>/config')
    app.register_blueprint(permissions_bp, url_prefix='/api/v1/guild/<int:guild_id>/permissions')
    app.register_blueprint(analytics_bp, url_prefix='/api/v1/guild/<int:guild_id>/analytics')
    app.register_blueprint(webhooks_bp, url_prefix='/api/v1/guild/<int:guild_id>/webhooks')
    
    # Register error handlers
    from .utils.errors import register_error_handlers
    register_error_handlers(app)
    
    logger.info("Premium API initialized successfully")
    
    return app


def run_api(bot, host='0.0.0.0', port=None):
    """Run the API server with bot integration"""
    app = create_app(bot)
    port = port or int(os.getenv('API_PORT', 5000))
    debug = os.getenv('FLASK_ENV', 'production') == 'development'
    
    logger.info(f"Starting Premium API on {host}:{port}")
    app.run(host=host, port=port, debug=debug, use_reloader=False)