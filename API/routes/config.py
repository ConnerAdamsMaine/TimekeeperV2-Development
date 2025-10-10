# premium/API/routes/config.py
from flask import Blueprint, request, jsonify, g
from ..middleware.auth import require_api_key
from ..utils.helpers import run_async, get_tracker_and_clock

config_bp = Blueprint('config', __name__)

@config_bp.route('', methods=['GET'])
@require_api_key(['read'])
def get_config(guild_id: int):
    if g.api_key_data['guild_id'] != guild_id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    async def fetch():
        tracker, _ = await get_tracker_and_clock()
        settings = await tracker.get_server_settings(guild_id)
        return {
            'timezone': settings.timezone,
            'work_hours_start': settings.work_hours_start,
            'work_hours_end': settings.work_hours_end,
            'max_session_hours': settings.max_session_hours,
            'analytics_enabled': settings.analytics_enabled
        }
    
    return jsonify({'guild_id': guild_id, 'config': run_async(fetch())}), 200

@config_bp.route('', methods=['PATCH'])
@require_api_key(['admin'])
def update_config(guild_id: int):
    if g.api_key_data['guild_id'] != guild_id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    async def update():
        tracker, _ = await get_tracker_and_clock()
        settings = await tracker.get_server_settings(guild_id)
        
        allowed = ['timezone', 'work_hours_start', 'work_hours_end', 'max_session_hours', 'analytics_enabled']
        updated = []
        for field in allowed:
            if field in data:
                setattr(settings, field, data[field])
                updated.append(field)
        
        await tracker._save_server_settings(guild_id, settings)
        return {'success': True, 'updated_fields': updated}
    
    return jsonify(run_async(update())), 200