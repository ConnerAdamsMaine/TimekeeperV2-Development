# premium/API/middleware/auth.py
# ============================================================================
# Authentication middleware for Premium API
# ============================================================================

from flask import request, jsonify, g, current_app
from functools import wraps
import hashlib
import secrets
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

from ...Utils.timekeeper import get_shared_tracker

logger = logging.getLogger(__name__)


class APIAuth:
    """API Authentication and rate limiting"""
    
    @staticmethod
    async def generate_api_key(guild_id: int, admin_user_id: int, 
                              permissions: List[str] = None, 
                              redis_client=None) -> str:
        """Generate a new API key for a guild"""
        if not redis_client:
            tracker, _ = await get_shared_tracker()
            redis_client = tracker.redis
        
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
            'rate_limit': 1000,
            'enabled': 'true',
            'last_used': '',
            'total_requests': 0
        }
        
        key_storage_key = f"api_key:{key_hash}"
        await redis_client.hset(key_storage_key, mapping=key_data)
        await redis_client.expire(key_storage_key, 86400 * 365)
        
        # Store guild -> key mapping
        guild_keys_key = f"api_keys:guild:{guild_id}"
        await redis_client.sadd(guild_keys_key, key_hash)
        
        logger.info(f"Generated API key for guild {guild_id}")
        return api_key
    
    @staticmethod
    async def validate_api_key(api_key: str, redis_client=None) -> Optional[Dict[str, Any]]:
        """Validate an API key and return its metadata"""
        if not api_key or not api_key.startswith('tk_'):
            return None
        
        if not redis_client:
            tracker, _ = await get_shared_tracker()
            redis_client = tracker.redis
        
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        key_storage_key = f"api_key:{key_hash}"
        key_data = await redis_client.hgetall(key_storage_key)
        
        if not key_data or key_data.get(b'enabled', b'true').decode() != 'true':
            return None
        
        return {
            'guild_id': int(key_data.get(b'guild_id', b'0')),
            'created_by': int(key_data.get(b'created_by', b'0')),
            'permissions': json.loads(key_data.get(b'permissions', b'[]')),
            'rate_limit': int(key_data.get(b'rate_limit', b'1000')),
            'total_requests': int(key_data.get(b'total_requests', b'0')),
            'key_hash': key_hash
        }
    
    @staticmethod
    async def check_rate_limit(key_hash: str, rate_limit: int, redis_client=None) -> bool:
        """Check if request is within rate limit"""
        if not redis_client:
            tracker, _ = await get_shared_tracker()
            redis_client = tracker.redis
        
        import time
        rate_key = f"rate_limit:{key_hash}:{int(time.time() // 3600)}"
        
        count = await redis_client.incr(rate_key)
        if count == 1:
            await redis_client.expire(rate_key, 3600)
        
        return count <= rate_limit
    
    @staticmethod
    async def update_key_usage(key_hash: str, redis_client=None):
        """Update key usage statistics"""
        if not redis_client:
            tracker, _ = await get_shared_tracker()
            redis_client = tracker.redis
        
        key_storage_key = f"api_key:{key_hash}"
        await redis_client.hincrby(key_storage_key, 'total_requests', 1)
        await redis_client.hset(key_storage_key, 'last_used', datetime.now().isoformat())


def require_api_key(required_permissions: List[str] = None):
    """Decorator to require valid API key"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from ...utils.helpers import run_async
            
            # Get API key from header
            api_key = request.headers.get('X-API-Key')
            
            if not api_key:
                return jsonify({
                    'error': 'Missing API key',
                    'message': 'X-API-Key header is required',
                    'code': 'AUTH_001'
                }), 401
            
            # Get tracker from bot
            bot = current_app.config.get('BOT')
            if not bot:
                return jsonify({
                    'error': 'Bot not initialized',
                    'code': 'SYS_001'
                }), 500
            
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
                        'message': f'Required: {", ".join(required_permissions)}',
                        'code': 'AUTH_003'
                    }), 403
            
            # Check rate limit
            if not run_async(APIAuth.check_rate_limit(key_data['key_hash'], key_data['rate_limit'])):
                return jsonify({
                    'error': 'Rate limit exceeded',
                    'message': f'Limit: {key_data["rate_limit"]} requests/hour',
                    'code': 'RATE_001'
                }), 429
            
            # Update usage
            run_async(APIAuth.update_key_usage(key_data['key_hash']))
            
            # Store in Flask g object
            g.api_key_data = key_data
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator