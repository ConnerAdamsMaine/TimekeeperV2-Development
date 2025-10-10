from flask import Blueprint, request, jsonify
import os
import logging

from ..middleware.auth import APIAuth, APITier
from ..utils.helpers import run_async

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/generate', methods=['POST'])
def generate_api_key():
    """Generate a new API key with tier support"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    guild_id = data.get('guild_id')
    admin_user_id = data.get('admin_user_id')
    master_key = data.get('master_key')
    tier_name = data.get('tier', 'SUPPORTER').upper()
    permissions = data.get('permissions')
    
    if not guild_id or not admin_user_id:
        return jsonify({
            'error': 'Missing required fields',
            'message': 'guild_id and admin_user_id are required'
        }), 400
    
    if master_key != os.getenv('API_MASTER_KEY'):
        return jsonify({
            'error': 'Unauthorized',
            'message': 'Invalid master key'
        }), 401
    
    # Validate tier
    try:
        tier = APITier[tier_name]
    except KeyError:
        return jsonify({
            'error': 'Invalid tier',
            'provided': tier_name,
            'valid_tiers': [t.name for t in APITier],
            'tier_descriptions': {
                'SUPPORTER': 'Basic read-only access (20 req/min)',
                'PREMIUM': 'Full read + limited write (60 req/min)',
                'ENTERPRISE': 'Full access + sub-keys (120 req/min)',
                'ADMIN': 'Unrestricted god-mode (unlimited)'
            }
        }), 400
    
    try:
        result = run_async(APIAuth.generate_api_key(
            guild_id=guild_id,
            admin_user_id=admin_user_id,
            tier=tier,
            permissions=permissions
        ))
        
        tier_config = result['tier_config']
        
        return jsonify({
            'success': True,
            'api_key': result['api_key'],
            'key_hash': result['key_hash'][:16] + '...',
            'guild_id': guild_id,
            'tier': {
                'name': tier.name,
                'display_name': tier_config['name'],
                'level': tier.value,
                'rate_limit': tier_config['rate_limit'],
                'rate_limit_display': f"{tier_config['rate_limit']} requests/minute" if tier_config['rate_limit'] else "Unlimited"
            },
            'permissions': result['tier_config']['permissions'] if not permissions else permissions,
            'features': tier_config['features'],
            'expires': 'Never (1 year renewable)',
            'warning': 'Store this key securely. It will not be shown again.',
            'endpoints': {
                'tier_info': '/api/v1/tier/my-tier',
                'usage': '/api/v1/tier/keys/usage',
                'upgrade_info': '/api/v1/tier/upgrade'
            }
        }), 201
        
    except Exception as e:
        logger.error(f"Error generating API key: {e}")
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/validate', methods=['POST'])
def validate_key():
    """Validate an API key without requiring auth header (for testing)"""
    data = request.get_json()
    
    if not data or 'api_key' not in data:
        return jsonify({
            'error': 'Missing api_key in request body'
        }), 400
    
    api_key = data['api_key']
    
    try:
        key_data = run_async(APIAuth.validate_api_key(api_key))
        
        if not key_data:
            return jsonify({
                'valid': False,
                'message': 'Invalid or expired API key'
            }), 200
        
        return jsonify({
            'valid': True,
            'tier': key_data['tier_name'],
            'tier_level': key_data['tier'].value,
            'guild_id': key_data['guild_id'],
            'is_sub_key': key_data['is_sub_key'],
            'rate_limit': key_data['rate_limit'],
            'features': key_data['tier_config']['features'],
            'permissions': key_data['permissions']
        }), 200
        
    except Exception as e:
        logger.error(f"Error validating key: {e}")
        return jsonify({'error': str(e)}), 500
