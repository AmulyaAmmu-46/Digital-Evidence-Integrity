from flask import abort
from sqlalchemy import and_, or_
from sqlalchemy.orm import aliased

from app.extensions import db
from app.models.case import Case
from app.models.case_viewer_grant import CaseViewerGrant
from app.models.custody import CustodyEvent
from app.models.evidence import Evidence
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


def current_evidence_custodian(evidence):
    current_event = CustodyEvent.query.filter_by(evidence_db_id=evidence.id).filter(
        CustodyEvent.new_custodian.isnot(None)
    ).order_by(CustodyEvent.timestamp.desc(), CustodyEvent.id.desc()).first()
    return current_event.new_custodian if current_event else evidence.collected_by


def can_view_evidence(user, evidence):
    return can_view_case(user, evidence.case) or (
        user.role == 'INVESTIGATOR'
        and current_evidence_custodian(evidence) == user.id
    )


def evidence_for_user(evidence_id, user):
    evidence = Evidence.query.get_or_404(evidence_id)
    if not can_view_evidence(user, evidence):
        log_audit_event(user.id, user.role, 'ACCESS_DENIED', 'Evidence', evidence.id, 'FAILURE', f'Denied access to evidence {evidence.evidence_id}')
        abort(404)
    return evidence


def visible_evidence(query, user):
    case_ids = visible_cases(Case.query, user).with_entities(Case.id)
    if user.role != 'INVESTIGATOR':
        return query.filter(Evidence.case_db_id.in_(case_ids))

    later_event = aliased(CustodyEvent)
    latest_custody_for_user = CustodyEvent.query.with_entities(CustodyEvent.evidence_db_id).filter(
        CustodyEvent.new_custodian == user.id,
        ~db.session.query(later_event.id).filter(
            later_event.evidence_db_id == CustodyEvent.evidence_db_id,
            later_event.new_custodian.isnot(None),
            or_(
                later_event.timestamp > CustodyEvent.timestamp,
                and_(
                    later_event.timestamp == CustodyEvent.timestamp,
                    later_event.id > CustodyEvent.id,
                ),
            ),
        ).correlate(CustodyEvent).exists(),
    )
    return query.filter(
        or_(
            Evidence.case_db_id.in_(case_ids),
            Evidence.id.in_(latest_custody_for_user),
        )
    )


def case_for_user(case_id, user):
    case = Case.query.get_or_404(case_id)
    if not can_view_case(user, case):
        log_audit_event(user.id, user.role, 'ACCESS_DENIED', 'Case', case.id, 'FAILURE', f'Denied access to case {case.case_id}')
        abort(404)
    return case