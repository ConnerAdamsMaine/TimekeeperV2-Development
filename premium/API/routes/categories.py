from flask import Blueprint, request, jsonify, g
from ..middleware.auth import require_api_key, require_tier, APITier
from ..utils.helpers import run_async, get_tracker_and_clock

categories_bp = Blueprint('categories', __name__)

# Supporter tier can read categories
@categories_bp.route('', methods=['GET'])
@require_api_key(['read:basic'])  # Supporter+
def get_categories(guild_id: int):
    """Get categories - Supporter tier and up"""
    if g.api_key_data['tier'] != APITier.ADMIN:
        if g.api_key_data['guild_id'] != guild_id:
            return jsonify({'error': 'Unauthorized guild access'}), 403
    
    async def fetch():
        tracker, _ = await get_tracker_and_clock()
        include_metadata = request.args.get('include_metadata', 'false').lower() == 'true'
        
        # Premium+ can get metadata
        if include_metadata and g.api_key_data['tier'].value < APITier.PREMIUM.value:
            include_metadata = False
        
        return await tracker.list_categories(guild_id, include_archived=False, include_metadata=include_metadata)
    
    return jsonify({
        'guild_id': guild_id,
        'categories': run_async(fetch()),
        'metadata_available': g.api_key_data['tier'].value >= APITier.PREMIUM.value
    }), 200

# Enterprise tier required to add categories
@categories_bp.route('', methods=['POST'])
@require_tier(APITier.ENTERPRISE)  # Enterprise+ only
def add_category(guild_id: int):
    """Add category - Enterprise tier and up"""
    if g.api_key_data['tier'] != APITier.ADMIN:
        if g.api_key_data['guild_id'] != guild_id:
            return jsonify({'error': 'Unauthorized guild access'}), 403
    
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

# Enterprise tier required to remove categories
@categories_bp.route('/<string:category>', methods=['DELETE'])
@require_tier(APITier.ENTERPRISE)
def remove_category(guild_id: int, category: str):
    """Remove category - Enterprise tier and up"""
    if g.api_key_data['tier'] != APITier.ADMIN:
        if g.api_key_data['guild_id'] != guild_id:
            return jsonify({'error': 'Unauthorized guild access'}), 403
    
    async def delete():
        tracker, _ = await get_tracker_and_clock()
        return await tracker.remove_category(
            guild_id, category,
            user_id=g.api_key_data['created_by'],
            force=request.args.get('force', 'false').lower() == 'true'
        )
    
    result = run_async(delete())
    return jsonify(result), 200 if result['success'] else 400