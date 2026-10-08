from flask import abort
from sqlalchemy import or_

from app.models.case import Case
from app.models.case_viewer_grant import CaseViewerGrant
from app.services.audit_service import log_audit_event


def visible_cases(query, user):
    if user.role in ('ADMIN', 'AUDITOR'):
        return query
    if user.role == 'INVESTIGATOR':
        return query.filter(or_(Case.created_by == user.id, Case.assigned_to == user.id))
    if user.role == 'VIEWER':
        grant_case_ids = CaseViewerGrant.query.filter_by(viewer_id=user.id).with_entities(CaseViewerGrant.case_id)
        return query.filter(Case.id.in_(grant_case_ids))
    return query.filter(False)


def can_view_case(user, case):
    if user.role in ('ADMIN', 'AUDITOR'):
        return True
    if user.role == 'INVESTIGATOR':
        return case.created_by == user.id or case.assigned_to == user.id
    if user.role == 'VIEWER':
        return CaseViewerGrant.query.filter_by(case_id=case.id, viewer_id=user.id).first() is not None
    return False


def can_edit_case(user, case):
    return user.role == 'ADMIN' or (
        user.role == 'INVESTIGATOR'
        and (case.created_by == user.id or case.assigned_to == user.id)
    )


def case_for_user(case_id, user):
    case = Case.query.get_or_404(case_id)
    if not can_view_case(user, case):
        log_audit_event(user.id, user.role, 'ACCESS_DENIED', 'Case', case.id, 'FAILURE', f'Denied access to case {case.case_id}')
        abort(404)
    return case