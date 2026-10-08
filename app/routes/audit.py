from flask import Blueprint, render_template, request
from flask_login import current_user, login_required
from app.models.audit import AuditLog
from app.utils.decorators import role_required
from app.models.case import Case
from app.models.evidence import Evidence
from app.utils.authorization import visible_cases

audit_bp = Blueprint('audit', __name__)

@audit_bp.route('/')
@login_required
@role_required('ADMIN', 'AUDITOR', 'INVESTIGATOR')
def index():
    query = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    logs_query = AuditLog.query
    if current_user.role == 'INVESTIGATOR':
        case_ids = [case.id for case in visible_cases(Case.query, current_user).with_entities(Case.id).all()]
        evidence_ids = Evidence.query.filter(Evidence.case_db_id.in_(case_ids)).with_entities(Evidence.id)
        logs_query = logs_query.filter(
            (AuditLog.user_id == current_user.id)
            | AuditLog.resource_id.in_(case_ids)
            | AuditLog.resource_id.in_(evidence_ids)
        )
    if query:
        logs_query = logs_query.filter(
            AuditLog.action.ilike(f'%{query}%') | 
            AuditLog.description.ilike(f'%{query}%') |
            AuditLog.result.ilike(f'%{query}%')
        )
    pagination = logs_query.order_by(AuditLog.timestamp.desc()).paginate(page=page, per_page=100, error_out=False)
        
    return render_template('audit/index.html', logs=pagination.items, pagination=pagination, query=query)
