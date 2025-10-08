# premium/API/routes/permissions.py
from flask import Blueprint, request, jsonify, g
from ..middleware.auth import require_api_key
from ..utils.helpers import run_async, get_tracker_and_clock

permissions_bp = Blueprint('permissions', __name__)

@permissions_bp.route('', methods=['GET'])
@require_api_key(['admin'])
def get_permissions(guild_id: int):
    if g.api_key_data['guild_id'] != guild_id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    async def fetch():
        tracker, _ = await get_tracker_and_clock()
        return await tracker.get_server_permissions(guild_id)
    
    return jsonify({'guild_id': guild_id, 'permissions': run_async(fetch())}), 200

@permissions_bp.route('/suspend', methods=['POST'])
@require_api_key(['admin'])
def suspend_user(guild_id: int):
    if g.api_key_data['guild_id'] != guild_id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    if not data or 'user_id' not in data:
        return jsonify({'error': 'Missing user_id'}), 400
    
    async def suspend():
        tracker, _ = await get_tracker_and_clock()
        return await tracker.suspend_user(guild_id, data['user_id'])
    
    success = run_async(suspend())
    return jsonify({'success': success, 'user_id': data['user_id']}), 200 if success else 400