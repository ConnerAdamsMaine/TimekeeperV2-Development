from flask import Blueprint, request, jsonify, g
from ..middleware.auth import require_api_key, require_tier, APITier
from ..utils.helpers import run_async, get_tracker_and_clock

analytics_bp = Blueprint('analytics', __name__)

# Premium tier required for analytics
@analytics_bp.route('/insights/<int:user_id>', methods=['GET'])
@require_tier(APITier.PREMIUM)  # Premium+ for analytics
def get_insights(guild_id: int, user_id: int):
    """Get user insights - Premium tier and up"""
    if g.api_key_data['tier'] != APITier.ADMIN:
        if g.api_key_data['guild_id'] != guild_id:
            return jsonify({'error': 'Unauthorized guild access'}), 403
    
    # Verify analytics feature is enabled for tier
    if not g.api_key_data['tier_config']['features']['analytics']:
        return jsonify({
            'error': 'Analytics not available for your tier',
            'your_tier': g.api_key_data['tier_name'],
            'required_tier': 'Premium',
            'feature': 'analytics'
        }), 403
    
    async def fetch():
        tracker, _ = await get_tracker_and_clock()
        if not tracker.analytics:
            return {'error': 'Analytics not enabled on server'}
        return await tracker.analytics.get_advanced_insights(guild_id, user_id)
    
    insights = run_async(fetch())
    if insights.get('error'):
        return jsonify(insights), 400
    
    return jsonify({
        'guild_id': guild_id,
        'user_id': user_id,
        'insights': insights,
        'tier': g.api_key_data['tier_name']
    }), 200