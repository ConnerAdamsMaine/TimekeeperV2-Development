from flask import Blueprint, jsonify, g
from ..middleware.auth import require_api_key, APITier
from ..utils.helpers import run_async, get_tracker_and_clock

users_bp = Blueprint('users', __name__)

# Supporter tier can list basic user data
@users_bp.route('', methods=['GET'])
@require_api_key(['read:basic'])  # Supporter+
def list_users(guild_id: int):
    """List all users - Supporter: basic, Premium+: detailed"""
    if g.api_key_data['tier'] != APITier.ADMIN:
        if g.api_key_data['guild_id'] != guild_id:
            return jsonify({'error': 'Unauthorized guild access'}), 403
    
    # Supporter gets basic data, Premium+ gets full data
    include_details = g.api_key_data['tier'].value >= APITier.PREMIUM.value
    
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
                    
                    if include_details:
                        # Premium+: Get full user data
                        user_data = await tracker.get_user_times(guild_id, user_id, include_metadata=True)
                        users.append({
                            'user_id': user_id,
                            'total_seconds': user_data.get('total', 0),
                            'total_hours': round(user_data.get('total', 0) / 3600, 2),
                            'categories': user_data.get('categories'),
                            'metadata': user_data.get('metadata')
                        })
                    else:
                        # Supporter: Basic data only
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
            'users': users_data,
            'detail_level': 'full' if include_details else 'basic',
            'tier': g.api_key_data['tier_name']
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500