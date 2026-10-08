from app.models.audit import AuditLog
from app.extensions import db
from flask import request
import logging


logger = logging.getLogger(__name__)

def log_audit_event(user_id, role, action, resource_type, resource_id, result, description=None):
    """
    Creates an audit log entry.
    """
    ip_address = request.remote_addr if request else None
    
    audit_log = AuditLog(
        user_id=user_id,
        role=role,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=ip_address,
        result=result,
        description=description
    )
    
    db.session.add(audit_log)
    db.session.commit()
    try:
        from app.services.telegram_service import notify_audit_event
        notify_audit_event(audit_log)
    except Exception:
        logger.warning('Security notification could not be prepared.')
    return audit_log
