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


from flask import Flask, request, jsonify, g
from flask_cors import CORS
from functools import wraps
import asyncio
import logging
import os
import time
import hashlib
import secrets
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import redis.asyncio as redis
from dotenv import load_dotenv

# Import the existing tracker system
import sys
sys.path.append('..')
from Utils.timekeeper import get_shared_tracker, ValidationError, CategoryError, PermissionError

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
app.config['JSON_SORT_KEYS'] = False

# Enable CORS with restrictions
CORS(app, resources={
    r"/api/*": {
        "origins": os.getenv("ALLOWED_ORIGINS", "*").split(","),
        "methods": ["GET", "POST", "PUT", "DELETE", "PATCH"],
        "allow_headers": ["Content-Type", "Authorization", "X-API-Key"]
    }
})

# Global tracker instance
tracker = None
clock = None
redis_client = None


# ============================================================================
# INITIALIZATION
# ============================================================================

async def init_tracker():
    """Initialize the tracker system"""
    global tracker, clock, redis_client
    
    if not tracker:
        try:
            tracker, clock = await get_shared_tracker()
            redis_client = tracker.redis
            logger.info("Premium API connected to tracker system")
        except Exception as e:
            logger.error(f"Failed to initialize tracker: {e}")
            raise


def run_async(coro):
    """Helper to run async functions in Flask"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ============================================================================
# AUTHENTICATION & RATE LIMITING
# ============================================================================

class APIAuth:
    """API Authentication and rate limiting"""
    
    @staticmethod
    async def generate_api_key(guild_id: int, admin_user_id: int, permissions: List[str] = None) -> str:
        """Generate a new API key for a guild"""
        # Generate secure random key
        api_key = f"tk_{secrets.token_urlsafe(32)}"
        
        # Hash for storage
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        # Store key metadata
        key_data = {
            'guild_id': guild_id,
            'created_by': admin_user_id,
            'created_at': datetime.now().isoformat(),
            'permissions': json.dumps(permissions or ['read', 'write', 'admin']),
            'rate_limit': 1000,  # requests per hour
            'enabled': 'true',
            'last_used': '',
            'total_requests': 0
        }
        
        key_storage_key = f"api_key:{key_hash}"
        await redis_client.hset(key_storage_key, mapping=key_data)
        await redis_client.expire(key_storage_key, 86400 * 365)  # 1 year expiry
        
        # Store guild -> key mapping
        guild_keys_key = f"api_keys:guild:{guild_id}"
        await redis_client.sadd(guild_keys_key, key_hash)
        
        logger.info(f"Generated API key for guild {guild_id} by user {admin_user_id}")
        
        return api_key
    
    @staticmethod
    async def validate_api_key(api_key: str) -> Optional[Dict[str, Any]]:
        """Validate an API key and return its metadata"""
        if not api_key or not api_key.startswith('tk_'):
            return None
        
        # Hash the key
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        # Get key data
        key_storage_key = f"api_key:{key_hash}"
        key_data = await redis_client.hgetall(key_storage_key)
        
        if not key_data:
            return None
        
        # Check if enabled
        if key_data.get(b'enabled', b'true').decode() != 'true':
            return None
        
        # Parse and return
        return {
            'guild_id': int(key_data.get(b'guild_id', b'0')),
            'created_by': int(key_data.get(b'created_by', b'0')),
            'permissions': json.loads(key_data.get(b'permissions', b'[]')),
            'rate_limit': int(key_data.get(b'rate_limit', b'1000')),
            'total_requests': int(key_data.get(b'total_requests', b'0')),
            'key_hash': key_hash
        }
    
    @staticmethod
    async def check_rate_limit(key_hash: str, rate_limit: int) -> bool:
        """Check if request is within rate limit"""
        rate_key = f"rate_limit:{key_hash}:{int(time.time() // 3600)}"
        
        # Increment counter
        count = await redis_client.incr(rate_key)
        
        # Set expiry on first request
        if count == 1:
            await redis_client.expire(rate_key, 3600)
        
        return count <= rate_limit
    
    @staticmethod
    async def update_key_usage(key_hash: str):
        """Update key usage statistics"""
        key_storage_key = f"api_key:{key_hash}"
        await redis_client.hincrby(key_storage_key, 'total_requests', 1)
        await redis_client.hset(key_storage_key, 'last_used', datetime.now().isoformat())


def require_api_key(required_permissions: List[str] = None):
    """Decorator to require valid API key"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get API key from header
            api_key = request.headers.get('X-API-Key')
            
            if not api_key:
                return jsonify({
                    'error': 'Missing API key',
                    'message': 'X-API-Key header is required',
                    'code': 'AUTH_001'
                }), 401
            
            # Validate key
            key_data = run_async(APIAuth.validate_api_key(api_key))
            
            if not key_data:
                return jsonify({
                    'error': 'Invalid API key',
                    'message': 'The provided API key is invalid or expired',
                    'code': 'AUTH_002'
                }), 401
            
            # Check permissions
            if required_permissions:
                key_permissions = key_data['permissions']
                if not any(perm in key_permissions for perm in required_permissions):
                    return jsonify({
                        'error': 'Insufficient permissions',
                        'message': f'This operation requires one of: {", ".join(required_permissions)}',
                        'code': 'AUTH_003'
                    }), 403
            
            # Check rate limit
            if not run_async(APIAuth.check_rate_limit(key_data['key_hash'], key_data['rate_limit'])):
                return jsonify({
                    'error': 'Rate limit exceeded',
                    'message': f'Rate limit of {key_data["rate_limit"]} requests per hour exceeded',
                    'code': 'RATE_001'
                }), 429
            
            # Update usage
            run_async(APIAuth.update_key_usage(key_data['key_hash']))
            
            # Store key data in Flask g object
            g.api_key_data = key_data
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


# ============================================================================
# API ENDPOINTS - AUTHENTICATION
# ============================================================================

@app.route('/api/v1/auth/generate', methods=['POST'])
def generate_api_key():
    """
    Generate a new API key
    Requires Discord admin authentication or master key
    """
    data = request.get_json()
    
    # Validate request
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    guild_id = data.get('guild_id')
    admin_user_id = data.get('admin_user_id')
    master_key = data.get('master_key')
    permissions = data.get('permissions', ['read', 'write'])
    
    if not guild_id or not admin_user_id:
        return jsonify({
            'error': 'Missing required fields',
            'message': 'guild_id and admin_user_id are required'
        }), 400
    
    # Verify master key
    if master_key != os.getenv('API_MASTER_KEY'):
        return jsonify({
            'error': 'Unauthorized',
            'message': 'Invalid master key'
        }), 401
    
    try:
        # Generate key
        api_key = run_async(APIAuth.generate_api_key(guild_id, admin_user_id, permissions))
        
        return jsonify({
            'success': True,
            'api_key': api_key,
            'guild_id': guild_id,
            'permissions': permissions,
            'rate_limit': 1000,
            'expires': 'Never (1 year renewable)',
            'warning': 'Store this key securely. It will not be shown again.'
        }), 201
        
    except Exception as e:
        logger.error(f"Error generating API key: {e}")
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500


# ============================================================================
# API ENDPOINTS - STATUS & INFO
# ============================================================================

@app.route('/api/v1/status', methods=['GET'])
def api_status():
    """Get API status and version info"""
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


@app.route('/api/v1/guild/<int:guild_id>/status', methods=['GET'])
@require_api_key(['read'])
def guild_status(guild_id: int):
    """Get comprehensive guild status"""
    # Verify API key has access to this guild
    if g.api_key_data['guild_id'] != guild_id:
        return jsonify({
            'error': 'Unauthorized',
            'message': 'API key does not have access to this guild'
        }), 403
    
    try:
        # Get verbose status
        verbose = request.args.get('verbose', 'false').lower() == 'true'
        
        async def get_status():
            # Get server totals
            server_key = f"server_times:{guild_id}"
            server_data = await redis_client.hgetall(server_key)
            
            total_seconds = 0
            categories = {}
            
            if server_data:
                total_seconds = int(server_data.get(b'total', b'0'))
                for key, value in server_data.items():
                    key_str = key.decode('utf-8')
                    if key_str != 'total':
                        categories[key_str] = int(value)
            
            # Count active users
            pattern = f"user_times:{guild_id}:*"
            cursor = 0
            user_count = 0
            
            while cursor != 0 or user_count == 0:
                cursor, keys = await redis_client.scan(cursor, match=pattern, count=100)
                user_count += len(keys)
                if cursor == 0:
                    break
            
            # Count currently clocked in
            active_pattern = f"active_session:{guild_id}:*"
            cursor = 0
            active_count = 0
            active_sessions = []
            
            while cursor != 0 or active_count == 0:
                cursor, keys = await redis_client.scan(cursor, match=active_pattern, count=100)
                active_count += len(keys)
                
                if verbose:
                    for key in keys:
                        session_data = await redis_client.get(key)
                        if session_data:
                            session = json.loads(session_data)
                            active_sessions.append({
                                'user_id': session['user_id'],
                                'category': session['category'],
                                'start_time': session['start_time'],
                                'duration_seconds': int((datetime.now() - datetime.fromisoformat(session['start_time'])).total_seconds())
                            })
                
                if cursor == 0:
                    break
            
            response = {
                'guild_id': guild_id,
                'total_time_seconds': total_seconds,
                'total_time_hours': round(total_seconds / 3600, 2),
                'total_users': user_count,
                'active_sessions': active_count,
                'categories': categories,
                'timestamp': datetime.now().isoformat()
            }
            
            if verbose:
                response['active_session_details'] = active_sessions
                
                # Get category list
                category_list = await tracker.list_categories(guild_id)
                response['configured_categories'] = list(category_list)
            
            return response
        
        status_data = run_async(get_status())
        
        return jsonify(status_data), 200
        
    except Exception as e:
        logger.error(f"Error getting guild status: {e}")
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500


# ============================================================================
# API ENDPOINTS - USER MANAGEMENT
# ============================================================================

@app.route('/api/v1/guild/<int:guild_id>/users', methods=['GET'])
@require_api_key(['read'])
def list_users(guild_id: int):
    """List all users with time tracking data"""
    if g.api_key_data['guild_id'] != guild_id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        async def get_users():
            users = []
            pattern = f"user_times:{guild_id}:*"
            cursor = 0
            
            while cursor != 0 or len(users) == 0:
                cursor, keys = await redis_client.scan(cursor, match=pattern, count=100)
                
                for key in keys:
                    user_id = int(key.decode().split(':')[-1])
                    user_data = await redis_client.hgetall(key)
                    
                    if user_data:
                        total_seconds = int(user_data.get(b'total', b'0'))
                        
                        users.append({
                            'user_id': user_id,
                            'total_seconds': total_seconds,
                            'total_hours': round(total_seconds / 3600, 2)
                        })
                
                if cursor == 0:
                    break
            
            # Sort by total time
            users.sort(key=lambda x: x['total_seconds'], reverse=True)
            
            return users
        
        users_data = run_async(get_users())
        
        return jsonify({
            'guild_id': guild_id,
            'user_count': len(users_data),
            'users': users_data
        }), 200
        
    except Exception as e:
        logger.error(f"Error listing users: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/guild/<int:guild_id>/users/<int:user_id>', methods=['GET'])
@require_api_key(['read'])
def get_user(guild_id: int, user_id: int):
    """Get detailed user data"""
    if g.api_key_data['guild_id'] != guild_id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        async def get_user_data():
            return await tracker.get_user_times(guild_id, user_id, include_metadata=True)
        
        user_data = run_async(get_user_data())
        
        return jsonify({
            'guild_id': guild_id,
            'user_id': user_id,
            'data': user_data
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting user data: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# API ENDPOINTS - CLOCK IN/OUT
# ============================================================================

@app.route('/api/v1/guild/<int:guild_id>/clockin', methods=['POST'])
@require_api_key(['write'])
def api_clockin(guild_id: int):
    """Clock in a user via API"""
    if g.api_key_data['guild_id'] != guild_id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    
    if not data or 'user_id' not in data or 'category' not in data:
        return jsonify({
            'error': 'Missing required fields',
            'message': 'user_id and category are required'
        }), 400
    
    user_id = data['user_id']
    category = data['category']
    description = data.get('description')
    
    try:
        async def clockin():
            # Use the clock manager (without Discord interaction)
            metadata = {
                'description': description,
                'source': 'api',
                'api_key': g.api_key_data['key_hash'][:8]
            }
            
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
                }
            
            # Create session
            session_id = f"api_{secrets.token_hex(8)}"
            start_time = datetime.now()
            
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
            await redis_client.setex(session_key, 86400, json.dumps(session_data))
            
            return {
                'success': True,
                'session_id': session_id,
                'category': category,
                'start_time': start_time.isoformat(),
                'user_id': user_id
            }
        
        result = run_async(clockin())
        
        if result['success']:
            return jsonify(result), 201
        else:
            return jsonify(result), 400
        
    except Exception as e:
        logger.error(f"Error clocking in user: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/guild/<int:guild_id>/clockout', methods=['POST'])
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
        result = run_async(clock.clock_out(guild_id, user_id))
        
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
        logger.error(f"Error clocking out user: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/guild/<int:guild_id>/active', methods=['GET'])
@require_api_key(['read'])
def get_active_sessions(guild_id: int):
    """Get all currently active sessions"""
    if g.api_key_data['guild_id'] != guild_id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        async def get_sessions():
            pattern = f"active_session:{guild_id}:*"
            cursor = 0
            sessions = []
            
            while cursor != 0 or len(sessions) == 0:
                cursor, keys = await redis_client.scan(cursor, match=pattern, count=100)
                
                for key in keys:
                    session_data = await redis_client.get(key)
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
        logger.error(f"Error getting active sessions: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'error': 'Not found',
        'message': 'The requested endpoint does not exist',
        'code': 'HTTP_404'
    }), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'error': 'Internal server error',
        'message': 'An unexpected error occurred',
        'code': 'HTTP_500'
    }), 500

# ============================================================================
# API ENDPOINTS - CATEGORIES
# ============================================================================

@app.route('/api/v1/guild/<int:guild_id>/categories', methods=['GET'])
@require_api_key(['read'])
def get_categories(guild_id: int):
    """Get all categories for a guild"""
    if g.api_key_data['guild_id'] != guild_id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        async def fetch_categories():
            include_metadata = request.args.get('include_metadata', 'false').lower() == 'true'
            return await tracker.list_categories(
                guild_id, 
                include_archived=False,
                include_metadata=include_metadata
            )
        
        categories = run_async(fetch_categories())
        
        return jsonify({
            'guild_id': guild_id,
            'categories': categories if isinstance(categories, dict) else list(categories)
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting categories: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/guild/<int:guild_id>/categories', methods=['POST'])
@require_api_key(['admin'])
def add_category(guild_id: int):
    """Add a new category"""
    if g.api_key_data['guild_id'] != guild_id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    
    if not data or 'name' not in data:
        return jsonify({
            'error': 'Missing required fields',
            'message': 'name is required'
        }), 400
    
    name = data['name']
    description = data.get('description')
    color = data.get('color')
    productivity_weight = data.get('productivity_weight', 1.0)
    
    try:
        async def create_category():
            return await tracker.add_category(
                guild_id,
                name,
                user_id=g.api_key_data['created_by'],
                description=description,
                color=color,
                productivity_weight=productivity_weight
            )
        
        result = run_async(create_category())
        
        if result['success']:
            return jsonify(result), 201
        else:
            return jsonify(result), 400
        
    except Exception as e:
        logger.error(f"Error adding category: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/guild/<int:guild_id>/categories/<string:category>', methods=['DELETE'])
@require_api_key(['admin'])
def remove_category(guild_id: int, category: str):
    """Remove a category"""
    if g.api_key_data['guild_id'] != guild_id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    force = request.args.get('force', 'false').lower() == 'true'
    
    try:
        async def delete_category():
            return await tracker.remove_category(
                guild_id,
                category,
                user_id=g.api_key_data['created_by'],
                force=force
            )
        
        result = run_async(delete_category())
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 400
        
    except Exception as e:
        logger.error(f"Error removing category: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# API ENDPOINTS - LEADERBOARD
# ============================================================================

@app.route('/api/v1/guild/<int:guild_id>/leaderboard', methods=['GET'])
@require_api_key(['read'])
def get_leaderboard(guild_id: int):
    """Get guild leaderboard"""
    if g.api_key_data['guild_id'] != guild_id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    category = request.args.get('category')
    limit = int(request.args.get('limit', 10))
    time_range = request.args.get('timeframe', 'all')
    
    if limit < 1 or limit > 100:
        limit = 10
    
    try:
        async def fetch_leaderboard():
            return await tracker.get_server_leaderboard(
                guild_id,
                category=category,
                limit=limit,
                time_range=time_range,
                include_stats=True
            )
        
        leaderboard = run_async(fetch_leaderboard())
        
        return jsonify({
            'guild_id': guild_id,
            'category': category or 'total',
            'timeframe': time_range,
            'count': len(leaderboard),
            'leaderboard': leaderboard
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting leaderboard: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# API ENDPOINTS - EXPORT
# ============================================================================

@app.route('/api/v1/guild/<int:guild_id>/export/<int:user_id>', methods=['GET'])
@require_api_key(['read'])
def export_user_data(guild_id: int, user_id: int):
    """Export user data in various formats"""
    if g.api_key_data['guild_id'] != guild_id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    format_type = request.args.get('format', 'json').lower()
    
    if format_type not in ['json', 'csv']:
        return jsonify({
            'error': 'Invalid format',
            'message': 'Supported formats: json, csv'
        }), 400
    
    try:
        async def get_export_data():
            # Get user times
            user_times = await tracker.get_user_times(guild_id, user_id, include_metadata=True)
            
            # Get time entries
            entries_key = f"time_entries:{guild_id}:{user_id}"
            entries_data = await redis_client.zrevrange(entries_key, 0, -1, withscores=True)
            
            entries = []
            for entry_bytes, timestamp in entries_data:
                try:
                    entry = json.loads(entry_bytes)
                    entry['timestamp'] = timestamp
                    entry['date'] = datetime.fromtimestamp(timestamp).isoformat()
                    entries.append(entry)
                except:
                    continue
            
            return {
                'user_id': user_id,
                'guild_id': guild_id,
                'export_date': datetime.now().isoformat(),
                'summary': user_times,
                'entries': entries
            }
        
        data = run_async(get_export_data())
        
        if format_type == 'json':
            return jsonify(data), 200
        
        elif format_type == 'csv':
            import io
            import csv
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Header
            writer.writerow(['Date', 'Category', 'Duration (seconds)', 'Duration (formatted)', 'Session ID'])
            
            # Data
            for entry in data['entries']:
                writer.writerow([
                    entry['date'],
                    entry['category'],
                    entry['seconds'],
                    f"{entry['seconds'] // 3600}h {(entry['seconds'] % 3600) // 60}m",
                    entry.get('session_id', 'N/A')
                ])
            
            # Summary
            writer.writerow([])
            writer.writerow(['Summary'])
            writer.writerow(['Total Time', data['summary']['total'], data['summary']['total_formatted']])
            
            output.seek(0)
            
            from flask import Response
            return Response(
                output.getvalue(),
                mimetype='text/csv',
                headers={'Content-Disposition': f'attachment; filename=timetracker_{user_id}_{datetime.now().strftime("%Y%m%d")}.csv'}
            )
        
    except Exception as e:
        logger.error(f"Error exporting data: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# API ENDPOINTS - CONFIGURATION
# ============================================================================

@app.route('/api/v1/guild/<int:guild_id>/config', methods=['GET'])
@require_api_key(['read'])
def get_config(guild_id: int):
    """Get guild configuration"""
    if g.api_key_data['guild_id'] != guild_id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        async def fetch_config():
            settings = await tracker.get_server_settings(guild_id)
            
            return {
                'timezone': settings.timezone,
                'work_hours_start': settings.work_hours_start,
                'work_hours_end': settings.work_hours_end,
                'max_session_hours': settings.max_session_hours,
                'role_prefix': settings.role_prefix,
                'auto_logout_hours': settings.auto_logout_hours,
                'analytics_enabled': settings.analytics_enabled,
                'audit_enabled': settings.audit_enabled,
                'backup_enabled': settings.backup_enabled
            }
        
        config = run_async(fetch_config())
        
        return jsonify({
            'guild_id': guild_id,
            'config': config
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting config: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/guild/<int:guild_id>/config', methods=['PATCH'])
@require_api_key(['admin'])
def update_config(guild_id: int):
    """Update guild configuration"""
    if g.api_key_data['guild_id'] != guild_id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    
    if not data:
        return jsonify({
            'error': 'No data provided',
            'message': 'Request body must contain configuration updates'
        }), 400
    
    try:
        async def update_settings():
            settings = await tracker.get_server_settings(guild_id)
            
            # Update allowed fields
            allowed_fields = [
                'timezone', 'work_hours_start', 'work_hours_end',
                'max_session_hours', 'role_prefix', 'auto_logout_hours',
                'analytics_enabled', 'audit_enabled', 'backup_enabled'
            ]
            
            updated_fields = []
            for field in allowed_fields:
                if field in data:
                    setattr(settings, field, data[field])
                    updated_fields.append(field)
            
            # Save settings
            await tracker._save_server_settings(guild_id, settings)
            
            return {
                'success': True,
                'updated_fields': updated_fields,
                'message': f'Updated {len(updated_fields)} configuration fields'
            }
        
        result = run_async(update_settings())
        
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Error updating config: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# API ENDPOINTS - PERMISSIONS
# ============================================================================

@app.route('/api/v1/guild/<int:guild_id>/permissions', methods=['GET'])
@require_api_key(['admin'])
def get_permissions(guild_id: int):
    """Get guild permissions"""
    if g.api_key_data['guild_id'] != guild_id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        async def fetch_permissions():
            perms_key = f"permissions:{guild_id}"
            perms_data = await redis_client.hgetall(perms_key)
            
            return {
                "required_roles": json.loads(perms_data.get(b"required_roles", b"[]")),
                "suspended_users": json.loads(perms_data.get(b"suspended_users", b"[]")),
                "admin_roles": json.loads(perms_data.get(b"admin_roles", b"[]")),
                "enabled": perms_data.get(b"enabled", b"true").decode() == "true"
            }
        
        permissions = run_async(fetch_permissions())
        
        return jsonify({
            'guild_id': guild_id,
            'permissions': permissions
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting permissions: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/guild/<int:guild_id>/permissions/suspend', methods=['POST'])
@require_api_key(['admin'])
def suspend_user(guild_id: int):
    """Suspend a user from time tracking"""
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
        async def suspend():
            return await tracker.suspend_user(guild_id, user_id)
        
        success = run_async(suspend())
        
        if success:
            return jsonify({
                'success': True,
                'message': f'User {user_id} suspended',
                'user_id': user_id
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'User already suspended',
                'user_id': user_id
            }), 400
        
    except Exception as e:
        logger.error(f"Error suspending user: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/guild/<int:guild_id>/permissions/unsuspend', methods=['POST'])
@require_api_key(['admin'])
def unsuspend_user(guild_id: int):
    """Unsuspend a user"""
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
        async def unsuspend():
            return await tracker.unsuspend_user(guild_id, user_id)
        
        success = run_async(unsuspend())
        
        if success:
            return jsonify({
                'success': True,
                'message': f'User {user_id} unsuspended',
                'user_id': user_id
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'User not suspended',
                'user_id': user_id
            }), 400
        
    except Exception as e:
        logger.error(f"Error unsuspending user: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# API ENDPOINTS - ANALYTICS & INSIGHTS
# ============================================================================

@app.route('/api/v1/guild/<int:guild_id>/analytics/insights/<int:user_id>', methods=['GET'])
@require_api_key(['read'])
def get_user_insights(guild_id: int, user_id: int):
    """Get advanced productivity insights for a user"""
    if g.api_key_data['guild_id'] != guild_id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        async def fetch_insights():
            if not tracker.analytics:
                return {
                    'error': 'Analytics not enabled',
                    'message': 'Advanced analytics are not available'
                }
            
            return await tracker.analytics.get_advanced_insights(guild_id, user_id)
        
        insights = run_async(fetch_insights())
        
        if insights.get('error'):
            return jsonify(insights), 400
        
        return jsonify({
            'guild_id': guild_id,
            'user_id': user_id,
            'insights': insights
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting insights: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/guild/<int:guild_id>/analytics/productivity/<int:user_id>', methods=['GET'])
@require_api_key(['read'])
def get_productivity_score(guild_id: int, user_id: int):
    """Get productivity score for a user"""
    if g.api_key_data['guild_id'] != guild_id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    days = int(request.args.get('days', 7))
    use_ml = request.args.get('use_ml', 'true').lower() == 'true'
    
    try:
        async def fetch_score():
            if not tracker.analytics:
                return {'error': 'Analytics not enabled'}
            
            score = await tracker.analytics.calculate_productivity_score(
                guild_id, user_id, days=days, use_ml=use_ml
            )
            
            return {
                'score': round(score * 100, 2),
                'grade': tracker.analytics._score_to_grade(score),
                'days_analyzed': days,
                'ml_enhanced': use_ml
            }
        
        result = run_async(fetch_score())
        
        if result.get('error'):
            return jsonify(result), 400
        
        return jsonify({
            'guild_id': guild_id,
            'user_id': user_id,
            'productivity': result
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting productivity score: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# API ENDPOINTS - WEBHOOKS
# ============================================================================

@app.route('/api/v1/guild/<int:guild_id>/webhooks', methods=['POST'])
@require_api_key(['admin'])
def create_webhook(guild_id: int):
    """Create a webhook for event notifications"""
    if g.api_key_data['guild_id'] != guild_id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    
    if not data or 'url' not in data or 'events' not in data:
        return jsonify({
            'error': 'Missing required fields',
            'message': 'url and events are required'
        }), 400
    
    webhook_url = data['url']
    events = data['events']  # List of events: ['clockin', 'clockout', 'category_added', etc.]
    
    try:
        async def store_webhook():
            webhook_id = secrets.token_hex(16)
            
            webhook_data = {
                'id': webhook_id,
                'guild_id': guild_id,
                'url': webhook_url,
                'events': json.dumps(events),
                'created_at': datetime.now().isoformat(),
                'enabled': 'true',
                'secret': secrets.token_hex(32)
            }
            
            webhook_key = f"webhook:{guild_id}:{webhook_id}"
            await redis_client.hset(webhook_key, mapping=webhook_data)
            
            # Add to guild's webhook list
            await redis_client.sadd(f"webhooks:guild:{guild_id}", webhook_id)
            
            return {
                'webhook_id': webhook_id,
                'url': webhook_url,
                'events': events,
                'secret': webhook_data['secret']
            }
        
        webhook = run_async(store_webhook())
        
        return jsonify({
            'success': True,
            'webhook': webhook,
            'message': 'Webhook created successfully. Use the secret to verify webhook signatures.'
        }), 201
        
    except Exception as e:
        logger.error(f"Error creating webhook: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# STARTUP
# ============================================================================

@app.before_request
def before_request():
    """Initialize tracker before first request"""
    global tracker, clock, redis_client
    
    if not tracker:
        run_async(init_tracker())


if __name__ == '__main__':
    # Initialize tracker
    run_async(init_tracker())
    
    # Run Flask app
    port = int(os.getenv('API_PORT', 5000))
    debug = os.getenv('FLASK_ENV', 'production') == 'development'
    
    logger.info(f"Starting Premium API on port {port}")
    app.run(host='0.0.0.0', port=port, debug=debug)