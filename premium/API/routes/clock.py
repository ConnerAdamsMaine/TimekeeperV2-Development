# premium/API/routes/clock.py
# ============================================================================
# Clock in/out routes
# ============================================================================

from flask import Blueprint, request, jsonify, g
import secrets
import json
from datetime import datetime
import logging

from ..middleware.auth import require_api_key, require_tier, APITier
from ..utils.helpers import run_async, get_tracker_and_clock

logger = logging.getLogger(__name__)

clock_bp = Blueprint('clock', __name__)

# Premium tier required for clock in (admin users only for Premium tier)
@clock_bp.route('/clockin', methods=['POST'])
@require_tier(APITier.PREMIUM)  # Premium+ can clock in
def api_clockin(guild_id: int):
    """Clock in user - Premium: admin users only, Enterprise+: all users"""
    if g.api_key_data['tier'] != APITier.ADMIN:
        if g.api_key_data['guild_id'] != guild_id:
            return jsonify({'error': 'Unauthorized guild access'}), 403
    
    data = request.get_json()
    
    if not data or 'user_id' not in data or 'category' not in data:
        return jsonify({
            'error': 'Missing required fields',
            'message': 'user_id and category are required'
        }), 400
    
    user_id = data['user_id']
    
    # Premium tier can only clock in admin users
    if g.api_key_data['tier'] == APITier.PREMIUM:
        # Check if user is admin
        async def check_admin():
            bot = current_app.config.get('BOT')
            if not bot:
                return False
            
            guild = bot.get_guild(guild_id)
            if not guild:
                return False
            
            member = guild.get_member(user_id)
            if not member:
                return False
            
            return member.guild_permissions.administrator
        
        is_admin = run_async(check_admin())
        
        if not is_admin:
            return jsonify({
                'error': 'Premium tier restriction',
                'message': 'Premium tier can only clock in/out admin users',
                'your_tier': 'PREMIUM',
                'required_tier_for_all_users': 'ENTERPRISE',
                'upgrade_endpoint': '/api/v1/tier/upgrade'
            }), 403
    
    try:
        async def clockin():
            tracker, clock = await get_tracker_and_clock()
            
            # Check if already clocked in
            session = await clock.get_active_session(guild_id, user_id)
            if session:
                return {
                    'success': False,
                    'error': 'Already clocked in',
                    'current_session': {
                        'category': session['category'],
                        'start_time': session['start_time'],
                        'session_id': session['session_id']
                    }
                }, 400
            
            # Create session
            session_id = f"api_{secrets.token_hex(8)}"
            start_time = datetime.now()
            
            metadata = {
                'description': description,
                'source': 'api',
                'api_key': g.api_key_data['key_hash'][:8]
            }
            
            session_data = {
                'server_id': guild_id,
                'user_id': user_id,
                'category': category,
                'start_time': start_time.isoformat(),
                'session_id': session_id,
                'role_id': None,
                'metadata': metadata
            }
            
            session_key = f"active_session:{guild_id}:{user_id}"
            await tracker.redis.setex(session_key, 86400, json.dumps(session_data))
            
            return {
                'success': True,
                'session_id': session_id,
                'category': category,
                'start_time': start_time.isoformat(),
                'user_id': user_id
            }, 201
        
        result, status = run_async(clockin())
        return jsonify(result), status
        
    except Exception as e:
        logger.error(f"Error clocking in: {e}")
        return jsonify({'error': str(e)}), 500


@clock_bp.route('/clockout', methods=['POST'])
@require_api_key(['write'])
def api_clockout(guild_id: int):
    """Clock out a user via API"""
    if g.api_key_data['guild_id'] != guild_id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    
    if not data or 'user_id' not in data:
        return jsonify({
            'error': 'Missing required fields',
            'message': 'user_id is required'
        }), 400
    
    user_id = data['user_id']
    
    try:
        async def clockout():
            _, clock = await get_tracker_and_clock()
            return await clock.clock_out(guild_id, user_id)
        
        result = run_async(clockout())
        
        if result['success']:
            return jsonify({
                'success': True,
                'category': result['category'],
                'duration_seconds': result['session_duration'],
                'duration_formatted': result['session_duration_formatted'],
                'session_id': result['session_id']
            }), 200
        else:
            return jsonify(result), 400
        
    except Exception as e:
        logger.error(f"Error clocking out: {e}")
        return jsonify({'error': str(e)}), 500


@clock_bp.route('/active', methods=['GET'])
@require_api_key(['read'])
def get_active_sessions(guild_id: int):
    """Get all active sessions"""
    if g.api_key_data['guild_id'] != guild_id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        async def get_sessions():
            tracker, _ = await get_tracker_and_clock()
            
            pattern = f"active_session:{guild_id}:*"
            cursor = 0
            sessions = []
            
            while True:
                cursor, keys = await tracker.redis.scan(cursor, match=pattern, count=100)
                
                for key in keys:
                    session_data = await tracker.redis.get(key)
                    if session_data:
                        session = json.loads(session_data)
                        start_time = datetime.fromisoformat(session['start_time'])
                        duration = int((datetime.now() - start_time).total_seconds())
                        
                        sessions.append({
                            'user_id': session['user_id'],
                            'category': session['category'],
                            'start_time': session['start_time'],
                            'duration_seconds': duration,
                            'session_id': session['session_id']
                        })
                
                if cursor == 0:
                    break
            
            return sessions
        
        sessions = run_async(get_sessions())
        return jsonify({
            'guild_id': guild_id,
            'active_count': len(sessions),
            'sessions': sessions
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500