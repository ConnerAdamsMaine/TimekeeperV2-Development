# premium/API/routes/analytics.py
from flask import Blueprint, request, jsonify, g
from ..middleware.auth import require_api_key
from ..utils.helpers import run_async, get_tracker_and_clock

analytics_bp = Blueprint('analytics', __name__)

@analytics_bp.route('/insights/<int:user_id>', methods=['GET'])
@require_api_key(['read'])
def get_insights(guild_id: int, user_id: int):
    if g.api_key_data['guild_id'] != guild_id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    async def fetch():
        tracker, _ = await get_tracker_and_clock()
        if not tracker.analytics:
            return {'error': 'Analytics not enabled'}
        return await tracker.analytics.get_advanced_insights(guild_id, user_id)
    
    insights = run_async(fetch())
    if insights.get('error'):
        return jsonify(insights), 400
    return jsonify({'guild_id': guild_id, 'user_id': user_id, 'insights': insights}), 200