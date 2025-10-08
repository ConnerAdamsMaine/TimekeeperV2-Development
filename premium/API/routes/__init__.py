# premium/API/routes/__init__.py
# ============================================================================
# Import and expose all route blueprints
# ============================================================================

from .auth import auth_bp
from .status import status_bp
from .users import users_bp
from .clock import clock_bp
from .categories import categories_bp
from .leaderboard import leaderboard_bp
from .export import export_bp
from .config import config_bp
from .permissions import permissions_bp
from .analytics import analytics_bp
from .webhooks import webhooks_bp

__all__ = [
    'auth_bp', 'status_bp', 'users_bp', 'clock_bp',
    'categories_bp', 'leaderboard_bp', 'export_bp',
    'config_bp', 'permissions_bp', 'analytics_bp', 'webhooks_bp'
]