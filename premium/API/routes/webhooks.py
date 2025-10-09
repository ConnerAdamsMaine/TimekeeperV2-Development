# premium/API/routes/webhooks.py
from flask import Blueprint, request, jsonify, g
import secrets
import json
from datetime import datetime
from ..middleware.auth import require_tier, APITier
from ..utils.helpers import run_async, get_tracker_and_clock

webhooks_bp = Blueprint('webhooks', __name__)

# Enterprise tier required for webhooks
@webhooks_bp.route('', methods=['POST'])
@require_tier(APITier.ENTERPRISE)  # Enterprise+ for webhooks
def create_webhook(guild_id: int):
    """Create webhook - Enterprise tier and up"""
    if g.api_key_data['tier'] != APITier.ADMIN:
        if g.api_key_data['guild_id'] != guild_id:
            return jsonify({'error': 'Unauthorized guild access'}), 403
    
    # Verify webhooks feature is enabled
    if not g.api_key_data['tier_config']['features']['webhooks']:
        return jsonify({
            'error': 'Webhooks not available for your tier',
            'your_tier': g.api_key_data['tier_name'],
            'required_tier': 'Enterprise',
            'feature': 'webhooks'
        }), 403
    
    data = request.get_json()
    if not data or 'url' not in data or 'events' not in data:
        return jsonify({'error': 'Missing url or events'}), 400
    if not data or 'url' not in data or 'events' not in data:
        return jsonify({'error': 'Missing url or events'}), 400
    
    async def store():
        tracker, _ = await get_tracker_and_clock()
        webhook_id = secrets.token_hex(16)
        
        webhook_data = {
            'id': webhook_id,
            'guild_id': guild_id,
            'url': data['url'],
            'events': json.dumps(data['events']),
            'created_at': datetime.now().isoformat(),
            'enabled': 'true',
            'secret': secrets.token_hex(32)
        }
        
        webhook_key = f"webhook:{guild_id}:{webhook_id}"
        await tracker.redis.hset(webhook_key, mapping=webhook_data)
        await tracker.redis.sadd(f"webhooks:guild:{guild_id}", webhook_id)
        
        return {
            'webhook_id': webhook_id,
            'url': data['url'],
            'events': data['events'],
            'secret': webhook_data['secret']
        }
    
    return jsonify({
        'success': True,
        'webhook': {},
        'tier': g.api_key_data['tier_name']
    }), 201