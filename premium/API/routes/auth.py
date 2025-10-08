# premium/API/routes/auth.py
# ============================================================================
# Authentication routes
# ============================================================================

from flask import Blueprint, request, jsonify
import os
import logging

from ..middleware.auth import APIAuth
from ..utils.helpers import run_async

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/generate', methods=['POST'])
def generate_api_key():
    """Generate a new API key"""
    data = request.get_json()
    
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
    
    if master_key != os.getenv('API_MASTER_KEY'):
        return jsonify({
            'error': 'Unauthorized',
            'message': 'Invalid master key'
        }), 401
    
    try:
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
        return jsonify({'error': str(e)}), 500