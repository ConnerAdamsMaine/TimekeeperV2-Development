# premium/API/routes/categories.py
from flask import Blueprint, request, jsonify, g
from ..middleware.auth import require_api_key
from ..utils.helpers import run_async, get_tracker_and_clock

categories_bp = Blueprint('categories', __name__)

@categories_bp.route('', methods=['GET'])
@require_api_key(['read'])
def get_categories(guild_id: int):
    if g.api_key_data['guild_id'] != guild_id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    async def fetch():
        tracker, _ = await get_tracker_and_clock()
        include_metadata = request.args.get('include_metadata', 'false').lower() == 'true'
        return await tracker.list_categories(guild_id, include_archived=False, include_metadata=include_metadata)
    
    return jsonify({'guild_id': guild_id, 'categories': run_async(fetch())}), 200

@categories_bp.route('', methods=['POST'])
@require_api_key(['admin'])
def add_category(guild_id: int):
    if g.api_key_data['guild_id'] != guild_id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    if not data or 'name' not in data:
        return jsonify({'error': 'Missing name field'}), 400
    
    async def create():
        tracker, _ = await get_tracker_and_clock()
        return await tracker.add_category(
            guild_id, data['name'], 
            user_id=g.api_key_data['created_by'],
            description=data.get('description'),
            color=data.get('color'),
            productivity_weight=data.get('productivity_weight', 1.0)
        )
    
    result = run_async(create())
    return jsonify(result), 201 if result['success'] else 400

@categories_bp.route('/<string:category>', methods=['DELETE'])
@require_api_key(['admin'])
def remove_category(guild_id: int, category: str):
    if g.api_key_data['guild_id'] != guild_id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    async def delete():
        tracker, _ = await get_tracker_and_clock()
        return await tracker.remove_category(
            guild_id, category,
            user_id=g.api_key_data['created_by'],
            force=request.args.get('force', 'false').lower() == 'true'
        )
    
    result = run_async(delete())
    return jsonify(result), 200 if result['success'] else 400