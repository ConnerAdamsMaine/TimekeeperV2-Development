# premium/API/routes/admin.py
# ============================================================================
# Admin-only API endpoints for system monitoring and management
# ============================================================================

from flask import Blueprint, jsonify, request, g
from datetime import datetime
import logging
from typing import Dict, Any, List

from ..middleware.auth import require_tier, APITier
from ..utils.helpers import run_async, get_tracker_and_clock, get_bot

logger = logging.getLogger(__name__)

admin_api_bp = Blueprint('admin_api', __name__)


# ============================================================================
# SYSTEM HEALTH ENDPOINTS
# ============================================================================

@admin_api_bp.route('/health', methods=['GET'])
@require_tier(APITier.ADMIN)
def get_system_health():
    """Get comprehensive system health status (Admin only)"""
    try:
        async def fetch_health():
            from Utils.timekeeper import get_system_status
            
            tracker, clock = await get_tracker_and_clock()
            
            # Get tracker health
            tracker_health = await tracker.health_check()
            
            # Get system status
            system_status = await get_system_status()
            
            # Get bot info
            bot = get_bot()
            bot_status = {
                'connected': bot is not None,
                'latency_ms': round(bot.latency * 1000, 2) if bot else None,
                'user_count': len(bot.users) if bot else 0,
                'guild_count': len(bot.guilds) if bot else 0
            }
            
            return {
                'tracker_health': tracker_health,
                'system_status': system_status,
                'bot_status': bot_status
            }
        
        health_data = run_async(fetch_health())
        
        # Determine overall health
        overall_status = 'healthy'
        if health_data['tracker_health']['status'] != 'healthy':
            overall_status = 'degraded'
        if health_data['system_status']['status'] != 'operational':
            overall_status = 'unhealthy'
        
        return jsonify({
            'overall_status': overall_status,
            'timestamp': datetime.now().isoformat(),
            'health_score': health_data['tracker_health'].get('health_score', 0),
            'details': health_data
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting system health: {e}")
        return jsonify({
            'error': str(e),
            'overall_status': 'error'
        }), 500


@admin_api_bp.route('/health/components', methods=['GET'])
@require_tier(APITier.ADMIN)
def get_health_components():
    """Get detailed component health breakdown (Admin only)"""
    try:
        async def fetch_components():
            tracker, _ = await get_tracker_and_clock()
            health = await tracker.health_check()
            
            components = {}
            
            # Redis component
            if 'components' in health:
                redis_info = health['components'].get('redis', {})
                components['redis'] = {
                    'status': redis_info.get('status', 'unknown'),
                    'response_time_ms': redis_info.get('response_time_ms', 0),
                    'connected': redis_info.get('connected', False)
                }
                
                # Circuit breaker
                circuit_info = health['components'].get('circuit_breaker', {})
                components['circuit_breaker'] = {
                    'status': circuit_info.get('status', 'unknown'),
                    'health_score': circuit_info.get('health_score', 0),
                    'failure_count': circuit_info.get('failure_count', 0),
                    'error_rate': circuit_info.get('error_rate', 0)
                }
                
                # Batch processor
                batch_info = health['components'].get('batch_processor', {})
                components['batch_processor'] = {
                    'status': batch_info.get('status', 'unknown'),
                    'queue_size': batch_info.get('queue_size', 0),
                    'operations_per_second': batch_info.get('operations_per_second', 0),
                    'success_rate': batch_info.get('success_rate', 0)
                }
                
                # Cache
                cache_info = health['components'].get('cache', {})
                components['cache'] = {
                    'status': cache_info.get('status', 'unknown'),
                    'hit_rate': cache_info.get('hit_rate', 0),
                    'total_operations': cache_info.get('total_operations', 0),
                    'sizes': cache_info.get('sizes', {})
                }
                
                # Performance
                perf_info = health['components'].get('performance', {})
                components['performance'] = {
                    'status': perf_info.get('status', 'unknown'),
                    'avg_response_time_ms': perf_info.get('avg_response_time_ms', 0),
                    'peak_response_time_ms': perf_info.get('peak_response_time_ms', 0),
                    'operations_per_second': perf_info.get('operations_per_second', 0),
                    'success_rate': perf_info.get('success_rate', 0)
                }
            
            return components
        
        components = run_async(fetch_components())
        
        return jsonify({
            'timestamp': datetime.now().isoformat(),
            'components': components
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting health components: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# SYSTEM STATUS ENDPOINTS
# ============================================================================

@admin_api_bp.route('/status', methods=['GET'])
@require_tier(APITier.ADMIN)
def get_admin_status():
    """Get comprehensive system status (Admin only)"""
    try:
        async def fetch_status():
            tracker, clock = await get_tracker_and_clock()
            bot = get_bot()
            
            # Bot statistics
            bot_stats = {
                'connected': bot is not None,
                'uptime_seconds': (datetime.now() - bot.start_time).total_seconds() if bot and hasattr(bot, 'start_time') else None,
                'guild_count': len(bot.guilds) if bot else 0,
                'user_count': len(bot.users) if bot else 0,
                'latency_ms': round(bot.latency * 1000, 2) if bot else None,
                'shard_count': bot.shard_count if bot else 1
            }
            
            # Database statistics
            redis_info = await tracker.redis.info('stats')
            db_stats = {
                'total_commands_processed': redis_info.get('total_commands_processed', 0),
                'instantaneous_ops_per_sec': redis_info.get('instantaneous_ops_per_sec', 0),
                'total_connections_received': redis_info.get('total_connections_received', 0),
                'keyspace_hits': redis_info.get('keyspace_hits', 0),
                'keyspace_misses': redis_info.get('keyspace_misses', 0)
            }
            
            # Calculate hit rate
            total_keyspace = db_stats['keyspace_hits'] + db_stats['keyspace_misses']
            db_stats['hit_rate'] = round((db_stats['keyspace_hits'] / total_keyspace * 100), 2) if total_keyspace > 0 else 0
            
            # System metrics
            metrics = await tracker.get_metrics() if hasattr(tracker, 'get_metrics') else {}
            
            return {
                'bot': bot_stats,
                'database': db_stats,
                'metrics': metrics,
                'timestamp': datetime.now().isoformat()
            }
        
        status_data = run_async(fetch_status())
        
        return jsonify({
            'status': 'operational',
            'data': status_data
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting admin status: {e}")
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500


@admin_api_bp.route('/status/metrics', methods=['GET'])
@require_tier(APITier.ADMIN)
def get_system_metrics():
    """Get detailed system performance metrics (Admin only)"""
    try:
        async def fetch_metrics():
            tracker, clock = await get_tracker_and_clock()
            
            # Get tracker metrics
            tracker_metrics = {}
            if hasattr(tracker, 'operation_metrics'):
                tracker_metrics = tracker.operation_metrics.copy()
            
            # Get batch processor metrics
            batch_metrics = {}
            if tracker.batch_processor:
                batch_metrics = await tracker.batch_processor.get_metrics()
            
            # Get circuit breaker metrics
            circuit_metrics = {}
            if hasattr(tracker, 'circuit_breaker'):
                circuit_metrics = tracker.circuit_breaker.get_metrics()
            
            # Get analytics metrics
            analytics_metrics = {}
            if tracker.analytics:
                analytics_metrics = await tracker.analytics.get_analytics_metrics()
            
            # Get clock metrics
            clock_metrics = {}
            if hasattr(clock, 'session_metrics'):
                clock_metrics = clock.session_metrics.copy()
            
            return {
                'tracker': tracker_metrics,
                'batch_processor': batch_metrics,
                'circuit_breaker': circuit_metrics,
                'analytics': analytics_metrics,
                'clock': clock_metrics
            }
        
        metrics = run_async(fetch_metrics())
        
        return jsonify({
            'timestamp': datetime.now().isoformat(),
            'metrics': metrics
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting system metrics: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# GUILD STATISTICS ENDPOINTS
# ============================================================================

@admin_api_bp.route('/guilds', methods=['GET'])
@require_tier(APITier.ADMIN)
def get_all_guilds():
    """Get all guilds with statistics (Admin only)"""
    try:
        include_details = request.args.get('details', 'false').lower() == 'true'
        limit = min(int(request.args.get('limit', 100)), 500)
        offset = int(request.args.get('offset', 0))
        
        async def fetch_guilds():
            tracker, _ = await get_tracker_and_clock()
            bot = get_bot()
            
            guilds = []
            
            if bot:
                # Get guilds from bot
                for guild in list(bot.guilds)[offset:offset + limit]:
                    guild_data = {
                        'guild_id': guild.id,
                        'name': guild.name,
                        'member_count': guild.member_count,
                        'owner_id': guild.owner_id,
                        'created_at': guild.created_at.isoformat() if guild.created_at else None
                    }
                    
                    if include_details:
                        # Get time tracking stats for guild
                        server_key = f"server_times:{guild.id}"
                        server_data = await tracker.redis.hgetall(server_key)
                        
                        total_seconds = int(server_data.get(b'total', b'0')) if server_data else 0
                        
                        # Count users
                        user_pattern = f"user_times:{guild.id}:*"
                        user_cursor = 0
                        user_count = 0
                        while True:
                            user_cursor, keys = await tracker.redis.scan(user_cursor, match=user_pattern, count=100)
                            user_count += len(keys)
                            if user_cursor == 0:
                                break
                        
                        # Count active sessions
                        active_pattern = f"active_session:{guild.id}:*"
                        active_cursor = 0
                        active_count = 0
                        while True:
                            active_cursor, keys = await tracker.redis.scan(active_cursor, match=active_pattern, count=100)
                            active_count += len(keys)
                            if active_cursor == 0:
                                break
                        
                        guild_data['tracking_stats'] = {
                            'total_time_seconds': total_seconds,
                            'total_time_hours': round(total_seconds / 3600, 2),
                            'active_users': user_count,
                            'active_sessions': active_count
                        }
                    
                    guilds.append(guild_data)
            
            return guilds
        
        guilds_data = run_async(fetch_guilds())
        
        bot = get_bot()
        total_guilds = len(bot.guilds) if bot else 0
        
        return jsonify({
            'total_guilds': total_guilds,
            'returned': len(guilds_data),
            'limit': limit,
            'offset': offset,
            'has_more': (offset + limit) < total_guilds,
            'guilds': guilds_data
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting guilds: {e}")
        return jsonify({'error': str(e)}), 500


@admin_api_bp.route('/guilds/count', methods=['GET'])
@require_tier(APITier.ADMIN)
def get_guild_count():
    """Get total guild count (Admin only)"""
    try:
        bot = get_bot()
        
        if not bot:
            return jsonify({
                'error': 'Bot not available',
                'guild_count': 0
            }), 503
        
        guild_count = len(bot.guilds)
        
        # Get active guilds (guilds with tracking data)
        async def count_active():
            tracker, _ = await get_tracker_and_clock()
            
            pattern = "server_times:*"
            cursor = 0
            active_guilds = set()
            
            while True:
                cursor, keys = await tracker.redis.scan(cursor, match=pattern, count=100)
                for key in keys:
                    guild_id = int(key.decode().split(':')[1])
                    active_guilds.add(guild_id)
                
                if cursor == 0:
                    break
            
            return len(active_guilds)
        
        active_guild_count = run_async(count_active())
        
        return jsonify({
            'total_guilds': guild_count,
            'active_guilds': active_guild_count,
            'inactive_guilds': guild_count - active_guild_count,
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting guild count: {e}")
        return jsonify({'error': str(e)}), 500


@admin_api_bp.route('/guilds/<int:guild_id>/details', methods=['GET'])
@require_tier(APITier.ADMIN)
def get_guild_details(guild_id: int):
    """Get detailed information about a specific guild (Admin only)"""
    try:
        async def fetch_details():
            tracker, clock = await get_tracker_and_clock()
            bot = get_bot()
            
            # Get guild from bot
            guild = bot.get_guild(guild_id) if bot else None
            
            if not guild:
                return None
            
            # Basic guild info
            guild_info = {
                'guild_id': guild.id,
                'name': guild.name,
                'member_count': guild.member_count,
                'owner_id': guild.owner_id,
                'created_at': guild.created_at.isoformat() if guild.created_at else None,
                'features': guild.features,
                'premium_tier': guild.premium_tier,
                'premium_subscription_count': guild.premium_subscription_count
            }
            
            # Get tracking statistics
            server_key = f"server_times:{guild_id}"
            server_data = await tracker.redis.hgetall(server_key)
            
            total_seconds = int(server_data.get(b'total', b'0')) if server_data else 0
            
            categories = {}
            if server_data:
                for key, value in server_data.items():
                    key_str = key.decode('utf-8')
                    if key_str != 'total':
                        categories[key_str] = int(value)
            
            # Count users
            user_pattern = f"user_times:{guild_id}:*"
            user_cursor = 0
            user_count = 0
            while True:
                user_cursor, keys = await tracker.redis.scan(user_cursor, match=user_pattern, count=100)
                user_count += len(keys)
                if user_cursor == 0:
                    break
            
            # Count active sessions
            active_pattern = f"active_session:{guild_id}:*"
            active_cursor = 0
            active_sessions = []
            while True:
                active_cursor, keys = await tracker.redis.scan(active_cursor, match=active_pattern, count=100)
                for key in keys:
                    session_data = await tracker.redis.get(key)
                    if session_data:
                        import json
                        session = json.loads(session_data)
                        active_sessions.append({
                            'user_id': session['user_id'],
                            'category': session['category'],
                            'start_time': session['start_time']
                        })
                if active_cursor == 0:
                    break
            
            # Get categories
            categories_list = await tracker.list_categories(guild_id)
            
            # Get permissions
            permissions = await tracker.get_server_permissions(guild_id)
            
            guild_info['tracking_stats'] = {
                'total_time_seconds': total_seconds,
                'total_time_hours': round(total_seconds / 3600, 2),
                'active_users': user_count,
                'active_sessions': len(active_sessions),
                'categories': categories,
                'configured_categories': list(categories_list),
                'sessions': active_sessions
            }
            
            guild_info['permissions'] = permissions
            
            return guild_info
        
        details = run_async(fetch_details())
        
        if not details:
            return jsonify({
                'error': 'Guild not found',
                'guild_id': guild_id
            }), 404
        
        return jsonify(details), 200
        
    except Exception as e:
        logger.error(f"Error getting guild details: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# USER STATISTICS ENDPOINTS
# ============================================================================

@admin_api_bp.route('/users/total', methods=['GET'])
@require_tier(APITier.ADMIN)
def get_total_users():
    """Get total user count across all guilds (Admin only)"""
    try:
        async def count_users():
            tracker, _ = await get_tracker_and_clock()
            
            # Count unique users across all guilds
            all_users = set()
            
            pattern = "user_times:*:*"
            cursor = 0
            
            while True:
                cursor, keys = await tracker.redis.scan(cursor, match=pattern, count=1000)
                
                for key in keys:
                    try:
                        parts = key.decode().split(':')
                        if len(parts) >= 3:
                            user_id = int(parts[2])
                            all_users.add(user_id)
                    except (ValueError, IndexError):
                        continue
                
                if cursor == 0:
                    break
            
            return len(all_users)
        
        total_users = run_async(count_users())
        
        # Get bot user count for comparison
        bot = get_bot()
        bot_user_count = len(bot.users) if bot else 0
        
        return jsonify({
            'total_tracking_users': total_users,
            'total_bot_users': bot_user_count,
            'note': 'total_tracking_users = users with time data, total_bot_users = all users bot can see',
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Error counting total users: {e}")
        return jsonify({'error': str(e)}), 500


@admin_api_bp.route('/users/statistics', methods=['GET'])
@require_tier(APITier.ADMIN)
def get_user_statistics():
    """Get comprehensive user statistics across all guilds (Admin only)"""
    try:
        async def fetch_stats():
            tracker, _ = await get_tracker_and_clock()
            
            # Count users by guild
            guild_user_counts = {}
            total_users = set()
            total_time_seconds = 0
            
            pattern = "user_times:*:*"
            cursor = 0
            
            while True:
                cursor, keys = await tracker.redis.scan(cursor, match=pattern, count=1000)
                
                for key in keys:
                    try:
                        parts = key.decode().split(':')
                        if len(parts) >= 3:
                            guild_id = int(parts[1])
                            user_id = int(parts[2])
                            
                            total_users.add(user_id)
                            
                            if guild_id not in guild_user_counts:
                                guild_user_counts[guild_id] = 0
                            guild_user_counts[guild_id] += 1
                            
                            # Get user's total time
                            user_data = await tracker.redis.hgetall(key)
                            if user_data and b'total' in user_data:
                                total_time_seconds += int(user_data[b'total'])
                    except (ValueError, IndexError):
                        continue
                
                if cursor == 0:
                    break
            
            # Calculate averages
            avg_users_per_guild = len(total_users) / len(guild_user_counts) if guild_user_counts else 0
            avg_time_per_user = total_time_seconds / len(total_users) if total_users else 0
            
            # Find top guilds by user count
            top_guilds = sorted(guild_user_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            
            return {
                'unique_users': len(total_users),
                'total_guilds_with_users': len(guild_user_counts),
                'average_users_per_guild': round(avg_users_per_guild, 2),
                'total_time_tracked_seconds': total_time_seconds,
                'total_time_tracked_hours': round(total_time_seconds / 3600, 2),
                'average_time_per_user_hours': round(avg_time_per_user / 3600, 2),
                'top_guilds_by_users': [
                    {'guild_id': guild_id, 'user_count': count}
                    for guild_id, count in top_guilds
                ]
            }
        
        stats = run_async(fetch_stats())
        
        return jsonify({
            'timestamp': datetime.now().isoformat(),
            'statistics': stats
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting user statistics: {e}")
        return jsonify({'error': str(e)}), 500


@admin_api_bp.route('/users/active', methods=['GET'])
@require_tier(APITier.ADMIN)
def get_active_users():
    """Get currently active users (clocked in) across all guilds (Admin only)"""
    try:
        async def fetch_active():
            tracker, _ = await get_tracker_and_clock()
            
            active_users = []
            
            pattern = "active_session:*:*"
            cursor = 0
            
            while True:
                cursor, keys = await tracker.redis.scan(cursor, match=pattern, count=1000)
                
                for key in keys:
                    session_data = await tracker.redis.get(key)
                    if session_data:
                        import json
                        try:
                            session = json.loads(session_data)
                            active_users.append({
                                'guild_id': session['server_id'],
                                'user_id': session['user_id'],
                                'category': session['category'],
                                'start_time': session['start_time'],
                                'session_id': session['session_id']
                            })
                        except (json.JSONDecodeError, KeyError):
                            continue
                
                if cursor == 0:
                    break
            
            # Group by guild
            by_guild = {}
            for session in active_users:
                guild_id = session['guild_id']
                if guild_id not in by_guild:
                    by_guild[guild_id] = []
                by_guild[guild_id].append(session)
            
            return {
                'total_active': len(active_users),
                'guilds_with_active': len(by_guild),
                'sessions': active_users,
                'by_guild': by_guild
            }
        
        active_data = run_async(fetch_active())
        
        return jsonify({
            'timestamp': datetime.now().isoformat(),
            'active_users': active_data
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting active users: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# SYSTEM OPERATIONS ENDPOINTS
# ============================================================================

@admin_api_bp.route('/operations/cleanup', methods=['POST'])
@require_tier(APITier.ADMIN)
def trigger_cleanup():
    """Trigger system cleanup operations (Admin only)"""
    try:
        cleanup_type = request.args.get('type', 'cache')
        
        async def perform_cleanup():
            tracker, _ = await get_tracker_and_clock()
            
            results = {}
            
            if cleanup_type == 'cache' or cleanup_type == 'all':
                # Clear caches
                tracker.l1_cache.clear()
                tracker.l2_cache.clear()
                tracker.l3_cache.clear()
                results['cache_cleared'] = True
            
            if cleanup_type == 'sessions' or cleanup_type == 'all':
                # Clean up old sessions
                pattern = "completed_session:*"
                cursor = 0
                deleted = 0
                
                while True:
                    cursor, keys = await tracker.redis.scan(cursor, match=pattern, count=100)
                    
                    for key in keys:
                        ttl = await tracker.redis.ttl(key)
                        if ttl < 0:  # No expiry or expired
                            await tracker.redis.delete(key)
                            deleted += 1
                    
                    if cursor == 0:
                        break
                
                results['sessions_cleaned'] = deleted
            
            return results
        
        results = run_async(perform_cleanup())
        
        return jsonify({
            'success': True,
            'cleanup_type': cleanup_type,
            'results': results,
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Error performing cleanup: {e}")
        return jsonify({'error': str(e)}), 500


@admin_api_bp.route('/operations/reset-metrics', methods=['POST'])
@require_tier(APITier.ADMIN)
def reset_metrics():
    """Reset system metrics (Admin only)"""
    try:
        async def reset():
            tracker, clock = await get_tracker_and_clock()
            
            # Reset tracker metrics
            if hasattr(tracker, 'operation_metrics'):
                for key in tracker.operation_metrics:
                    if isinstance(tracker.operation_metrics[key], (int, float)):
                        tracker.operation_metrics[key] = 0
            
            # Reset circuit breaker
            if hasattr(tracker, 'circuit_breaker'):
                tracker.circuit_breaker.reset()
            
            # Reset clock metrics
            if hasattr(clock, 'session_metrics'):
                for key in clock.session_metrics:
                    if isinstance(clock.session_metrics[key], (int, float)):
                        clock.session_metrics[key] = 0
            
            return {'success': True}
        
        result = run_async(reset())
        
        return jsonify({
            'success': True,
            'message': 'System metrics reset successfully',
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Error resetting metrics: {e}")
        return jsonify({'error': str(e)}), 500