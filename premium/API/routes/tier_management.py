from flask import Blueprint, request, jsonify, g
import os
import logging
from datetime import datetime
import redis

from ..middleware.auth import APIAuth, APITier, TierConfig, require_api_key, require_tier
from ..utils.helpers import run_async

logger = logging.getLogger(__name__)

tier_mgmt_bp = Blueprint('tier_management', __name__)


# ============================================================================
# TIER INFORMATION
# ============================================================================

@tier_mgmt_bp.route('/tiers', methods=['GET'])
def list_tiers():
    """List all available tiers and their features"""
    tiers = {}
    for tier in APITier:
        config = TierConfig.get_config(tier)
        tiers[tier.name] = {
            'name': config['name'],
            'tier_level': tier.value,
            'rate_limit': config['rate_limit'],
            'rate_limit_display': f"{config['rate_limit']} requests/minute" if config['rate_limit'] else "Unlimited",
            'permissions': config['permissions'],
            'features': config['features'],
            'allowed_endpoints': config['allowed_endpoints'][:5] if len(config['allowed_endpoints']) > 5 else config['allowed_endpoints']
        }
    
    return jsonify({
        'tiers': tiers,
        'current_tier': g.api_key_data['tier_name'] if hasattr(g, 'api_key_data') else None
    }), 200


@tier_mgmt_bp.route('/my-tier', methods=['GET'])
@require_api_key()
def get_my_tier():
    """Get information about your current tier"""
    tier_name = g.api_key_data['tier_name']
    tier = g.api_key_data['tier']
    tier_config = g.api_key_data['tier_config']
    
    return jsonify({
        'tier': tier_name,
        'tier_level': tier.value,
        'rate_limit': tier_config['rate_limit'],
        'rate_limit_display': f"{tier_config['rate_limit']} requests/minute" if tier_config['rate_limit'] else "Unlimited",
        'permissions': g.api_key_data['permissions'],
        'features': tier_config['features'],
        'usage': {
            'total_requests': g.api_key_data['total_requests'],
            'current_rate_limit': {
                'remaining': g.rate_limit['remaining'],
                'limit': g.rate_limit['limit'],
                'reset_in': g.rate_limit['reset_in']
            }
        },
        'is_sub_key': g.api_key_data['is_sub_key'],
        'parent_key': g.api_key_data['parent_key_hash'] if g.api_key_data['is_sub_key'] else None
    }), 200


# ============================================================================
# SUB-KEY MANAGEMENT (Enterprise & Admin only)
# ============================================================================

@tier_mgmt_bp.route('/sub-keys', methods=['GET'])
@require_tier(APITier.ENTERPRISE)
def list_sub_keys():
    """List all sub-keys for your API key (Enterprise+)"""
    if g.api_key_data['is_sub_key']:
        return jsonify({
            'error': 'Sub-keys cannot create their own sub-keys',
            'code': 'SUBKEY_001'
        }), 400
    
    try:
        sub_keys = run_async(APIAuth.list_sub_keys(g.api_key_data['key_hash']))
        
        return jsonify({
            'parent_key_hash': g.api_key_data['key_hash'][:16] + '...',
            'tier': g.api_key_data['tier_name'],
            'sub_keys': sub_keys,
            'count': len(sub_keys),
            'max_allowed': g.api_key_data['tier_config']['features'].get('max_sub_keys')
        }), 200
        
    except Exception as e:
        logger.error(f"Error listing sub-keys: {e}")
        return jsonify({'error': str(e)}), 500


@tier_mgmt_bp.route('/sub-keys', methods=['POST'])
@require_tier(APITier.ENTERPRISE)
def create_sub_key():
    """Create a new sub-key (Enterprise+)"""
    if g.api_key_data['is_sub_key']:
        return jsonify({
            'error': 'Sub-keys cannot create their own sub-keys',
            'code': 'SUBKEY_001'
        }), 400
    
    data = request.get_json()
    
    if not data or 'name' not in data:
        return jsonify({
            'error': 'Missing required field: name',
            'message': 'Sub-key name is required'
        }), 400
    
    sub_key_name = data['name']
    custom_permissions = data.get('permissions')  # Optional: restrict sub-key permissions
    
    # Validate permissions are subset of parent's permissions
    if custom_permissions:
        parent_permissions = set(g.api_key_data['permissions'])
        if '*' not in parent_permissions:
            requested_permissions = set(custom_permissions)
            if not requested_permissions.issubset(parent_permissions):
                return jsonify({
                    'error': 'Invalid permissions',
                    'message': 'Sub-key permissions must be a subset of parent key permissions',
                    'your_permissions': list(parent_permissions),
                    'requested': custom_permissions
                }), 400
    
    try:
        result = run_async(APIAuth.generate_api_key(
            guild_id=g.api_key_data['guild_id'],
            admin_user_id=g.api_key_data['created_by'],
            tier=g.api_key_data['tier'],
            permissions=custom_permissions,
            parent_key_hash=g.api_key_data['key_hash'],
            sub_key_name=sub_key_name
        ))
        
        return jsonify({
            'success': True,
            'sub_key': {
                'api_key': result['api_key'],
                'key_hash': result['key_hash'][:16] + '...',
                'name': sub_key_name,
                'tier': result['tier'],
                'permissions': result['tier_config']['permissions'] if not custom_permissions else custom_permissions,
                'rate_limit_note': f"Shares parent's {result['tier_config']['rate_limit']} requests/minute pool"
            },
            'warning': 'Store this key securely. It will not be shown again.',
            'note': 'This sub-key shares your rate limit pool'
        }), 201
        
    except ValueError as e:
        return jsonify({
            'error': str(e),
            'code': 'SUBKEY_002'
        }), 400
    except Exception as e:
        logger.error(f"Error creating sub-key: {e}")
        return jsonify({'error': str(e)}), 500


@tier_mgmt_bp.route('/sub-keys/<string:sub_key_hash>', methods=['DELETE'])
@require_tier(APITier.ENTERPRISE)
def revoke_sub_key(sub_key_hash: str):
    """Revoke a specific sub-key (Enterprise+)"""
    if g.api_key_data['is_sub_key']:
        return jsonify({
            'error': 'Sub-keys cannot revoke other keys',
            'code': 'SUBKEY_001'
        }), 400
    
    try:
        # Verify the sub-key belongs to this parent
        sub_keys = run_async(APIAuth.list_sub_keys(g.api_key_data['key_hash']))
        
        if not any(sk['key_hash'] == sub_key_hash for sk in sub_keys):
            return jsonify({
                'error': 'Sub-key not found or does not belong to you',
                'code': 'SUBKEY_003'
            }), 404
        
        # Revoke the sub-key
        success = run_async(APIAuth.revoke_key(sub_key_hash))
        
        return jsonify({
            'success': success,
            'message': f'Sub-key {sub_key_hash[:16]}... has been revoked',
            'key_hash': sub_key_hash[:16] + '...'
        }), 200
        
    except Exception as e:
        logger.error(f"Error revoking sub-key: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# KEY MANAGEMENT
# ============================================================================

@tier_mgmt_bp.route('/keys/usage', methods=['GET'])
@require_api_key()
def get_key_usage():
    """Get detailed usage statistics for your API key"""
    return jsonify({
        'key_hash': g.api_key_data['key_hash'][:16] + '...',
        'tier': g.api_key_data['tier_name'],
        'is_sub_key': g.api_key_data['is_sub_key'],
        'usage': {
            'total_requests': g.api_key_data['total_requests'],
            'rate_limit': {
                'limit': g.rate_limit['limit'],
                'remaining': g.rate_limit['remaining'],
                'reset_in_seconds': g.rate_limit['reset_in'],
                'current_usage': g.rate_limit['current']
            }
        },
        'permissions': g.api_key_data['permissions'],
        'features_enabled': g.api_key_data['tier_config']['features']
    }), 200


@tier_mgmt_bp.route('/keys/revoke', methods=['POST'])
@require_api_key()
def revoke_own_key():
    """Revoke your own API key"""
    data = request.get_json()
    confirm = data.get('confirm') if data else False
    
    if not confirm:
        return jsonify({
            'error': 'Confirmation required',
            'message': 'Set "confirm": true to revoke this key',
            'warning': 'This action cannot be undone. All sub-keys will also be revoked.'
        }), 400
    
    try:
        key_hash = g.api_key_data['key_hash']
        is_sub_key = g.api_key_data['is_sub_key']
        
        success = run_async(APIAuth.revoke_key(key_hash))
        
        message = 'API key revoked successfully'
        if not is_sub_key:
            sub_keys = run_async(APIAuth.list_sub_keys(key_hash))
            if sub_keys:
                message += f' along with {len(sub_keys)} sub-key(s)'
        
        return jsonify({
            'success': success,
            'message': message,
            'revoked_at': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Error revoking key: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# TIER UPGRADE INFORMATION (Read-only)
# ============================================================================

@tier_mgmt_bp.route('/upgrade', methods=['GET'])
@require_api_key()
def get_upgrade_info():
    """Get information about upgrading your tier"""
    current_tier = g.api_key_data['tier']
    current_config = g.api_key_data['tier_config']
    
    upgrades = []
    for tier in APITier:
        if tier.value > current_tier.value:
            config = TierConfig.get_config(tier)
            upgrades.append({
                'tier': tier.name,
                'tier_level': tier.value,
                'name': config['name'],
                'rate_limit': config['rate_limit'],
                'rate_limit_display': f"{config['rate_limit']} requests/minute" if config['rate_limit'] else "Unlimited",
                'new_features': list(set(config['features'].keys()) - set(current_config['features'].keys())),
                'additional_permissions': [p for p in config['permissions'] if p not in current_config['permissions']]
            })
    
    return jsonify({
        'current_tier': g.api_key_data['tier_name'],
        'current_level': current_tier.value,
        'available_upgrades': upgrades,
        'contact': 'Contact support for tier upgrades'
    }), 200


# ============================================================================
# ADMIN-ONLY ENDPOINTS
# ============================================================================

@tier_mgmt_bp.route('/admin/keys', methods=['GET'])
@require_tier(APITier.ADMIN)
def admin_list_all_keys():
    """List all API keys (Admin only)"""
    guild_id = request.args.get('guild_id', type=int)
    
    try:
        async def get_all_keys():
            from Utils.timekeeper import get_shared_tracker
            tracker, _ = await get_shared_tracker()
            redis = tracker.redis
            
            pattern = f"api_keys:guild:{guild_id}:*" if guild_id else "api_keys:guild:*"
            cursor = 0
            all_keys = []
            
            while True:
                cursor, keys = await redis.scan(cursor, match=pattern, count=100)
                
                for key in keys:
                    guild_keys = await redis.smembers(key)
                    for key_hash in guild_keys:
                        key_data = await redis.hgetall(f"api_key:{key_hash.decode()}")
                        if key_data:
                            all_keys.append({
                                'key_hash': key_hash.decode()[:16] + '...',
                                'guild_id': int(key_data.get(b'guild_id', b'0')),
                                'tier': key_data.get(b'tier', b'SUPPORTER').decode(),
                                'created_at': key_data.get(b'created_at', b'').decode(),
                                'total_requests': int(key_data.get(b'total_requests', b'0')),
                                'enabled': key_data.get(b'enabled', b'true').decode() == 'true',
                                'is_sub_key': key_data.get(b'is_sub_key', b'false').decode() == 'true'
                            })
                
                if cursor == 0:
                    break
            
            return all_keys
        
        keys = run_async(get_all_keys())
        
        return jsonify({
            'total_keys': len(keys),
            'filter': {'guild_id': guild_id} if guild_id else None,
            'keys': keys
        }), 200
        
    except Exception as e:
        logger.error(f"Error listing all keys: {e}")
        return jsonify({'error': str(e)}), 500


@tier_mgmt_bp.route('/admin/keys/<string:key_hash>/upgrade', methods=['POST'])
@require_tier(APITier.ADMIN)
def admin_upgrade_key(key_hash: str):
    """Upgrade a key's tier (Admin only)"""
    data = request.get_json()
    
    if not data or 'new_tier' not in data:
        return jsonify({
            'error': 'Missing required field: new_tier',
            'valid_tiers': [t.name for t in APITier]
        }), 400
    
    try:
        new_tier_name = data['new_tier'].upper()
        new_tier = APITier[new_tier_name]
    except KeyError:
        return jsonify({
            'error': 'Invalid tier',
            'provided': data['new_tier'],
            'valid_tiers': [t.name for t in APITier]
        }), 400
    
    try:
        async def upgrade():
            from Utils.timekeeper import get_shared_tracker
            tracker, _ = await get_shared_tracker()
            redis = tracker.redis
            
            key_storage_key = f"api_key:{key_hash}"
            key_data = await redis.hgetall(key_storage_key)
            
            if not key_data:
                return None
            
            old_tier = key_data.get(b'tier', b'SUPPORTER').decode()
            new_tier_config = TierConfig.get_config(new_tier)
            
            # Update tier and related fields
            await redis.hset(key_storage_key, 'tier', new_tier.name)
            await redis.hset(key_storage_key, 'rate_limit', new_tier_config['rate_limit'] or 0)
            await redis.hset(key_storage_key, 'permissions', json.dumps(new_tier_config['permissions']))
            
            return {
                'old_tier': old_tier,
                'new_tier': new_tier.name,
                'new_config': new_tier_config
            }
        
        result = run_async(upgrade())
        
        if not result:
            return jsonify({
                'error': 'Key not found',
                'key_hash': key_hash[:16] + '...'
            }), 404
        
        return jsonify({
            'success': True,
            'message': f'Key upgraded from {result["old_tier"]} to {result["new_tier"]}',
            'key_hash': key_hash[:16] + '...',
            'old_tier': result['old_tier'],
            'new_tier': result['new_tier'],
            'new_rate_limit': result['new_config']['rate_limit'],
            'updated_at': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Error upgrading key: {e}")
        return jsonify({'error': str(e)}), 500