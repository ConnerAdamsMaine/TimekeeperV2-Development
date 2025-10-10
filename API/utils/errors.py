# premium/API/utils/errors.py
# ============================================================================
# Error handlers for Premium API
# ============================================================================

from flask import jsonify


def register_error_handlers(app):
    """Register error handlers for the Flask app"""
    
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            'error': 'Not found',
            'message': 'The requested endpoint does not exist',
            'code': 'HTTP_404'
        }), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({
            'error': 'Internal server error',
            'message': 'An unexpected error occurred',
            'code': 'HTTP_500'
        }), 500
    
    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({
            'error': 'Bad request',
            'message': str(error),
            'code': 'HTTP_400'
        }), 400