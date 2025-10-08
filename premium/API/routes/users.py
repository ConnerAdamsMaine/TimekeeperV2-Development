# premium/API/routes/users.py
# ============================================================================
# User management routes
# ============================================================================

from flask import Blueprint, jsonify, g

from ..middleware.auth import require_api_key
from ..utils.helpers import run_async, get_tracker_and_clock

users_bp = Blueprint('users', __name__)


@users_bp.route('', methods=['GET'])
@require_api_key(['read'])
def list_users(guild_id: int):
    """List all users with time tracking data"""
    if g.api_key_data['guild_id'] != guild_id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        async def get_users():
            tracker, _ = await get_tracker_and_clock()
            users = []
            pattern = f"user_times:{guild_id}:*"
            cursor = 0
            
            while True:
                cursor, keys = await tracker.redis.scan(cursor, match=pattern, count=100)
                
                for key in keys:
                    user_id = int(key.decode().split(':')[-1])
                    user_data = await tracker.redis.hgetall(key)
                    
                    if user_data:
                        total_seconds = int(user_data.get(b'total', b'0'))
                        users.append({
                            'user_id': user_id,
                            'total_seconds': total_seconds,
                            'total_hours': round(total_seconds / 3600, 2)
                        })
                
                if cursor == 0:
                    break
            
            users.sort(key=lambda x: x['total_seconds'], reverse=True)
            return users
        
        users_data = run_async(get_users())
        
        return jsonify({
            'guild_id': guild_id,
            'user_count': len(users_data),
            'users': users_data
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@users_bp.route('/<int:user_id>', methods=['GET'])
@require_api_key(['read'])
def get_user(guild_id: int, user_id: int):
    """Get detailed user data"""
    if g.api_key_data['guild_id'] != guild_id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        async def get_user_data():
            tracker, _ = await get_tracker_and_clock()
            return await tracker.get_user_times(guild_id, user_id, include_metadata=True)
        
        user_data = run_async(get_user_data())
        
        return jsonify({
            'guild_id': guild_id,
            'user_id': user_id,
            'data': user_data
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500