from flask import Blueprint, request, jsonify, g
from ..middleware.auth import require_api_key, APITier
from ..utils.helpers import run_async, get_tracker_and_clock

leaderboard_bp = Blueprint('leaderboard', __name__)

# Supporter tier can read leaderboard
@leaderboard_bp.route('', methods=['GET'])
@require_api_key(['read:basic'])  # Supporter+
def get_leaderboard(guild_id: int):
    """Get leaderboard - Supporter tier and up"""
    if g.api_key_data['tier'] != APITier.ADMIN:
        if g.api_key_data['guild_id'] != guild_id:
            return jsonify({'error': 'Unauthorized guild access'}), 403
    
    category = request.args.get('category')
    limit = min(int(request.args.get('limit', 10)), 100)
    time_range = request.args.get('timeframe', 'all')
    
    # Premium+ can get detailed stats
    include_stats = g.api_key_data['tier'].value >= APITier.PREMIUM.value
    
    async def fetch():
        tracker, _ = await get_tracker_and_clock()
        return await tracker.get_server_leaderboard(
            guild_id, category=category, limit=limit,
            time_range=time_range, include_stats=include_stats
        )
    
    return jsonify({
        'guild_id': guild_id,
        'category': category or 'total',
        'timeframe': time_range,
        'leaderboard': run_async(fetch()),
        'stats_included': include_stats,
        'tier': g.api_key_data['tier_name']
    }), 200