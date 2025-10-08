# premium/API/routes/status.py
# ============================================================================
# Status and info routes
# ============================================================================

from flask import Blueprint, jsonify, g
from datetime import datetime

from ..middleware.auth import require_api_key
from ..utils.helpers import run_async, get_tracker_and_clock

status_bp = Blueprint('status', __name__)


@status_bp.route('/status', methods=['GET'])
def api_status():
    """Get API status"""
    return jsonify({
        'status': 'operational',
        'version': '1.0.0',
        'timestamp': datetime.now().isoformat(),
        'endpoints': {
            'authentication': '/api/v1/auth',
            'guilds': '/api/v1/guild/{guild_id}',
            'documentation': '/api/v1/docs'
        }
    }), 200


@status_bp.route('/guild/<int:guild_id>/status', methods=['GET'])
@require_api_key(['read'])
def guild_status(guild_id: int):
    """Get guild status"""
    if g.api_key_data['guild_id'] != guild_id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        async def get_status():
            tracker, _ = await get_tracker_and_clock()
            
            # Get server totals
            server_key = f"server_times:{guild_id}"
            server_data = await tracker.redis.hgetall(server_key)
            
            total_seconds = int(server_data.get(b'total', b'0')) if server_data else 0
            categories = {}
            
            if server_data:
                for key, value in server_data.items():
                    key_str = key.decode('utf-8')
                    if key_str != 'total':
                        categories[key_str] = int(value)
            
            # Count users and active sessions
            user_pattern = f"user_times:{guild_id}:*"
            active_pattern = f"active_session:{guild_id}:*"
            
            user_cursor = 0
            user_count = 0
            while True:
                user_cursor, keys = await tracker.redis.scan(user_cursor, match=user_pattern, count=100)
                user_count += len(keys)
                if user_cursor == 0:
                    break
            
            active_cursor = 0
            active_count = 0
            while True:
                active_cursor, keys = await tracker.redis.scan(active_cursor, match=active_pattern, count=100)
                active_count += len(keys)
                if active_cursor == 0:
                    break
            
            return {
                'guild_id': guild_id,
                'total_time_seconds': total_seconds,
                'total_time_hours': round(total_seconds / 3600, 2),
                'total_users': user_count,
                'active_sessions': active_count,
                'categories': categories,
                'timestamp': datetime.now().isoformat()
            }
        
        status_data = run_async(get_status())
        return jsonify(status_data), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500