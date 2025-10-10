from flask import Flask, jsonify
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
    from .routes.tier_management import tier_mgmt_bp
    from routes.admin import admin_api_bp
    
    app.register_blueprint(admin_api_bp, url_prefix="/api/v1/admin")
    
    # Core routes
    app.register_blueprint(auth_bp, url_prefix='/api/v1/auth')
    app.register_blueprint(status_bp, url_prefix='/api/v1')
    app.register_blueprint(tier_mgmt_bp, url_prefix='/api/v1/tier')
    
    # Guild-specific routes
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
    
    # API documentation endpoint
    @app.route('/api/v1/docs', methods=['GET'])
    def api_docs():
        """API documentation and tier information"""
        return jsonify({
            'version': '1.0.0',
            'base_url': '/api/v1',
            'authentication': {
                'method': 'API Key',
                'header': 'X-API-Key',
                'obtain_key': 'POST /api/v1/auth/generate'
            },
            'tiers': {
                'supporter': {
                    'rate_limit': '20 requests/minute',
                    'permissions': 'Read-only basic data',
                    'price': 'Free/Donation'
                },
                'premium': {
                    'rate_limit': '60 requests/minute',
                    'permissions': 'Full read + admin write',
                    'price': 'Contact for pricing'
                },
                'enterprise': {
                    'rate_limit': '120 requests/minute',
                    'permissions': 'Full access + sub-keys',
                    'price': 'Contact for pricing'
                },
                'admin': {
                    'rate_limit': 'Unlimited',
                    'permissions': 'Unrestricted access',
                    'price': 'Internal only'
                }
            },
            'endpoints': {
                'authentication': {
                    'POST /auth/generate': 'Generate new API key',
                    'POST /auth/validate': 'Validate API key'
                },
                'tier_management': {
                    'GET /tier/tiers': 'List all tiers',
                    'GET /tier/my-tier': 'Get your tier info',
                    'GET /tier/upgrade': 'Get upgrade information',
                    'GET /tier/sub-keys': 'List sub-keys (Enterprise+)',
                    'POST /tier/sub-keys': 'Create sub-key (Enterprise+)',
                    'DELETE /tier/sub-keys/<hash>': 'Revoke sub-key (Enterprise+)'
                },
                'guild_data': {
                    'GET /guild/{guild_id}/status': 'Guild status',
                    'GET /guild/{guild_id}/users': 'List users (Supporter+)',
                    'GET /guild/{guild_id}/users/{user_id}': 'User details (Supporter+)',
                    'GET /guild/{guild_id}/leaderboard': 'Leaderboard (Supporter+)',
                    'GET /guild/{guild_id}/categories': 'List categories (Supporter+)',
                    'POST /guild/{guild_id}/categories': 'Add category (Enterprise+)',
                    'POST /guild/{guild_id}/clockin': 'Clock in user (Premium+)',
                    'POST /guild/{guild_id}/clockout': 'Clock out user (Premium+)',
                    'GET /guild/{guild_id}/analytics/insights/<user_id>': 'User insights (Premium+)',
                    'POST /guild/{guild_id}/webhooks': 'Create webhook (Enterprise+)'
                }
            },
            'rate_limiting': {
                'headers': {
                    'X-RateLimit-Limit': 'Maximum requests per minute',
                    'X-RateLimit-Remaining': 'Remaining requests',
                    'X-RateLimit-Reset': 'Seconds until reset',
                    'X-API-Tier': 'Your current tier'
                },
                'shared_pools': 'Sub-keys share parent key rate limit'
            }
        }), 200
    
    logger.info("Premium API initialized with tiered access system")
    
    return app


def run_api(bot, host='0.0.0.0', port=None):
    """Run the API server with bot integration"""
    app = create_app(bot)
    port = port or int(os.getenv('API_PORT', 5000))
    debug = os.getenv('FLASK_ENV', 'production') == 'development'
    
    logger.info(f"Starting Premium API on {host}:{port}")
    logger.info("Tiered access system enabled:")
    logger.info("  - Supporter: 20 req/min, read-only")
    logger.info("  - Premium: 60 req/min, read + limited write")
    logger.info("  - Enterprise: 120 req/min, full access + sub-keys")
    logger.info("  - Admin: Unlimited, unrestricted")
    
    app.run(host=host, port=port, debug=debug, use_reloader=False)