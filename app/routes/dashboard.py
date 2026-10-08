from flask import Blueprint, render_template
from flask_login import current_user, login_required
from app.models.case import Case
from app.models.evidence import Evidence
from app.models.user import User
from app.models.audit import AuditLog
from app.models.custody import CustodyEvent
from app.utils.authorization import visible_cases

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@dashboard_bp.route('/dashboard')
@login_required
def index():
    cases_query = visible_cases(Case.query, current_user)
    case_ids = [case.id for case in cases_query.with_entities(Case.id).all()]
    evidence_query = Evidence.query.filter(Evidence.case_db_id.in_(case_ids))
    total_cases = len(case_ids)
    open_cases = cases_query.filter(Case.status.in_(['OPEN', 'IN_PROGRESS'])).count()
    closed_cases = cases_query.filter(Case.status.in_(['CLOSED', 'ARCHIVED'])).count()
    total_evidence = evidence_query.count()
    verified_evidence = evidence_query.filter_by(status='VERIFIED').count()
    pending_verification = evidence_query.filter(Evidence.status != 'VERIFIED').count()
    my_evidence = evidence_query.filter_by(collected_by=current_user.id).count()
    evidence_ids = [evidence_id for (evidence_id,) in evidence_query.with_entities(Evidence.id).all()]
    integrity_failures = AuditLog.query.filter_by(action='INTEGRITY_FAILED').filter(
        AuditLog.resource_id.in_(evidence_ids)
    ).count()
    active_investigators = User.query.filter_by(role='INVESTIGATOR', is_active=True).count()
    recent_cases = cases_query.order_by(Case.created_at.desc()).limit(5).all()
    recent_evidence = evidence_query.order_by(Evidence.created_at.desc()).limit(5).all()
    recent_custody = CustodyEvent.query.filter(CustodyEvent.case_db_id.in_(case_ids)).order_by(CustodyEvent.timestamp.desc()).limit(8).all()

    if current_user.role in ('ADMIN', 'AUDITOR'):
        recent_activity = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(8).all()
    elif current_user.role == 'INVESTIGATOR':
        relevant_ids = case_ids + evidence_ids
        recent_activity = AuditLog.query.filter(
            (AuditLog.user_id == current_user.id) | AuditLog.resource_id.in_(relevant_ids)
        ).order_by(AuditLog.timestamp.desc()).limit(8).all()
    else:
        recent_activity = []

    my_cases = Case.query.filter_by(created_by=current_user.id).count()
    assigned_cases = Case.query.filter_by(assigned_to=current_user.id).count()

    return render_template('dashboard/index.html',
                           total_cases=total_cases,
                           open_cases=open_cases,
                           closed_cases=closed_cases,
                           total_evidence=total_evidence,
                           verified_evidence=verified_evidence,
                           integrity_failures=integrity_failures,
                           active_investigators=active_investigators,
                           pending_verification=pending_verification,
                           my_evidence=my_evidence,
                           my_cases=my_cases,
                           assigned_cases=assigned_cases,
                           recent_cases=recent_cases,
                           recent_evidence=recent_evidence,
                           recent_custody=recent_custody,
                           recent_activity=recent_activity)
