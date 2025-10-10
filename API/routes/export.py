# premium/API/routes/export.py
from flask import Blueprint, jsonify, g, Response
import io, csv, json
from datetime import datetime
from ..middleware.auth import require_api_key
from ..utils.helpers import run_async, get_tracker_and_clock

export_bp = Blueprint('export', __name__)

@export_bp.route('/<int:user_id>', methods=['GET'])
@require_api_key(['read'])
def export_user_data(guild_id: int, user_id: int):
    if g.api_key_data['guild_id'] != guild_id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    format_type = request.args.get('format', 'json').lower()
    
    async def get_data():
        tracker, _ = await get_tracker_and_clock()
        user_times = await tracker.get_user_times(guild_id, user_id, include_metadata=True)
        
        entries_key = f"time_entries:{guild_id}:{user_id}"
        entries_data = await tracker.redis.zrevrange(entries_key, 0, -1, withscores=True)
        
        entries = []
        for entry_bytes, timestamp in entries_data:
            try:
                entry = json.loads(entry_bytes)
                entry['timestamp'] = timestamp
                entry['date'] = datetime.fromtimestamp(timestamp).isoformat()
                entries.append(entry)
            except:
                continue
        
        return {
            'user_id': user_id,
            'guild_id': guild_id,
            'export_date': datetime.now().isoformat(),
            'summary': user_times,
            'entries': entries
        }
    
    data = run_async(get_data())
    
    if format_type == 'csv':
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Date', 'Category', 'Duration (seconds)', 'Session ID'])
        for entry in data['entries']:
            writer.writerow([entry['date'], entry['category'], entry['seconds'], entry.get('session_id', 'N/A')])
        output.seek(0)
        return Response(output.getvalue(), mimetype='text/csv',
                       headers={'Content-Disposition': f'attachment; filename=timetracker_{user_id}_{datetime.now().strftime("%Y%m%d")}.csv'})
    
    return jsonify(data), 200