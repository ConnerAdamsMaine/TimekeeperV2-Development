from flask import request, jsonify, g, current_app
from functools import wraps
import hashlib
import secrets
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum

from Utils.timekeeper import get_shared_tracker

logger = logging.getLogger(__name__)


class APITier(Enum):
    """API Access Tiers"""
    SUPPORTER = 1    # Basic read-only
    PREMIUM = 2      # Read + limited write
    ENTERPRISE = 3   # Full access + sub-keys
    ADMIN = 4        # Unrestricted god-mode


class TierConfig:
    """Configuration for each tier"""
    CONFIGS = {
        APITier.SUPPORTER: {
            'name': 'Supporter',
            'rate_limit': 20,  # requests per minute
            'permissions': ['read:basic'],
            'allowed_endpoints': [
                'categories:read',
                'leaderboard:read',
                'users:read:basic',
                'export:basic'
            ],
            'features': {
                'analytics': False,
                'webhooks': False,
                'bulk_operations': False,
                'sub_keys': False
            }
        },
        APITier.PREMIUM: {
            'name': 'Premium',
            'rate_limit': 60,
            'permissions': ['read:full', 'write:limited'],
            'allowed_endpoints': [
                'categories:read',
                'leaderboard:read',
                'users:read:full',
                'clock:admin_write',  # Can clock in/out admin users
                'export:full',
                'analytics:basic'
            ],
            'features': {
                'analytics': True,
                'webhooks': False,
                'bulk_operations': False,
                'sub_keys': False
            }
        },
        APITier.ENTERPRISE: {
            'name': 'Enterprise',
            'rate_limit': 120,
            'permissions': ['read:full', 'write:full'],
            'allowed_endpoints': [
                'categories:full',
                'leaderboard:read',
                'users:full',
                'clock:full',
                'export:full',
                'analytics:full',
                'webhooks:full',
                'config:full',
                'permissions:full'
            ],
            'features': {
                'analytics': True,
                'webhooks': True,
                'bulk_operations': True,
                'sub_keys': True,
                'max_sub_keys': 10
            }
        },
        APITier.ADMIN: {
            'name': 'Admin',
            'rate_limit': None,  # Unrestricted
            'permissions': ['*'],  # All permissions
            'allowed_endpoints': ['*'],  # All endpoints
            'features': {
                'analytics': True,
                'webhooks': True,
                'bulk_operations': True,
                'sub_keys': True,
                'max_sub_keys': None,  # Unlimited
                'cross_guild_access': True,
                'encryption_required': True,
                'audit_logging': True
            }
        }
    }
    
    @classmethod
    def get_config(cls, tier: APITier) -> Dict[str, Any]:
        """Get configuration for a tier"""
        return cls.CONFIGS[tier]
    
    @classmethod
    def can_access_endpoint(cls, tier: APITier, endpoint: str) -> bool:
        """Check if tier can access an endpoint"""
        config = cls.get_config(tier)
        allowed = config['allowed_endpoints']
        
        if '*' in allowed:
            return True
        
        # Check exact match or wildcard match
        for allowed_endpoint in allowed:
            if allowed_endpoint == endpoint or allowed_endpoint.endswith(':full'):
                base = allowed_endpoint.split(':')[0]
                if endpoint.startswith(base):
                    return True
        
        return False


class APIAuth:
    """Enhanced API Authentication with tier system"""
    
    @staticmethod
    async def generate_api_key(
        guild_id: int,
        admin_user_id: int,
        tier: APITier = APITier.SUPPORTER,
        permissions: List[str] = None,
        redis_client=None,
        parent_key_hash: str = None,
        sub_key_name: str = None
    ) -> Dict[str, Any]:
        """Generate a new API key with tier support"""
        if not redis_client:
            tracker, _ = await get_shared_tracker()
            redis_client = tracker.redis
        
        # Validate tier
        if not isinstance(tier, APITier):
            tier = APITier.SUPPORTER
        
        tier_config = TierConfig.get_config(tier)
        
        # Check if this is a sub-key for Enterprise tier
        is_sub_key = parent_key_hash is not None
        
        if is_sub_key:
            # Verify parent key is Enterprise or Admin
            parent_data = await redis_client.hgetall(f"api_key:{parent_key_hash}")
            if not parent_data:
                raise ValueError("Parent key not found")
            
            parent_tier = APITier[parent_data.get(b'tier', b'SUPPORTER').decode()]
            parent_config = TierConfig.get_config(parent_tier)
            
            if not parent_config['features'].get('sub_keys'):
                raise ValueError("Parent tier does not support sub-keys")
            
            # Check sub-key limits
            sub_keys_key = f"sub_keys:{parent_key_hash}"
            sub_key_count = await redis_client.scard(sub_keys_key)
            max_sub_keys = parent_config['features'].get('max_sub_keys')
            
            if max_sub_keys and sub_key_count >= max_sub_keys:
                raise ValueError(f"Maximum sub-keys ({max_sub_keys}) reached")
        
        # Generate secure random key
        prefix = "tk_sub" if is_sub_key else "tk"
        api_key = f"{prefix}_{secrets.token_urlsafe(32)}"
        
        # Hash for storage
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        # Store key metadata
        key_data = {
            'guild_id': guild_id,
            'created_by': admin_user_id,
            'created_at': datetime.now().isoformat(),
            'tier': tier.name,
            'permissions': json.dumps(permissions or tier_config['permissions']),
            'rate_limit': tier_config['rate_limit'],
            'enabled': 'true',
            'last_used': '',
            'total_requests': 0,
            'is_sub_key': str(is_sub_key).lower(),
            'parent_key': parent_key_hash or '',
            'sub_key_name': sub_key_name or ''
        }
        
        key_storage_key = f"api_key:{key_hash}"
        await redis_client.hset(key_storage_key, mapping=key_data)
        await redis_client.expire(key_storage_key, 86400 * 365)  # 1 year
        
        # Store guild -> key mapping
        guild_keys_key = f"api_keys:guild:{guild_id}"
        await redis_client.sadd(guild_keys_key, key_hash)
        
        # If sub-key, store in parent's sub-keys set
        if is_sub_key:
            sub_keys_key = f"sub_keys:{parent_key_hash}"
            await redis_client.sadd(sub_keys_key, key_hash)
        
        logger.info(f"Generated {tier.name} API key for guild {guild_id} (sub_key: {is_sub_key})")
        
        return {
            'api_key': api_key,
            'key_hash': key_hash,
            'tier': tier.name,
            'tier_config': tier_config,
            'is_sub_key': is_sub_key,
            'parent_key': parent_key_hash if is_sub_key else None
        }
    
    @staticmethod
    async def validate_api_key(api_key: str, redis_client=None) -> Optional[Dict[str, Any]]:
        """Validate an API key and return its metadata with tier info"""
        if not api_key or not api_key.startswith('tk'):
            return None
        
        if not redis_client:
            tracker, _ = await get_shared_tracker()
            redis_client = tracker.redis
        
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        key_storage_key = f"api_key:{key_hash}"
        key_data = await redis_client.hgetall(key_storage_key)
        
        if not key_data or key_data.get(b'enabled', b'true').decode() != 'true':
            return None
        
        # Get tier info
        tier_name = key_data.get(b'tier', b'SUPPORTER').decode()
        tier = APITier[tier_name]
        tier_config = TierConfig.get_config(tier)
        
        # Check if this is a sub-key
        is_sub_key = key_data.get(b'is_sub_key', b'false').decode() == 'true'
        parent_key_hash = key_data.get(b'parent_key', b'').decode()
        
        # If sub-key, get parent's rate limit pool
        rate_limit_key_hash = parent_key_hash if is_sub_key else key_hash
        
        return {
            'guild_id': int(key_data.get(b'guild_id', b'0')),
            'created_by': int(key_data.get(b'created_by', b'0')),
            'tier': tier,
            'tier_name': tier_name,
            'tier_config': tier_config,
            'permissions': json.loads(key_data.get(b'permissions', b'[]')),
            'rate_limit': tier_config['rate_limit'],
            'total_requests': int(key_data.get(b'total_requests', b'0')),
            'key_hash': key_hash,
            'is_sub_key': is_sub_key,
            'parent_key_hash': parent_key_hash,
            'rate_limit_key_hash': rate_limit_key_hash,
            'sub_key_name': key_data.get(b'sub_key_name', b'').decode()
        }
    
    @staticmethod
    async def check_rate_limit(key_data: Dict[str, Any], redis_client=None) -> Dict[str, Any]:
        """Check if request is within rate limit for the tier"""
        if not redis_client:
            tracker, _ = await get_shared_tracker()
            redis_client = tracker.redis
        
        tier = key_data['tier']
        rate_limit = key_data['rate_limit']
        
        # Admin tier has no rate limit
        if tier == APITier.ADMIN or rate_limit is None:
            return {'allowed': True, 'remaining': None, 'reset_in': None}
        
        # Use parent's rate limit pool if sub-key
        rate_limit_hash = key_data['rate_limit_key_hash']
        
        import time
        current_minute = int(time.time() // 60)
        rate_key = f"rate_limit:{rate_limit_hash}:{current_minute}"
        
        count = await redis_client.incr(rate_key)
        if count == 1:
            await redis_client.expire(rate_key, 60)
        
        remaining = max(0, rate_limit - count)
        ttl = await redis_client.ttl(rate_key)
        
        return {
            'allowed': count <= rate_limit,
            'remaining': remaining,
            'reset_in': ttl,
            'limit': rate_limit,
            'current': count
        }
    
    @staticmethod
    async def update_key_usage(key_hash: str, redis_client=None):
        """Update key usage statistics"""
        if not redis_client:
            tracker, _ = await get_shared_tracker()
            redis_client = tracker.redis
        
        key_storage_key = f"api_key:{key_hash}"
        await redis_client.hincrby(key_storage_key, 'total_requests', 1)
        await redis_client.hset(key_storage_key, 'last_used', datetime.now().isoformat())
    
    @staticmethod
    async def list_sub_keys(parent_key_hash: str, redis_client=None) -> List[Dict[str, Any]]:
        """List all sub-keys for a parent key"""
        if not redis_client:
            tracker, _ = await get_shared_tracker()
            redis_client = tracker.redis
        
        sub_keys_key = f"sub_keys:{parent_key_hash}"
        sub_key_hashes = await redis_client.smembers(sub_keys_key)
        
        sub_keys = []
        for sub_key_hash in sub_key_hashes:
            key_data = await redis_client.hgetall(f"api_key:{sub_key_hash.decode()}")
            if key_data:
                sub_keys.append({
                    'key_hash': sub_key_hash.decode(),
                    'name': key_data.get(b'sub_key_name', b'').decode(),
                    'created_at': key_data.get(b'created_at', b'').decode(),
                    'enabled': key_data.get(b'enabled', b'true').decode() == 'true',
                    'total_requests': int(key_data.get(b'total_requests', b'0'))
                })
        
        return sub_keys
    
    @staticmethod
    async def revoke_key(key_hash: str, redis_client=None) -> bool:
        """Revoke an API key (and all its sub-keys if applicable)"""
        if not redis_client:
            tracker, _ = await get_shared_tracker()
            redis_client = tracker.redis
        
        key_storage_key = f"api_key:{key_hash}"
        
        # Check if it's a parent key with sub-keys
        sub_keys = await APIAuth.list_sub_keys(key_hash, redis_client)
        
        # Revoke all sub-keys first
        for sub_key in sub_keys:
            await redis_client.hset(f"api_key:{sub_key['key_hash']}", 'enabled', 'false')
        
        # Revoke the main key
        await redis_client.hset(key_storage_key, 'enabled', 'false')
        
        logger.info(f"Revoked API key {key_hash} and {len(sub_keys)} sub-keys")
        return True


def require_api_key(required_permissions: List[str] = None, min_tier: APITier = None):
    """Enhanced decorator to require valid API key with tier checking"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from Utils.timekeeper import get_shared_tracker
            import asyncio
            
            def run_async(coro):
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    return loop.run_until_complete(coro)
                finally:
                    loop.close()
            
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
            
            # Check minimum tier requirement
            if min_tier and key_data['tier'].value < min_tier.value:
                return jsonify({
                    'error': 'Insufficient tier',
                    'message': f'This endpoint requires {min_tier.name} tier or higher',
                    'your_tier': key_data['tier_name'],
                    'required_tier': min_tier.name,
                    'code': 'AUTH_004'
                }), 403
            
            # Check endpoint permission
            endpoint = request.endpoint
            if not TierConfig.can_access_endpoint(key_data['tier'], endpoint):
                return jsonify({
                    'error': 'Endpoint not available',
                    'message': f'Your tier does not have access to this endpoint',
                    'tier': key_data['tier_name'],
                    'endpoint': endpoint,
                    'code': 'AUTH_005'
                }), 403
            
            # Check specific permissions
            if required_permissions:
                key_permissions = key_data['permissions']
                if '*' not in key_permissions and not any(perm in key_permissions for perm in required_permissions):
                    return jsonify({
                        'error': 'Insufficient permissions',
                        'message': f'Required: {", ".join(required_permissions)}',
                        'your_permissions': key_permissions,
                        'code': 'AUTH_003'
                    }), 403
            
            # Check rate limit
            rate_limit_result = run_async(APIAuth.check_rate_limit(key_data))
            
            if not rate_limit_result['allowed']:
                return jsonify({
                    'error': 'Rate limit exceeded',
                    'message': f'Limit: {rate_limit_result["limit"]} requests/minute',
                    'remaining': 0,
                    'reset_in': rate_limit_result['reset_in'],
                    'tier': key_data['tier_name'],
                    'code': 'RATE_001'
                }), 429
            
            # Update usage
            run_async(APIAuth.update_key_usage(key_data['key_hash']))
            
            # Store in Flask g object
            g.api_key_data = key_data
            g.rate_limit = rate_limit_result
            
            # Add rate limit headers
            response = f(*args, **kwargs)
            if isinstance(response, tuple):
                response_obj, status_code = response[0], response[1]
            else:
                response_obj = response
                status_code = 200
            
            if hasattr(response_obj, 'headers'):
                if rate_limit_result['limit']:
                    response_obj.headers['X-RateLimit-Limit'] = str(rate_limit_result['limit'])
                    response_obj.headers['X-RateLimit-Remaining'] = str(rate_limit_result['remaining'])
                    response_obj.headers['X-RateLimit-Reset'] = str(rate_limit_result['reset_in'])
                response_obj.headers['X-API-Tier'] = key_data['tier_name']
            
            return response_obj, status_code
        
        return decorated_function
    return decorator


def require_tier(min_tier: APITier):
    """Decorator to require specific tier"""
    return require_api_key(min_tier=min_tier)