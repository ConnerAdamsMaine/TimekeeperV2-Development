# premium/API/routes/leaderboard.py
from flask import Blueprint, request, jsonify, g
from ..middleware.auth import require_api_key
from ..utils.helpers import run_async, get_tracker_and_clock

leaderboard_bp = Blueprint('leaderboard', __name__)

@leaderboard_bp.route('', methods=['GET'])
@require_api_key(['read'])
def get_leaderboard(guild_id: int):
    if g.api_key_data['guild_id'] != guild_id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    category = request.args.get('category')
    limit = min(int(request.args.get('limit', 10)), 100)
    time_range = request.args.get('timeframe', 'all')
    
    async def fetch():
        tracker, _ = await get_tracker_and_clock()
        return await tracker.get_server_leaderboard(
            guild_id, category=category, limit=limit,
            time_range=time_range, include_stats=True
        )
    
    return jsonify({
        'guild_id': guild_id,
        'category': category or 'total',
        'timeframe': time_range,
        'leaderboard': run_async(fetch())
    }), 200