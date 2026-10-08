from functools import wraps
from flask import abort, request
from flask_login import current_user
from app.services.audit_service import log_audit_event

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role not in roles:
                log_audit_event(current_user.id, current_user.role, 'ACCESS_DENIED', 'Route', None, 'FAILURE', f'Role is not permitted to access {request.path}')
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator
